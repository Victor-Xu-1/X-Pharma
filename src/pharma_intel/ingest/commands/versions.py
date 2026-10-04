from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from pharma_intel.config import Settings
from pharma_intel.governance.source_policy import source_governance_policy
from pharma_intel.ingest.commands.errors import IngestionCommandError
from pharma_intel.ingest.contracts import ProcessInput
from pharma_intel.ingest.replay import replayable_source_version_stages
from pharma_intel.ingest.workflows import SourceVersionReprocessWorkflow
from pharma_intel.models import AuditEvent, QuarantineStatus, SourceVersion, SourceVersionOperation
from pharma_intel.schemas import SourceVersionReplayAcceptedRead, SourceVersionReplayRequest
from pharma_intel.security import Principal


async def replay_source_version(
    version_id: str,
    payload: SourceVersionReplayRequest,
    request_id: str,
    principal: Principal,
    session: Session,
    *,
    settings: Settings,
) -> SourceVersionReplayAcceptedRead:
    principal.require("ingestion:manage")
    version = session.scalar(
        select(SourceVersion).where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
        )
    )
    if version is None:
        raise IngestionCommandError(status_code=404, detail="Source version not found")
    operation = session.scalar(
        select(SourceVersionOperation).where(
            SourceVersionOperation.tenant_id == principal.tenant_id,
            SourceVersionOperation.operation_key == payload.operation_key,
        )
    )
    if operation is not None:
        same_command = (
            operation.source_version_id == version.id
            and operation.operation_type == "replay"
            and operation.from_stage == payload.from_stage
            and operation.expected_state == payload.expected_state.value
            and operation.expected_error_code == payload.expected_error_code
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise IngestionCommandError(
                status_code=409, detail="Operation key was already used with different arguments"
            )
        if operation.state == "accepted":
            return SourceVersionReplayAcceptedRead.model_validate(operation.response)
        if operation.state == "pending":
            raise IngestionCommandError(
                status_code=409, detail="Source version replay operation is already in progress"
            )

    if version.error_code == "malware_detected" and version.quarantine_status not in {
        QuarantineStatus.NOT_APPLICABLE,
        QuarantineStatus.CLEARED,
    }:
        raise IngestionCommandError(
            status_code=409,
            detail={
                "code": "quarantine_decision_required",
                "quarantine_status": version.quarantine_status.value,
                "quarantine_version": version.quarantine_version,
            },
        )

    if version.state != payload.expected_state or version.error_code != payload.expected_error_code:
        raise IngestionCommandError(
            status_code=409,
            detail={
                "code": "source_version_state_conflict",
                "expected_state": payload.expected_state.value,
                "current_state": version.state.value,
                "expected_error_code": payload.expected_error_code,
                "current_error_code": version.error_code,
            },
        )
    replayable_stages = replayable_source_version_stages(
        version,
        governance_enabled=source_governance_policy(session, settings, version) is not None,
    )
    if payload.from_stage not in replayable_stages:
        raise IngestionCommandError(
            status_code=409,
            detail={
                "code": "source_version_stage_not_replayable",
                "requested_stage": payload.from_stage,
                "replayable_stages": replayable_stages,
            },
        )

    if operation is not None:
        claimed = session.execute(
            update(SourceVersionOperation)
            .where(
                SourceVersionOperation.id == operation.id,
                SourceVersionOperation.state == "failed",
            )
            .values(state="pending", last_error=None)
        )
        session.commit()
        if claimed.rowcount != 1:
            raise IngestionCommandError(
                status_code=409, detail="Source version replay operation is already in progress"
            )
        session.refresh(operation)
    else:
        accepted = SourceVersionReplayAcceptedRead(
            workflow_id=f"source-version-reprocess-{version.id}",
            source_version_id=version.id,
            from_stage=payload.from_stage,
            status="accepted",
        )
        operation = SourceVersionOperation(
            tenant_id=principal.tenant_id,
            source_version_id=version.id,
            operation_key=payload.operation_key,
            operation_type="replay",
            from_stage=payload.from_stage,
            expected_state=payload.expected_state.value,
            expected_error_code=payload.expected_error_code,
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
                status_code=409,
                detail="Source version replay operation is already in progress",
            ) from exc

    accepted = SourceVersionReplayAcceptedRead.model_validate(operation.response)
    if not settings.temporal_enabled:
        operation.state = "failed"
        operation.last_error = "Durable workflow service is not enabled"
        session.commit()
        raise IngestionCommandError(status_code=503, detail=operation.last_error)
    try:
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        await client.start_workflow(
            SourceVersionReprocessWorkflow.run,
            ProcessInput(principal.tenant_id, version.id, from_stage=payload.from_stage),
            id=accepted.workflow_id,
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        )
    except WorkflowAlreadyStartedError as exc:
        operation.state = "failed"
        operation.last_error = "A replay is already running for this source version"
        session.commit()
        raise IngestionCommandError(status_code=409, detail=operation.last_error) from exc
    except Exception as exc:
        operation.state = "failed"
        operation.last_error = "Durable workflow service is unavailable"
        session.commit()
        raise IngestionCommandError(status_code=503, detail=operation.last_error) from exc
    operation.state = "accepted"
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="source_version.replay",
            resource_type="source_version",
            resource_id=version.id,
            outcome="success",
            request_id=request_id,
            details={
                "reason": payload.reason,
                "operation_key": payload.operation_key,
                "from_stage": payload.from_stage,
                "expected_state": payload.expected_state.value,
                "expected_error_code": payload.expected_error_code,
                "workflow_id": accepted.workflow_id,
            },
        )
    )
    session.commit()
    return accepted
