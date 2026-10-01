from __future__ import annotations

from typing import Literal, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from pharma_intel.config import Settings
from pharma_intel.ingest.commands.errors import IngestionCommandError
from pharma_intel.ingest.contracts import ProcessInput
from pharma_intel.ingest.quarantine import QuarantineTransitionError, apply_operator_decision, record_rescan_failure
from pharma_intel.ingest.workflows import SourceVersionReprocessWorkflow
from pharma_intel.models import (
    AuditEvent,
    QuarantineStatus,
    SourceVersion,
    SourceVersionOperation,
    SourceVersionQuarantineDecision,
)
from pharma_intel.schemas import SourceVersionQuarantineDecisionAcceptedRead, SourceVersionQuarantineDecisionRequest
from pharma_intel.security import Principal


def _quarantine_decision_response(
    decision: SourceVersionQuarantineDecision,
) -> SourceVersionQuarantineDecisionAcceptedRead:
    return SourceVersionQuarantineDecisionAcceptedRead(
        decision_id=decision.id,
        source_version_id=decision.source_version_id,
        action=cast(Literal["hold", "reject", "rescan"], decision.action),
        quarantine_status=decision.resulting_status,
        quarantine_version=decision.resulting_version,
        workflow_id=decision.workflow_id,
        status="accepted",
    )


async def decide_source_version_quarantine_case(
    version_id: str,
    payload: SourceVersionQuarantineDecisionRequest,
    request_id: str,
    principal: Principal,
    session: Session,
    *,
    settings: Settings,
) -> SourceVersionQuarantineDecisionAcceptedRead:
    principal.require("ingestion:manage")
    version = session.scalar(
        select(SourceVersion)
        .where(
            SourceVersion.id == version_id,
            SourceVersion.tenant_id == principal.tenant_id,
        )
        .with_for_update()
    )
    if version is None or version.quarantine_status == QuarantineStatus.NOT_APPLICABLE:
        raise IngestionCommandError(status_code=404, detail="Quarantine case not found")

    operation_type = f"quarantine_{payload.action}"
    operation = session.scalar(
        select(SourceVersionOperation).where(
            SourceVersionOperation.tenant_id == principal.tenant_id,
            SourceVersionOperation.operation_key == payload.operation_key,
        )
    )
    decision: SourceVersionQuarantineDecision | None = None
    if operation is not None:
        same_command = (
            operation.source_version_id == version.id
            and operation.operation_type == operation_type
            and operation.expected_quarantine_version == payload.expected_version
            and operation.reason == payload.reason
            and operation.requested_by_actor_type == principal.actor_type
            and operation.requested_by_actor_id == principal.actor_id
        )
        if not same_command:
            raise IngestionCommandError(
                status_code=409, detail="Operation key was already used with different arguments"
            )
        decision = session.scalar(
            select(SourceVersionQuarantineDecision).where(
                SourceVersionQuarantineDecision.tenant_id == principal.tenant_id,
                SourceVersionQuarantineDecision.operation_key == payload.operation_key,
            )
        )
        if decision is None:
            raise IngestionCommandError(status_code=409, detail="Quarantine operation is missing its decision record")
        accepted = SourceVersionQuarantineDecisionAcceptedRead.model_validate(operation.response)
        if operation.state == "accepted":
            return accepted
        if operation.state == "failed":
            raise IngestionCommandError(
                status_code=409,
                detail="Previous quarantine operation failed; refresh and submit a new operation key",
            )
        if payload.action != "rescan":
            raise IngestionCommandError(status_code=409, detail="Quarantine operation is already in progress")
        if version.quarantine_status != QuarantineStatus.RESCAN_REQUESTED:
            operation.state = "accepted"
            operation.response = accepted.model_dump(mode="json")
            session.commit()
            return accepted
    else:
        workflow_id = f"source-version-reprocess-{version.id}" if payload.action == "rescan" else None
        try:
            outcome = apply_operator_decision(
                session,
                version,
                operation_key=payload.operation_key,
                expected_version=payload.expected_version,
                action=payload.action,
                reason=payload.reason,
                actor_type=principal.actor_type,
                actor_id=principal.actor_id,
                workflow_id=workflow_id,
            )
        except QuarantineTransitionError as exc:
            raise IngestionCommandError(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
        decision = outcome.decision
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise IngestionCommandError(status_code=409, detail="Quarantine operation already exists") from exc
        accepted = _quarantine_decision_response(decision)
        operation = SourceVersionOperation(
            tenant_id=principal.tenant_id,
            source_version_id=version.id,
            operation_key=payload.operation_key,
            operation_type=operation_type,
            from_stage="malware_scan" if payload.action == "rescan" else "quarantine",
            expected_state=version.state.value,
            expected_error_code=version.error_code,
            expected_quarantine_version=payload.expected_version,
            reason=payload.reason,
            requested_by_actor_type=principal.actor_type,
            requested_by_actor_id=principal.actor_id,
            state="pending" if payload.action == "rescan" else "accepted",
            response=accepted.model_dump(mode="json"),
        )
        session.add(operation)
        if payload.action != "rescan":
            session.add(
                AuditEvent(
                    tenant_id=principal.tenant_id,
                    actor_type=principal.actor_type,
                    actor_id=principal.actor_id,
                    action=f"source_version.quarantine.{payload.action}",
                    resource_type="source_version",
                    resource_id=version.id,
                    outcome="success",
                    request_id=request_id,
                    details={
                        "operation_key": payload.operation_key,
                        "reason": payload.reason,
                        "expected_version": payload.expected_version,
                        "resulting_version": decision.resulting_version,
                        "previous_status": decision.previous_status.value,
                        "resulting_status": decision.resulting_status.value,
                    },
                )
            )
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise IngestionCommandError(status_code=409, detail="Quarantine operation already exists") from exc
        if payload.action != "rescan":
            return accepted

    assert decision is not None
    if not settings.temporal_enabled:
        operation.state = "failed"
        operation.last_error = "Durable workflow service is not enabled"
        record_rescan_failure(
            session,
            version,
            reason=operation.last_error,
            actor_id="api",
        )
        session.commit()
        raise IngestionCommandError(status_code=503, detail=operation.last_error)
    try:
        client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
        await client.start_workflow(
            SourceVersionReprocessWorkflow.run,
            ProcessInput(principal.tenant_id, version.id, from_stage="malware_scan"),
            id=decision.workflow_id or f"source-version-reprocess-{version.id}",
            task_queue=settings.temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        pass
    except Exception as exc:
        operation.state = "failed"
        operation.last_error = "Durable quarantine rescan workflow is unavailable"
        record_rescan_failure(
            session,
            version,
            reason=operation.last_error,
            actor_id="api",
        )
        session.add(
            AuditEvent(
                tenant_id=principal.tenant_id,
                actor_type=principal.actor_type,
                actor_id=principal.actor_id,
                action="source_version.quarantine.rescan",
                resource_type="source_version",
                resource_id=version.id,
                outcome="failure",
                request_id=request_id,
                details={"operation_key": payload.operation_key, "reason": payload.reason},
            )
        )
        session.commit()
        raise IngestionCommandError(status_code=503, detail=operation.last_error) from exc

    operation.state = "accepted"
    operation.last_error = None
    session.add(
        AuditEvent(
            tenant_id=principal.tenant_id,
            actor_type=principal.actor_type,
            actor_id=principal.actor_id,
            action="source_version.quarantine.rescan",
            resource_type="source_version",
            resource_id=version.id,
            outcome="success",
            request_id=request_id,
            details={
                "operation_key": payload.operation_key,
                "reason": payload.reason,
                "expected_version": payload.expected_version,
                "workflow_id": decision.workflow_id,
                "from_stage": "malware_scan",
            },
        )
    )
    session.commit()
    return SourceVersionQuarantineDecisionAcceptedRead.model_validate(operation.response)
