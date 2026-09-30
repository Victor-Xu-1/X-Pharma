from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from temporalio.client import Client, WorkflowExecutionStatus

from pharma_intel.db import set_tenant_context
from pharma_intel.models import IngestionRun, RunState, Tenant

logger = structlog.get_logger(__name__)

STALE_INGESTION_RUN_SECONDS = 300
MAX_RECONCILIATIONS_PER_TENANT = 25
MAX_TEMPORAL_LOOKUP_CONCURRENCY = 5
TEMPORAL_LOOKUP_TIMEOUT = timedelta(seconds=5)


@dataclass(frozen=True)
class IngestionRunReconciliationReport:
    scanned: int = 0
    reconciled: int = 0
    still_running: int = 0
    failed: int = 0


@dataclass(frozen=True)
class _Candidate:
    id: str
    tenant_id: str
    temporal_workflow_id: str
    temporal_run_id: str
    observed_heartbeat_at: datetime


@dataclass(frozen=True)
class _Resolution:
    state: RunState
    completed_at: datetime
    counters: dict[str, int] | None = None
    result: dict[str, Any] | None = None
    error_summary: str | None = None


@dataclass(frozen=True)
class _Inspection:
    candidate: _Candidate
    resolution: _Resolution | None = None
    still_running: bool = False
    failed: bool = False


async def reconcile_stale_ingestion_runs(
    client: Client,
    session_factory: sessionmaker[Session],
    *,
    now: datetime | None = None,
    stale_after: timedelta = timedelta(seconds=STALE_INGESTION_RUN_SECONDS),
) -> IngestionRunReconciliationReport:
    reconciled_at = now or datetime.now(UTC)
    if stale_after.total_seconds() <= 0:
        raise ValueError("stale_after must be positive")
    candidates = _load_candidates(session_factory, reconciled_at - stale_after)
    if not candidates:
        return IngestionRunReconciliationReport()

    semaphore = asyncio.Semaphore(MAX_TEMPORAL_LOOKUP_CONCURRENCY)

    async def inspect(candidate: _Candidate) -> _Inspection:
        async with semaphore:
            return await _inspect_execution(client, candidate, reconciled_at)

    inspections = await asyncio.gather(*(inspect(candidate) for candidate in candidates))
    reconciled = 0
    failed = 0
    still_running = 0
    for inspection in inspections:
        failed += int(inspection.failed)
        still_running += int(inspection.still_running)
        if inspection.resolution is not None and _apply_resolution(
            session_factory,
            inspection.candidate,
            inspection.resolution,
        ):
            reconciled += 1
    return IngestionRunReconciliationReport(
        scanned=len(candidates),
        reconciled=reconciled,
        still_running=still_running,
        failed=failed,
    )


def _load_candidates(
    session_factory: sessionmaker[Session],
    stale_before: datetime,
) -> list[_Candidate]:
    with session_factory() as identity_session:
        tenant_ids = list(identity_session.scalars(select(Tenant.id).where(Tenant.active.is_(True))))
    candidates: list[_Candidate] = []
    for tenant_id in tenant_ids:
        with session_factory() as session:
            set_tenant_context(session, tenant_id)
            heartbeat = func.coalesce(IngestionRun.heartbeat_at, IngestionRun.started_at, IngestionRun.created_at)
            runs = session.scalars(
                select(IngestionRun)
                .where(
                    IngestionRun.tenant_id == tenant_id,
                    IngestionRun.state.in_([RunState.PENDING, RunState.RUNNING]),
                    IngestionRun.temporal_workflow_id.is_not(None),
                    IngestionRun.temporal_run_id.is_not(None),
                    heartbeat < stale_before,
                )
                .order_by(heartbeat)
                .limit(MAX_RECONCILIATIONS_PER_TENANT)
            )
            for run in runs:
                observed = run.heartbeat_at or run.started_at or run.created_at
                if run.temporal_workflow_id is None or run.temporal_run_id is None:
                    continue
                candidates.append(
                    _Candidate(
                        id=run.id,
                        tenant_id=tenant_id,
                        temporal_workflow_id=run.temporal_workflow_id,
                        temporal_run_id=run.temporal_run_id,
                        observed_heartbeat_at=observed,
                    )
                )
    return candidates


async def _inspect_execution(client: Client, candidate: _Candidate, now: datetime) -> _Inspection:
    handle = client.get_workflow_handle(candidate.temporal_workflow_id, run_id=candidate.temporal_run_id)
    try:
        description = await handle.describe(rpc_timeout=TEMPORAL_LOOKUP_TIMEOUT)
    except Exception as exc:
        logger.warning(
            "stale_ingestion_temporal_describe_failed",
            ingestion_run_id=candidate.id,
            temporal_workflow_id=candidate.temporal_workflow_id,
            temporal_run_id=candidate.temporal_run_id,
            error_type=type(exc).__name__,
        )
        return _Inspection(candidate, failed=True)

    status = description.status
    if status is None or status in {
        WorkflowExecutionStatus.RUNNING,
        WorkflowExecutionStatus.CONTINUED_AS_NEW,
    }:
        return _Inspection(candidate, still_running=True)
    completed_at = description.close_time or now
    if status == WorkflowExecutionStatus.COMPLETED:
        try:
            payload = await handle.result(
                follow_runs=False,
                rpc_timeout=TEMPORAL_LOOKUP_TIMEOUT,
            )
        except Exception as exc:
            logger.warning(
                "stale_ingestion_temporal_result_failed",
                ingestion_run_id=candidate.id,
                temporal_workflow_id=candidate.temporal_workflow_id,
                temporal_run_id=candidate.temporal_run_id,
                error_type=type(exc).__name__,
            )
            return _Inspection(candidate, failed=True)
        resolution = _resolution_from_completed_payload(candidate, payload, completed_at)
        if resolution is None:
            return _Inspection(
                candidate,
                _Resolution(
                    state=RunState.FAILED,
                    completed_at=completed_at,
                    error_summary="Temporal workflow completed without a valid ingestion scan result",
                ),
                failed=True,
            )
        return _Inspection(candidate, resolution)
    if status in {WorkflowExecutionStatus.CANCELED, WorkflowExecutionStatus.TERMINATED}:
        return _Inspection(
            candidate,
            _Resolution(
                state=RunState.CANCELED,
                completed_at=completed_at,
                error_summary=f"Temporal workflow ended with {status.name.lower()}",
            ),
        )
    return _Inspection(
        candidate,
        _Resolution(
            state=RunState.FAILED,
            completed_at=completed_at,
            error_summary=f"Temporal workflow ended with {status.name.lower()}",
        ),
    )


def _resolution_from_completed_payload(
    candidate: _Candidate,
    payload: object,
    completed_at: datetime,
) -> _Resolution | None:
    if not isinstance(payload, Mapping):
        return None
    scan = payload.get("scan")
    if not isinstance(scan, Mapping) or scan.get("run_id") != candidate.id:
        return None
    state = scan.get("state")
    if not isinstance(state, str):
        return None
    state_map = {
        "succeeded": RunState.SUCCEEDED,
        "partial": RunState.PARTIAL,
        "failed": RunState.FAILED,
        "canceled": RunState.CANCELED,
    }
    run_state = state_map.get(state)
    if run_state is None:
        return None
    counters: dict[str, int] = {}
    for key in ("discovered", "unchanged", "unstable", "excluded", "failed"):
        value = scan.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        counters[key] = value
    version_ids = scan.get("version_ids")
    if version_ids is None:
        version_ids = []
    if not isinstance(version_ids, list) or any(not isinstance(item, str) for item in version_ids):
        return None
    error_summary = None
    if run_state == RunState.PARTIAL:
        error_summary = f"{counters['failed']} source items failed"
    elif run_state == RunState.FAILED:
        error_summary = "Temporal workflow completed with a failed ingestion scan"
    return _Resolution(
        state=run_state,
        completed_at=completed_at,
        counters=counters,
        result={"version_ids": list(dict.fromkeys(version_ids))},
        error_summary=error_summary,
    )


def _apply_resolution(
    session_factory: sessionmaker[Session],
    candidate: _Candidate,
    resolution: _Resolution,
) -> bool:
    with session_factory() as session:
        set_tenant_context(session, candidate.tenant_id)
        run = session.scalar(
            select(IngestionRun)
            .where(
                IngestionRun.id == candidate.id,
                IngestionRun.tenant_id == candidate.tenant_id,
                IngestionRun.state.in_([RunState.PENDING, RunState.RUNNING]),
                IngestionRun.temporal_workflow_id == candidate.temporal_workflow_id,
                IngestionRun.temporal_run_id == candidate.temporal_run_id,
            )
            .with_for_update()
        )
        if run is None:
            return False
        current_heartbeat = run.heartbeat_at or run.started_at or run.created_at
        if current_heartbeat != candidate.observed_heartbeat_at:
            return False
        run.state = resolution.state
        run.completed_at = resolution.completed_at
        run.heartbeat_at = resolution.completed_at
        if resolution.counters is not None:
            run.counters = resolution.counters
        if resolution.result is not None:
            run.result = resolution.result
        run.error_summary = resolution.error_summary
        session.commit()
        return True
