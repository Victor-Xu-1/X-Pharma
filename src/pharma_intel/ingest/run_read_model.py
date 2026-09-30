from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.models import IngestionRun, RunState, SourceVersion, SourceVersionState, StageStatus
from pharma_intel.schemas import IngestionRunRead, IngestionRunStageRead

_STAGE_FIELDS = (
    ("snapshot", "snapshot_status"),
    ("malware_scan", "malware_scan_status"),
    ("parse", "parse_status"),
    ("retrieval", "retrieval_status"),
    ("governance", "governance_status"),
)
_TERMINAL_VERSION_STATES = {
    SourceVersionState.INDEXED,
    SourceVersionState.REVIEW_PENDING,
    SourceVersionState.PUBLISHED,
    SourceVersionState.ASSET_ONLY,
    SourceVersionState.FAILED,
}


class IngestionRunReadService:
    def __init__(self, session: Session, tenant_id: str) -> None:
        self.session = session
        self.tenant_id = tenant_id

    def build_many(self, runs: Sequence[IngestionRun]) -> list[IngestionRunRead]:
        version_ids_by_run = {run.id: _version_ids(run) for run in runs}
        all_version_ids = sorted({version_id for ids in version_ids_by_run.values() for version_id in ids})
        versions_by_id: dict[str, SourceVersion] = {}
        if all_version_ids:
            versions_by_id = {
                version.id: version
                for version in self.session.scalars(
                    select(SourceVersion).where(
                        SourceVersion.tenant_id == self.tenant_id,
                        SourceVersion.id.in_(all_version_ids),
                    )
                )
            }
        return [
            self._build(run, [versions_by_id[item] for item in version_ids_by_run[run.id] if item in versions_by_id])
            for run in runs
        ]

    def build(self, run: IngestionRun) -> IngestionRunRead:
        return self.build_many([run])[0]

    def _build(self, run: IngestionRun, versions: list[SourceVersion]) -> IngestionRunRead:
        stages = [
            _discovery_stage(run),
            *(_version_stage(stage, field, versions, run) for stage, field in _STAGE_FIELDS),
        ]
        effective_state = _effective_state(run, stages, versions)
        progress = (
            round(sum(_stage_progress(stage) for stage in stages) / len(stages))
            if effective_state in {RunState.PENDING, RunState.RUNNING}
            else 100
        )
        return IngestionRunRead(
            id=run.id,
            data_source_id=run.data_source_id,
            workflow_id=run.workflow_id,
            temporal_workflow_id=run.temporal_workflow_id,
            temporal_run_id=run.temporal_run_id,
            state=run.state,
            effective_state=effective_state,
            started_at=run.started_at,
            completed_at=run.completed_at,
            heartbeat_at=run.heartbeat_at,
            counters=run.counters,
            result=run.result,
            error_summary=run.error_summary,
            cancel_requested_at=run.cancel_requested_at,
            cancelable=(
                effective_state == RunState.RUNNING
                and run.cancel_requested_at is None
                and bool(run.temporal_workflow_id)
                and bool(run.temporal_run_id)
            ),
            progress_percent=max(0, min(100, progress)),
            total_versions=len(versions),
            completed_versions=sum(version.state in _TERMINAL_VERSION_STATES for version in versions),
            stages=stages,
            created_at=run.created_at,
        )


def _version_ids(run: IngestionRun) -> list[str]:
    values = run.result.get("version_ids") if isinstance(run.result, dict) else None
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(str(value) for value in values if isinstance(value, str) and value))


def _discovery_stage(run: IngestionRun) -> IngestionRunStageRead:
    if run.state == RunState.PENDING:
        status = "not_started"
    elif run.state == RunState.RUNNING:
        status = "running"
    elif run.state == RunState.FAILED:
        status = "failed"
    elif run.state == RunState.CANCELED:
        status = "canceled"
    else:
        status = "succeeded"
    return IngestionRunStageRead(
        stage="discovery",
        status=status,
        completed_items=1 if status == "succeeded" else 0,
        failed_items=1 if status == "failed" else 0,
        total_items=1,
    )


def _version_stage(
    stage: str,
    field: str,
    versions: Sequence[SourceVersion],
    run: IngestionRun,
) -> IngestionRunStageRead:
    if not versions:
        status = "canceled" if run.state == RunState.CANCELED else "not_started"
        if run.state in {RunState.SUCCEEDED, RunState.PARTIAL}:
            status = "skipped"
        return IngestionRunStageRead(
            stage=stage,
            status=status,
            completed_items=0,
            failed_items=0,
            total_items=0,
        )
    statuses = [getattr(version, field) for version in versions]
    counts: defaultdict[StageStatus, int] = defaultdict(int)
    for value in statuses:
        counts[value] += 1
    status = _aggregate_status(counts, len(statuses))
    if run.state == RunState.CANCELED and status in {"not_started", "running"}:
        status = "canceled"
    return IngestionRunStageRead(
        stage=stage,
        status=status,
        completed_items=counts[StageStatus.SUCCEEDED] + counts[StageStatus.SKIPPED],
        failed_items=counts[StageStatus.FAILED],
        total_items=len(statuses),
    )


def _aggregate_status(counts: dict[StageStatus, int], total: int) -> str:
    if counts[StageStatus.RUNNING]:
        return "running"
    if counts[StageStatus.FAILED]:
        return "failed"
    if counts[StageStatus.NOT_STARTED]:
        return "not_started" if counts[StageStatus.NOT_STARTED] == total else "running"
    if counts[StageStatus.SUCCEEDED]:
        return "succeeded"
    return "skipped"


def _effective_state(
    run: IngestionRun,
    stages: Iterable[IngestionRunStageRead],
    versions: Sequence[SourceVersion],
) -> RunState:
    if run.state in {RunState.FAILED, RunState.CANCELED}:
        return run.state
    if run.state in {RunState.PENDING, RunState.RUNNING}:
        return run.state
    stage_statuses = [stage.status for stage in stages]
    has_active_versions = any(version.state not in _TERMINAL_VERSION_STATES for version in versions)
    if has_active_versions and ("running" in stage_statuses or "not_started" in stage_statuses):
        return RunState.RUNNING
    if "failed" in stage_statuses:
        completed = sum(
            version.state in _TERMINAL_VERSION_STATES and version.state != SourceVersionState.FAILED
            for version in versions
        )
        return RunState.PARTIAL if completed or run.state == RunState.PARTIAL else RunState.FAILED
    return RunState.PARTIAL if run.state == RunState.PARTIAL else RunState.SUCCEEDED


def _stage_progress(stage: IngestionRunStageRead) -> int:
    if stage.total_items == 0:
        return 100 if stage.status == "skipped" else 0
    terminal = stage.completed_items + stage.failed_items
    if stage.status == "canceled":
        terminal = max(terminal, stage.total_items)
    return round(100 * terminal / stage.total_items)
