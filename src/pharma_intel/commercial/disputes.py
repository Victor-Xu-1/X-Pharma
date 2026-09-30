from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.commercial.accounting import CommercialAccountingService, UsageAdjustmentCommand
from pharma_intel.commercial.service import CommercialAccessDenied, CommercialError
from pharma_intel.models import (
    AuditEvent,
    BillingAccount,
    BillingDispute,
    BillingDisputeEvent,
    BillingPeriodStatement,
    CommercialSubscription,
    InvoiceReference,
    OutboxEvent,
    Tenant,
)
from pharma_intel.security import Principal

DisputeStatus = Literal["all", "open", "investigating", "resolved", "rejected", "cancelled"]
DisputeAction = Literal["investigate", "resolve_credit", "resolve_no_credit", "reject", "cancel"]
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,119}$")
UNIT_QUANTUM = Decimal("0.00000001")
TERMINAL_STATUSES = frozenset({"resolved", "rejected", "cancelled"})


class BillingDisputeNotFound(CommercialError):
    pass


class BillingDisputeConflict(CommercialError):
    pass


@dataclass(frozen=True)
class CreateBillingDisputeCommand:
    dispute_key: str
    statement_id: str
    invoice_reference_id: str | None
    category: str
    disputed_units: Decimal | str
    subject: str
    description: str


@dataclass(frozen=True)
class TransitionBillingDisputeCommand:
    operation_key: str
    expected_version: int
    action: DisputeAction
    notes: str
    assigned_to: str | None = None
    adjustment_key: str | None = None
    credit_units: Decimal | str | None = None


class BillingDisputeService:
    def __init__(self, session: Session, principal: Principal, *, sla_hours: int = 120) -> None:
        if principal.actor_type != "user":
            raise CommercialAccessDenied("Human workspace account required")
        if not 1 <= sla_hours <= 720:
            raise ValueError("Billing dispute SLA must be between 1 and 720 hours")
        self.session = session
        self.principal = principal
        self.sla_hours = sla_hours

    def create(
        self,
        command: CreateBillingDisputeCommand,
        *,
        request_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.principal.require("commercial:write")
        dispute_key = _key(command.dispute_key, "Dispute key")
        category = command.category.strip().lower()
        if category not in {"usage", "pricing", "duplicate", "authorization", "service", "other"}:
            raise ValueError("Billing dispute category is invalid")
        disputed_units = _positive_units(command.disputed_units, "Disputed units")
        subject = _text(command.subject, "Dispute subject", 3, 200)
        description = _text(command.description, "Dispute description", 3, 4000)
        request_id = _text(request_id, "Request ID", 1, 100)
        existing = self.session.scalar(
            select(BillingDispute).where(
                BillingDispute.tenant_id == self.principal.tenant_id,
                BillingDispute.dispute_key == dispute_key,
            )
        )
        if existing is not None:
            if not self._same_create(existing, command, category, disputed_units, subject, description):
                raise BillingDisputeConflict("Dispute key already exists with different values")
            return self._view(existing, now=now)

        statement = self.session.scalar(
            select(BillingPeriodStatement).where(
                BillingPeriodStatement.tenant_id == self.principal.tenant_id,
                BillingPeriodStatement.id == command.statement_id,
            )
        )
        if statement is None:
            raise BillingDisputeNotFound("Billing statement does not exist")
        if disputed_units > max(statement.net_consumed_units, Decimal("0")):
            raise ValueError("Disputed units cannot exceed the billing statement net units")
        invoice: InvoiceReference | None = None
        if command.invoice_reference_id:
            invoice = self.session.scalar(
                select(InvoiceReference).where(
                    InvoiceReference.tenant_id == self.principal.tenant_id,
                    InvoiceReference.id == command.invoice_reference_id,
                    InvoiceReference.statement_id == statement.id,
                )
            )
            if invoice is None:
                raise BillingDisputeNotFound("Invoice reference does not belong to the billing statement")
        else:
            invoice = self.session.scalar(
                select(InvoiceReference).where(
                    InvoiceReference.tenant_id == self.principal.tenant_id,
                    InvoiceReference.statement_id == statement.id,
                )
            )
        opened_at = _utc(now)
        dispute = BillingDispute(
            tenant_id=self.principal.tenant_id,
            dispute_key=dispute_key,
            billing_account_id=statement.billing_account_id,
            subscription_id=statement.subscription_id,
            statement_id=statement.id,
            invoice_reference_id=invoice.id if invoice else None,
            status="open",
            category=category,
            disputed_units=disputed_units,
            subject=subject,
            description=description,
            opened_by=self.principal.actor_id,
            opened_at=opened_at,
            due_at=opened_at + timedelta(hours=self.sla_hours),
            resolution_notes="",
            version=1,
        )
        self.session.add(dispute)
        self.session.flush()
        self._record_event(
            dispute,
            event_type="opened",
            from_status=None,
            operation_key=dispute_key,
            request_id=request_id,
            note=description,
            payload={"category": category, "disputed_units": _unit_string(disputed_units)},
            now=opened_at,
        )
        self._audit_and_publish(dispute, "opened", request_id, {"category": category})
        self.session.commit()
        return self._view(dispute, now=opened_at)

    def list(
        self, *, status: DisputeStatus = "all", limit: int = 200, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        self.principal.require("commercial:read")
        if status not in {"all", "open", "investigating", "resolved", "rejected", "cancelled"}:
            raise ValueError("Billing dispute status is invalid")
        if not 1 <= limit <= 500:
            raise ValueError("Billing dispute list limit must be between 1 and 500")
        query = select(BillingDispute).where(BillingDispute.tenant_id == self.principal.tenant_id)
        if status != "all":
            query = query.where(BillingDispute.status == status)
        disputes = self.session.scalars(query.order_by(BillingDispute.opened_at.desc()).limit(limit)).all()
        return [self._view(item, now=now) for item in disputes]

    def transition(
        self,
        dispute_id: str,
        command: TransitionBillingDisputeCommand,
        *,
        request_id: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.principal.require("commercial:write")
        operation_key = _key(command.operation_key, "Operation key")
        request_id = _text(request_id, "Request ID", 1, 100)
        notes = _text(command.notes, "Transition notes", 3, 4000)
        command_sha256 = _transition_sha256(command, notes)
        existing_event = self.session.scalar(
            select(BillingDisputeEvent).where(
                BillingDisputeEvent.tenant_id == self.principal.tenant_id,
                BillingDisputeEvent.dispute_id == dispute_id,
                BillingDisputeEvent.operation_key == operation_key,
            )
        )
        if existing_event is not None:
            if existing_event.payload_json.get("command_sha256") != command_sha256:
                raise BillingDisputeConflict("Operation key already exists for another transition")
            dispute = self._get(dispute_id, lock=False)
            return self._view(dispute, now=now)

        dispute = self._get(dispute_id, lock=True)
        if dispute.version != command.expected_version:
            raise BillingDisputeConflict("Billing dispute version is stale; reload before retrying")
        if dispute.status in TERMINAL_STATUSES:
            raise BillingDisputeConflict("Terminal billing disputes cannot be changed")
        occurred_at = _utc(now)
        from_status = dispute.status
        target_status, resolution_code = self._validate_transition(dispute, command)
        assigned_to = command.assigned_to.strip() if command.assigned_to else None
        if assigned_to is not None and not 1 <= len(assigned_to) <= 500:
            raise ValueError("Dispute assignee is invalid")
        if command.action == "investigate":
            dispute.assigned_to = assigned_to or self.principal.actor_id
        elif assigned_to is not None:
            dispute.assigned_to = assigned_to
        dispute.status = target_status
        dispute.version += 1
        adjustment_key: str | None = None
        credit_units: Decimal | None = None
        if target_status in TERMINAL_STATUSES:
            dispute.resolution_code = resolution_code
            dispute.resolution_notes = notes
            dispute.resolved_by = self.principal.actor_id
            dispute.resolved_at = occurred_at
        if command.action == "resolve_credit":
            adjustment_key = _key(command.adjustment_key or "", "Adjustment key", max_length=199)
            credit_units = _positive_units(command.credit_units, "Credit units")
            if credit_units > dispute.disputed_units:
                raise ValueError("Credit units cannot exceed disputed units")
            dispute.resolution_adjustment_key = adjustment_key

        payload: dict[str, Any] = {
            "action": command.action,
            "expected_version": command.expected_version,
            "command_sha256": command_sha256,
        }
        if credit_units is not None:
            payload.update({"adjustment_key": adjustment_key, "credit_units": _unit_string(credit_units)})
        self._record_event(
            dispute,
            event_type=target_status,
            from_status=from_status,
            operation_key=operation_key,
            request_id=request_id,
            note=notes,
            payload=payload,
            now=occurred_at,
        )
        self._audit_and_publish(dispute, target_status, request_id, payload)
        if credit_units is None:
            self.session.commit()
        else:
            tenant = self.session.get(Tenant, self.principal.tenant_id)
            subscription = self.session.get(CommercialSubscription, dispute.subscription_id)
            if tenant is None or subscription is None:
                self.session.rollback()
                raise BillingDisputeConflict("Billing contract is unavailable")
            try:
                CommercialAccountingService(
                    self.session,
                    tenant,
                    actor_id=self.principal.actor_id,
                ).adjust_usage(
                    UsageAdjustmentCommand(
                        subscription_key=subscription.subscription_key,
                        adjustment_key=adjustment_key or "",
                        units_delta=-credit_units,
                        reason=f"Billing dispute {dispute.dispute_key}: {notes}",
                        request_id=request_id,
                        metadata={
                            "billing_dispute_id": dispute.id,
                            "billing_dispute_key": dispute.dispute_key,
                            "billing_statement_id": dispute.statement_id,
                        },
                    )
                )
            except Exception:
                self.session.rollback()
                raise
        return self._view(dispute, now=occurred_at)

    def _get(self, dispute_id: str, *, lock: bool) -> BillingDispute:
        query = select(BillingDispute).where(
            BillingDispute.tenant_id == self.principal.tenant_id,
            BillingDispute.id == dispute_id,
        )
        if lock:
            query = query.with_for_update()
        dispute = self.session.scalar(query)
        if dispute is None:
            raise BillingDisputeNotFound("Billing dispute does not exist")
        return dispute

    @staticmethod
    def _validate_transition(
        dispute: BillingDispute, command: TransitionBillingDisputeCommand
    ) -> tuple[str, str | None]:
        if command.action == "investigate" and dispute.status == "open":
            return "investigating", None
        if command.action == "cancel" and dispute.status in {"open", "investigating"}:
            return "cancelled", "cancelled"
        if dispute.status != "investigating":
            raise BillingDisputeConflict("Dispute must be investigating before a financial decision")
        if command.action == "resolve_credit":
            return "resolved", "credit"
        if command.action == "resolve_no_credit":
            return "resolved", "no_credit"
        if command.action == "reject":
            return "rejected", "rejected"
        raise BillingDisputeConflict("Billing dispute transition is not allowed")

    def _record_event(
        self,
        dispute: BillingDispute,
        *,
        event_type: str,
        from_status: str | None,
        operation_key: str,
        request_id: str,
        note: str,
        payload: dict[str, Any],
        now: datetime,
    ) -> None:
        self.session.add(
            BillingDisputeEvent(
                tenant_id=self.principal.tenant_id,
                dispute_id=dispute.id,
                event_type=event_type,
                from_status=from_status,
                to_status=dispute.status,
                actor_id=self.principal.actor_id,
                operation_key=operation_key,
                request_id=request_id,
                note=note,
                payload_json=payload,
                occurred_at=now,
            )
        )

    def _audit_and_publish(
        self, dispute: BillingDispute, event_type: str, request_id: str, details: dict[str, Any]
    ) -> None:
        safe_details = {"status": dispute.status, "version": dispute.version, **details}
        self.session.add_all(
            [
                AuditEvent(
                    tenant_id=self.principal.tenant_id,
                    actor_type=self.principal.actor_type,
                    actor_id=self.principal.actor_id,
                    action=f"commercial.billing_dispute.{event_type}",
                    resource_type="billing_dispute",
                    resource_id=dispute.id,
                    outcome="success",
                    request_id=request_id,
                    details=safe_details,
                ),
                OutboxEvent(
                    tenant_id=self.principal.tenant_id,
                    aggregate_type="billing_dispute",
                    aggregate_id=dispute.id,
                    event_type=f"commercial.billing_dispute_{event_type}.v1",
                    payload=safe_details,
                ),
            ]
        )

    def _view(self, dispute: BillingDispute, *, now: datetime | None = None) -> dict[str, Any]:
        account = self.session.get(BillingAccount, dispute.billing_account_id)
        statement = self.session.get(BillingPeriodStatement, dispute.statement_id)
        invoice = (
            self.session.get(InvoiceReference, dispute.invoice_reference_id) if dispute.invoice_reference_id else None
        )
        current = _utc(now)
        due_at = _utc(dispute.due_at)
        return {
            "id": dispute.id,
            "dispute_key": dispute.dispute_key,
            "billing_account_id": dispute.billing_account_id,
            "billing_account_key": account.account_key if account else "",
            "billing_account_name": account.display_name if account else "",
            "subscription_id": dispute.subscription_id,
            "statement_id": dispute.statement_id,
            "statement_key": statement.statement_key if statement else "",
            "invoice_reference_id": dispute.invoice_reference_id,
            "external_invoice_id": invoice.external_invoice_id if invoice else None,
            "status": dispute.status,
            "category": dispute.category,
            "disputed_units": _unit_string(dispute.disputed_units),
            "subject": dispute.subject,
            "description": dispute.description,
            "opened_by": dispute.opened_by,
            "opened_at": dispute.opened_at,
            "assigned_to": dispute.assigned_to,
            "due_at": dispute.due_at,
            "overdue": dispute.status not in TERMINAL_STATUSES and due_at < current,
            "resolution_code": dispute.resolution_code,
            "resolution_notes": dispute.resolution_notes,
            "resolved_by": dispute.resolved_by,
            "resolved_at": dispute.resolved_at,
            "resolution_adjustment_key": dispute.resolution_adjustment_key,
            "version": dispute.version,
            "created_at": dispute.created_at,
            "updated_at": dispute.updated_at,
        }

    @staticmethod
    def _same_create(
        existing: BillingDispute,
        command: CreateBillingDisputeCommand,
        category: str,
        disputed_units: Decimal,
        subject: str,
        description: str,
    ) -> bool:
        return (
            existing.statement_id == command.statement_id
            and (command.invoice_reference_id is None or existing.invoice_reference_id == command.invoice_reference_id)
            and existing.category == category
            and existing.disputed_units == disputed_units
            and existing.subject == subject
            and existing.description == description
        )


def _key(value: str, label: str, *, max_length: int = 119) -> str:
    normalized = value.strip()
    if len(normalized) > max_length or KEY_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{label} is invalid")
    return normalized


def _text(value: str, label: str, minimum: int, maximum: int) -> str:
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"{label} must contain {minimum}-{maximum} characters")
    return normalized


def _positive_units(value: Decimal | str | None, label: str) -> Decimal:
    try:
        units = Decimal(str(value)).quantize(UNIT_QUANTUM, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{label} is invalid") from exc
    if not units.is_finite() or units <= 0:
        raise ValueError(f"{label} must be greater than zero")
    return units


def _unit_string(value: Decimal) -> str:
    return format(value.quantize(UNIT_QUANTUM), "f")


def _utc(value: datetime | None) -> datetime:
    resolved = value or datetime.now(UTC)
    return resolved.replace(tzinfo=UTC) if resolved.tzinfo is None else resolved.astimezone(UTC)


def _transition_sha256(command: TransitionBillingDisputeCommand, notes: str) -> str:
    credit_units = None
    if command.credit_units is not None:
        try:
            credit_units = _unit_string(Decimal(str(command.credit_units)))
        except InvalidOperation:
            credit_units = str(command.credit_units)
    payload = {
        "action": command.action,
        "expected_version": command.expected_version,
        "notes": notes,
        "assigned_to": command.assigned_to.strip() if command.assigned_to else None,
        "adjustment_key": command.adjustment_key.strip() if command.adjustment_key else None,
        "credit_units": credit_units,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
