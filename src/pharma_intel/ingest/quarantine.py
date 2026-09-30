from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.models import (
    QuarantineStatus,
    SourceVersion,
    SourceVersionQuarantineDecision,
)

OperatorQuarantineAction = Literal["hold", "reject", "rescan"]


class QuarantineTransitionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class QuarantineDecisionOutcome:
    decision: SourceVersionQuarantineDecision
    replayed: bool


def record_malware_detection(
    session: Session,
    version: SourceVersion,
    *,
    threat_name: str | None,
) -> SourceVersionQuarantineDecision:
    if version.quarantine_status == QuarantineStatus.REJECTED:
        raise QuarantineTransitionError(
            "quarantine_rejected",
            "Permanently rejected content cannot be released by a scanner result",
        )
    return _append_transition(
        session,
        version,
        operation_key=f"system:scan-detected:{version.id}:{version.quarantine_version + 1}",
        action="scan_detected",
        resulting_status=QuarantineStatus.PENDING_REVIEW,
        reason="Malware scanner detection requires operator review",
        actor_type="system",
        actor_id="data-factory",
        details={"threat_name": threat_name} if threat_name else {},
    )


def record_clean_scan(
    session: Session,
    version: SourceVersion,
    *,
    scanner: str,
    signature_version: str,
) -> SourceVersionQuarantineDecision | None:
    if version.quarantine_status in {QuarantineStatus.NOT_APPLICABLE, QuarantineStatus.CLEARED}:
        return None
    if version.quarantine_status == QuarantineStatus.REJECTED:
        raise QuarantineTransitionError(
            "quarantine_rejected",
            "Permanently rejected content cannot be released by an unattended scan",
        )
    return _append_transition(
        session,
        version,
        operation_key=f"system:scan-clean:{version.id}:{version.quarantine_version + 1}",
        action="scan_clean",
        resulting_status=QuarantineStatus.CLEARED,
        reason="A complete malware rescan returned clean",
        actor_type="system",
        actor_id="data-factory",
        details={"scanner": scanner, "signature_version": signature_version[:240]},
    )


def record_rescan_failure(
    session: Session,
    version: SourceVersion,
    *,
    reason: str,
    actor_id: str,
) -> SourceVersionQuarantineDecision | None:
    if version.quarantine_status != QuarantineStatus.RESCAN_REQUESTED:
        return None
    rescan = session.scalar(
        select(SourceVersionQuarantineDecision)
        .where(
            SourceVersionQuarantineDecision.tenant_id == version.tenant_id,
            SourceVersionQuarantineDecision.source_version_id == version.id,
            SourceVersionQuarantineDecision.action == "rescan",
            SourceVersionQuarantineDecision.resulting_version == version.quarantine_version,
        )
        .order_by(SourceVersionQuarantineDecision.created_at.desc())
        .limit(1)
    )
    if rescan is None:
        raise QuarantineTransitionError(
            "quarantine_history_missing",
            "Rescan request does not have an immutable decision record",
        )
    return _append_transition(
        session,
        version,
        operation_key=f"system:rescan-failed:{rescan.id}",
        action="rescan_failed",
        resulting_status=rescan.previous_status,
        reason=reason[:500],
        actor_type="system",
        actor_id=actor_id,
        details={"rescan_decision_id": rescan.id},
    )


def apply_operator_decision(
    session: Session,
    version: SourceVersion,
    *,
    operation_key: str,
    expected_version: int,
    action: OperatorQuarantineAction,
    reason: str,
    actor_type: str,
    actor_id: str,
    workflow_id: str | None = None,
) -> QuarantineDecisionOutcome:
    existing = session.scalar(
        select(SourceVersionQuarantineDecision).where(
            SourceVersionQuarantineDecision.tenant_id == version.tenant_id,
            SourceVersionQuarantineDecision.operation_key == operation_key,
        )
    )
    if existing is not None:
        same_command = (
            existing.source_version_id == version.id
            and existing.action == action
            and existing.expected_version == expected_version
            and existing.reason == reason
            and existing.actor_type == actor_type
            and existing.actor_id == actor_id
        )
        if not same_command:
            raise QuarantineTransitionError(
                "operation_key_conflict",
                "Operation key was already used with different quarantine arguments",
            )
        return QuarantineDecisionOutcome(existing, True)
    if version.quarantine_version != expected_version:
        raise QuarantineTransitionError(
            "quarantine_version_conflict",
            "Quarantine case changed; refresh before applying a decision",
        )
    allowed: dict[OperatorQuarantineAction, set[QuarantineStatus]] = {
        "hold": {QuarantineStatus.PENDING_REVIEW},
        "reject": {QuarantineStatus.PENDING_REVIEW, QuarantineStatus.HELD},
        "rescan": {QuarantineStatus.PENDING_REVIEW, QuarantineStatus.HELD},
    }
    if version.quarantine_status not in allowed[action]:
        raise QuarantineTransitionError(
            "quarantine_action_not_allowed",
            f"Action {action} is not allowed from {version.quarantine_status.value}",
        )
    resulting_status = {
        "hold": QuarantineStatus.HELD,
        "reject": QuarantineStatus.REJECTED,
        "rescan": QuarantineStatus.RESCAN_REQUESTED,
    }[action]
    decision = _append_transition(
        session,
        version,
        operation_key=operation_key,
        action=action,
        resulting_status=resulting_status,
        reason=reason,
        actor_type=actor_type,
        actor_id=actor_id,
        workflow_id=workflow_id,
    )
    return QuarantineDecisionOutcome(decision, False)


def _append_transition(
    session: Session,
    version: SourceVersion,
    *,
    operation_key: str,
    action: str,
    resulting_status: QuarantineStatus,
    reason: str,
    actor_type: str,
    actor_id: str,
    workflow_id: str | None = None,
    details: dict[str, object] | None = None,
) -> SourceVersionQuarantineDecision:
    expected_version = version.quarantine_version
    resulting_version = expected_version + 1
    previous_status = version.quarantine_status
    now = datetime.now(UTC)
    decision = SourceVersionQuarantineDecision(
        tenant_id=version.tenant_id,
        source_version_id=version.id,
        operation_key=operation_key,
        action=action,
        expected_version=expected_version,
        resulting_version=resulting_version,
        previous_status=previous_status,
        resulting_status=resulting_status,
        reason=reason[:500],
        actor_type=actor_type,
        actor_id=actor_id,
        workflow_id=workflow_id,
        details=details or {},
        created_at=now,
    )
    version.quarantine_status = resulting_status
    version.quarantine_version = resulting_version
    version.quarantine_updated_at = now
    session.add(decision)
    return decision
