from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from temporalio.client import Client

from pharma_intel.config import Settings
from pharma_intel.ingest.commands.errors import IngestionCommandError
from pharma_intel.ingest.commands.scan import _start_data_source_scan
from pharma_intel.ingest.run_read_model import IngestionRunReadService
from pharma_intel.models import AuditEvent, DataSource, IngestionRun, IngestionRunOperation, RunState
from pharma_intel.schemas import (
    IngestionRunCancelAcceptedRead,
    IngestionRunCancelRequest,
    IngestionRunReplayRequest,
    IngestionScanAcceptedRead,
)
from pharma_intel.security import Principal


async def cancel_ingestion_run(
    run_id: str,
    payload: IngestionRunCancelRequest,
    request_id: str,
    principal: Principal,
    session: Session,
    *,
    settings: Settings,
) -> IngestionRunCancelAcceptedRead:
    principal.require("ingestion:manage")
    run = session.scalar(
        select(IngestionRun).where(
            IngestionRun.id == run_id,
            IngestionRun.tenant_id == principal.tenant_id,
        )
    )
    if run is None:
        raise IngestionCommandError(status_code=404, detail="Ingestion run not found")
    operation = session.scalar(
        select(IngestionRunOperation).where(
            IngestionRunOperation.tenant_id == principal.tenant_id,
            IngestionRunOperation.operation_key == payload.operation_key,
        )
    )
    if operation is not None:
        same_command = (
            operation.ingestion_run_id == run.id
            and operation.operation_type == "cancel"
            and operation.expected_state == payload.expected_state
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise IngestionCommandError(
                status_code=409, detail="Operation key was already used with different arguments"
            )
        if operation.state == "accepted":
            return IngestionRunCancelAcceptedRead.model_validate(operation.response)
        if operation.state == "pending":
            raise IngestionCommandError(status_code=409, detail="Ingestion cancel operation is already in progress")
        claimed = session.execute(
            update(IngestionRunOperation)
            .where(
                IngestionRunOperation.id == operation.id,
                IngestionRunOperation.state == "failed",
            )
            .values(state="pending", last_error=None)
        )
        if claimed.rowcount != 1:
            session.rollback()
            raise IngestionCommandError(status_code=409, detail="Ingestion cancel operation is already in progress")

    run_read = IngestionRunReadService(session, principal.tenant_id).build(run)
    if run_read.effective_state.value != payload.expected_state:
        raise IngestionCommandError(
            status_code=409,
            detail={
                "code": "ingestion_run_state_conflict",
                "expected_state": payload.expected_state,
                "current_state": run_read.effective_state.value,
            },
        )
    if not run.temporal_workflow_id or not run.temporal_run_id:
        raise IngestionCommandError(status_code=409, detail="Ingestion run does not have a bound Temporal execution")
    if run.cancel_requested_at is not None and operation is None:
        raise IngestionCommandError(status_code=409, detail="Ingestion cancellation was already requested")

    accepted = IngestionRunCancelAcceptedRead(
        run_id=run.id,
        workflow_id=run.workflow_id,
        temporal_workflow_id=run.temporal_workflow_id,
        temporal_run_id=run.temporal_run_id,
        status="cancel_requested",
    )
    if operation is None:
        operation = IngestionRunOperation(
            tenant_id=principal.tenant_id,
            ingestion_run_id=run.id,
            operation_key=payload.operation_key,
            operation_type="cancel",
            expected_state=payload.expected_state,
            reason=payload.reason,
            requested_by_actor_type=principal.actor_type,
            requested_by_actor_id=principal.actor_id,
            response=accepted.model_dump(mode="json"),
        )
        session.add(operation)
    else:
        operation.response = accepted.model_dump(mode="json")
    run.cancel_requested_at = datetime.now(UTC)
    run.cancel_reason = payload.reason
    run.cancel_requested_by_actor_type = principal.actor_type
    run.cancel_requested_by_actor_id = principal.actor_id
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise IngestionCommandError(
            status_code=409, detail="Ingestion cancel operation is already in progress"
        ) from exc

    temporal_workflow_id = run.temporal_workflow_id
    temporal_run_id = run.temporal_run_id
    try:
        if not settings.temporal_enabled:
            raise IngestionCommandError(status_code=503, detail="Durable workflow service is not enabled")
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        handle = client.get_workflow_handle(temporal_workflow_id, run_id=temporal_run_id)
        await handle.cancel(reason=payload.reason)
    except IngestionCommandError as exc:
        operation.state = "failed"
        operation.last_error = str(exc.detail)[:4000]
        run.cancel_requested_at = None
        run.cancel_reason = None
        run.cancel_requested_by_actor_type = None
        run.cancel_requested_by_actor_id = None
        session.commit()
        raise
    except Exception as exc:
        operation.state = "failed"
        operation.last_error = str(exc)[:4000]
        run.cancel_requested_at = None
        run.cancel_reason = None
        run.cancel_requested_by_actor_type = None
        run.cancel_requested_by_actor_id = None
        session.commit()
        raise IngestionCommandError(status_code=503, detail="Durable workflow cancellation is unavailable") from exc

    now = datetime.now(UTC)
    run.state = RunState.CANCELED
    run.completed_at = now
    run.heartbeat_at = now
    run.error_summary = f"Canceled by operator: {payload.reason}"[:4000]
    run.result = {**run.result, "cancellation": {"status": "requested", "operation_id": operation.id}}
    operation.state = "accepted"
    operation.response = accepted.model_dump(mode="json")
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="ingestion_run.cancel",
            resource_type="ingestion_run",
            resource_id=run.id,
            outcome="success",
            request_id=request_id,
            details={
                "reason": payload.reason,
                "operation_key": payload.operation_key,
                "expected_state": payload.expected_state,
                "data_source_id": run.data_source_id,
                "workflow_id": run.workflow_id,
                "temporal_workflow_id": temporal_workflow_id,
                "temporal_run_id": temporal_run_id,
            },
        )
    )
    session.commit()
    return accepted


async def replay_ingestion_run(
    run_id: str,
    payload: IngestionRunReplayRequest,
    request_id: str,
    principal: Principal,
    session: Session,
    *,
    settings: Settings,
) -> IngestionScanAcceptedRead:
    principal.require("ingestion:manage")
    run = session.scalar(
        select(IngestionRun).where(
            IngestionRun.id == run_id,
            IngestionRun.tenant_id == principal.tenant_id,
        )
    )
    if run is None:
        raise IngestionCommandError(status_code=404, detail="Ingestion run not found")
    if run.state.value != payload.expected_state:
        raise IngestionCommandError(
            status_code=409,
            detail={
                "code": "ingestion_run_state_conflict",
                "expected_state": payload.expected_state,
                "current_state": run.state.value,
            },
        )
    if run.state not in {RunState.FAILED, RunState.PARTIAL, RunState.CANCELED}:
        raise IngestionCommandError(
            status_code=409, detail=f"Ingestion run in {run.state.value} state cannot be replayed"
        )
    source = session.scalar(
        select(DataSource).where(
            DataSource.id == run.data_source_id,
            DataSource.tenant_id == principal.tenant_id,
        )
    )
    if source is None:
        raise IngestionCommandError(status_code=409, detail="The ingestion run data source is no longer available")
    operation = session.scalar(
        select(IngestionRunOperation).where(
            IngestionRunOperation.tenant_id == principal.tenant_id,
            IngestionRunOperation.operation_key == payload.operation_key,
        )
    )
    if operation is not None:
        same_command = (
            operation.ingestion_run_id == run.id
            and operation.operation_type == "replay"
            and operation.expected_state == payload.expected_state
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise IngestionCommandError(
                status_code=409, detail="Operation key was already used with different arguments"
            )
        if operation.state == "accepted":
            return IngestionScanAcceptedRead.model_validate(operation.response)
        if operation.state == "pending":
            raise IngestionCommandError(status_code=409, detail="Ingestion replay operation is already in progress")
        claimed = session.execute(
            update(IngestionRunOperation)
            .where(
                IngestionRunOperation.id == operation.id,
                IngestionRunOperation.state == "failed",
            )
            .values(state="pending", last_error=None)
        )
        session.commit()
        if claimed.rowcount != 1:
            raise IngestionCommandError(status_code=409, detail="Ingestion replay operation is already in progress")
        session.refresh(operation)
    else:
        workflow_id = f"source-ingest-{source.id}"
        accepted = IngestionScanAcceptedRead(
            workflow_id=workflow_id,
            ingestion_run_id=f"{workflow_id}-{uuid.uuid4()}",
            status="accepted",
            replayed_from_run_id=run.id,
        )
        operation = IngestionRunOperation(
            tenant_id=principal.tenant_id,
            ingestion_run_id=run.id,
            operation_key=payload.operation_key,
            operation_type="replay",
            expected_state=payload.expected_state,
            reason=payload.reason,
            requested_by_actor_type=principal.actor_type,
            requested_by_actor_id=principal.actor_id,
            response=accepted.model_dump(mode="json"),
        )
        session.add(operation)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise IngestionCommandError(
                status_code=409, detail="Ingestion replay operation is already in progress"
            ) from exc

    accepted = IngestionScanAcceptedRead.model_validate(operation.response)
    try:
        accepted = await _start_data_source_scan(
            source,
            principal,
            session,
            replayed_from_run_id=run.id,
            run_correlation_id=accepted.ingestion_run_id,
            settings=settings,
        )
    except IngestionCommandError as exc:
        operation.state = "failed"
        operation.last_error = str(exc.detail)[:4000]
        session.commit()
        raise
    operation.state = "accepted"
    operation.response = accepted.model_dump(mode="json")
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="ingestion_run.replay",
            resource_type="ingestion_run",
            resource_id=run.id,
            outcome="success",
            request_id=request_id,
            details={
                "reason": payload.reason,
                "operation_key": payload.operation_key,
                "expected_state": payload.expected_state,
                "data_source_id": source.id,
                "workflow_id": accepted.workflow_id,
                "ingestion_run_id": accepted.ingestion_run_id,
            },
        )
    )
    session.commit()
    return accepted
