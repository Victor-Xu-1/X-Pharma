from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.commercial.operations import CommercialOperationsConflict, CommercialOperationsNotFound
from pharma_intel.commercial.service import CommercialAccessDenied
from pharma_intel.models import (
    AuditEvent,
    BillingAccount,
    BillingPeriodStatement,
    InvoiceReference,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
)
from pharma_intel.security import Principal

BILLING_CONSUMER_NAME = "billing-provider-v1"
BILLING_STATEMENT_EVENT_TYPE = "commercial.billing_statement_created.v1"
EXTERNAL_CUSTOMER_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,499}$")
BillingDeliveryFilter = Literal["all", "pending", "processing", "retry", "succeeded", "dead"]
_BILLING_DELIVERY_STATES = frozenset({"all", "pending", "processing", "retry", "succeeded", "dead"})


class BillingOperationsService:
    def __init__(self, session: Session, principal: Principal) -> None:
        if principal.actor_type != "user":
            raise CommercialAccessDenied("Human workspace account required")
        self.session = session
        self.principal = principal

    def list_accounts(self, *, limit: int = 200) -> list[dict[str, Any]]:
        self.principal.require("commercial:read")
        if not 1 <= limit <= 500:
            raise ValueError("Billing-account list limit must be between 1 and 500")
        statistics = (
            select(
                BillingPeriodStatement.billing_account_id.label("account_id"),
                func.count(func.distinct(BillingPeriodStatement.id)).label("statement_count"),
                func.count(func.distinct(InvoiceReference.id)).label("invoice_count"),
                func.count(func.distinct(BillingPeriodStatement.id))
                .filter(InvoiceReference.id.is_(None))
                .label("unresolved_statement_count"),
            )
            .outerjoin(InvoiceReference, InvoiceReference.statement_id == BillingPeriodStatement.id)
            .where(BillingPeriodStatement.tenant_id == self.principal.tenant_id)
            .group_by(BillingPeriodStatement.billing_account_id)
            .subquery()
        )
        rows = self.session.execute(
            select(
                BillingAccount,
                func.coalesce(statistics.c.statement_count, 0),
                func.coalesce(statistics.c.unresolved_statement_count, 0),
                func.coalesce(statistics.c.invoice_count, 0),
            )
            .outerjoin(statistics, statistics.c.account_id == BillingAccount.id)
            .where(BillingAccount.tenant_id == self.principal.tenant_id)
            .order_by(BillingAccount.display_name, BillingAccount.id)
            .limit(limit)
        )
        return [
            self._account_view(
                account,
                statement_count=int(statement_count),
                unresolved_statement_count=int(unresolved_count),
                invoice_count=int(invoice_count),
            )
            for account, statement_count, unresolved_count, invoice_count in rows
        ]

    def set_customer_mapping(
        self,
        account_id: str,
        *,
        external_customer_reference: str,
        reason: str,
        request_id: str,
    ) -> dict[str, Any]:
        self.principal.require("commercial:write")
        normalized_reference = external_customer_reference.strip()
        normalized_reason = reason.strip()
        normalized_request_id = request_id.strip()
        if EXTERNAL_CUSTOMER_REFERENCE_PATTERN.fullmatch(normalized_reference) is None:
            raise ValueError("External customer reference is invalid")
        if not 3 <= len(normalized_reason) <= 500:
            raise ValueError("A mapping change reason between 3 and 500 characters is required")
        if not 1 <= len(normalized_request_id) <= 100:
            raise ValueError("A request ID between 1 and 100 characters is required")
        account = self.session.scalar(
            select(BillingAccount)
            .where(
                BillingAccount.tenant_id == self.principal.tenant_id,
                BillingAccount.id == account_id,
            )
            .with_for_update()
        )
        if account is None:
            raise CommercialOperationsNotFound("Billing account does not exist")
        current_reference = account.external_customer_reference
        if current_reference == normalized_reference:
            return self._account_view(account)
        if current_reference is not None and self._unresolved_statement_count(account.id) > 0:
            raise CommercialOperationsConflict(
                "Customer mapping cannot change while billing statements are awaiting an invoice"
            )
        account.external_customer_reference = normalized_reference
        previous_sha256 = _reference_sha256(current_reference) if current_reference else None
        next_sha256 = _reference_sha256(normalized_reference)
        self.session.add_all(
            [
                AuditEvent(
                    tenant_id=self.principal.tenant_id,
                    actor_type=self.principal.actor_type,
                    actor_id=self.principal.actor_id,
                    action="commercial.billing_customer_mapping.update",
                    resource_type="billing_account",
                    resource_id=account.id,
                    outcome="success",
                    request_id=normalized_request_id,
                    details={
                        "reason": normalized_reason,
                        "previous_reference_sha256": previous_sha256,
                        "reference_sha256": next_sha256,
                    },
                ),
                OutboxEvent(
                    tenant_id=self.principal.tenant_id,
                    aggregate_type="billing_account",
                    aggregate_id=account.id,
                    event_type="commercial.billing_customer_mapping_updated.v1",
                    payload={
                        "account_key": account.account_key,
                        "previous_reference_sha256": previous_sha256,
                        "reference_sha256": next_sha256,
                    },
                ),
            ]
        )
        self.session.commit()
        return self._account_view(account)

    def list_deliveries(
        self,
        *,
        state: BillingDeliveryFilter = "all",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        self.principal.require("commercial:read")
        if not 1 <= limit <= 500:
            raise ValueError("Billing-delivery list limit must be between 1 and 500")
        if state not in _BILLING_DELIVERY_STATES:
            raise ValueError("Billing-delivery state is invalid")
        statement = (
            select(
                OutboxEvent,
                BillingPeriodStatement,
                BillingAccount,
                ProjectionDelivery,
                InvoiceReference,
            )
            .join(
                BillingPeriodStatement,
                BillingPeriodStatement.id == OutboxEvent.aggregate_id,
            )
            .join(BillingAccount, BillingAccount.id == BillingPeriodStatement.billing_account_id)
            .outerjoin(
                ProjectionDelivery,
                (ProjectionDelivery.outbox_event_id == OutboxEvent.id)
                & (ProjectionDelivery.consumer_name == BILLING_CONSUMER_NAME),
            )
            .outerjoin(InvoiceReference, InvoiceReference.statement_id == BillingPeriodStatement.id)
            .where(
                OutboxEvent.tenant_id == self.principal.tenant_id,
                OutboxEvent.event_type == BILLING_STATEMENT_EVENT_TYPE,
            )
            .order_by(OutboxEvent.created_at.desc(), OutboxEvent.id.desc())
            .limit(limit)
        )
        if state == "pending":
            statement = statement.where(ProjectionDelivery.id.is_(None))
        elif state != "all":
            statement = statement.where(ProjectionDelivery.state == ProjectionDeliveryState(state))
        return [
            self._delivery_view(event, period, account, delivery, invoice)
            for event, period, account, delivery, invoice in self.session.execute(statement)
        ]

    def replay_delivery(self, delivery_id: str, *, reason: str, request_id: str) -> dict[str, Any]:
        self.principal.require("commercial:write")
        normalized_reason = reason.strip()
        normalized_request_id = request_id.strip()
        if not 3 <= len(normalized_reason) <= 500:
            raise ValueError("A replay reason between 3 and 500 characters is required")
        if not 1 <= len(normalized_request_id) <= 100:
            raise ValueError("A request ID between 1 and 100 characters is required")
        delivery = self.session.scalar(
            select(ProjectionDelivery)
            .where(
                ProjectionDelivery.tenant_id == self.principal.tenant_id,
                ProjectionDelivery.id == delivery_id,
                ProjectionDelivery.consumer_name == BILLING_CONSUMER_NAME,
            )
            .with_for_update()
        )
        if delivery is None:
            raise CommercialOperationsNotFound("Billing delivery does not exist")
        if delivery.state != ProjectionDeliveryState.DEAD:
            raise CommercialOperationsConflict("Only dead billing deliveries can be replayed")
        requeue_billing_delivery(
            self.session,
            delivery,
            actor_type=self.principal.actor_type,
            actor_id=self.principal.actor_id,
            reason=normalized_reason,
            request_id=normalized_request_id,
        )
        self.session.commit()
        event = self.session.get(OutboxEvent, delivery.outbox_event_id)
        if event is None:
            raise CommercialOperationsNotFound("Billing delivery event is unavailable")
        period = self.session.get(BillingPeriodStatement, event.aggregate_id)
        if period is None:
            raise CommercialOperationsNotFound("Billing statement is unavailable")
        account = self.session.get(BillingAccount, period.billing_account_id)
        if account is None:
            raise CommercialOperationsNotFound("Billing account is unavailable")
        invoice = self.session.scalar(select(InvoiceReference).where(InvoiceReference.statement_id == period.id))
        return self._delivery_view(event, period, account, delivery, invoice)

    def _account_view(
        self,
        account: BillingAccount,
        *,
        statement_count: int | None = None,
        unresolved_statement_count: int | None = None,
        invoice_count: int | None = None,
    ) -> dict[str, Any]:
        resolved_statement_count = statement_count
        if resolved_statement_count is None:
            resolved_statement_count = int(
                self.session.scalar(
                    select(func.count())
                    .select_from(BillingPeriodStatement)
                    .where(
                        BillingPeriodStatement.tenant_id == self.principal.tenant_id,
                        BillingPeriodStatement.billing_account_id == account.id,
                    )
                )
                or 0
            )
        resolved_invoice_count = invoice_count
        if resolved_invoice_count is None:
            resolved_invoice_count = int(
                self.session.scalar(
                    select(func.count())
                    .select_from(InvoiceReference)
                    .where(
                        InvoiceReference.tenant_id == self.principal.tenant_id,
                        InvoiceReference.billing_account_id == account.id,
                    )
                )
                or 0
            )
        resolved_unresolved_count = unresolved_statement_count
        if resolved_unresolved_count is None:
            resolved_unresolved_count = self._unresolved_statement_count(account.id)
        return {
            "id": account.id,
            "account_key": account.account_key,
            "display_name": account.display_name,
            "currency": account.currency,
            "status": account.status.value,
            "mapping_configured": account.external_customer_reference is not None,
            "external_customer_reference_masked": _masked_reference(account.external_customer_reference),
            "statement_count": resolved_statement_count,
            "unresolved_statement_count": resolved_unresolved_count,
            "invoice_count": resolved_invoice_count,
            "updated_at": account.updated_at,
        }

    def _unresolved_statement_count(self, account_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(BillingPeriodStatement)
                .outerjoin(InvoiceReference, InvoiceReference.statement_id == BillingPeriodStatement.id)
                .where(
                    BillingPeriodStatement.tenant_id == self.principal.tenant_id,
                    BillingPeriodStatement.billing_account_id == account_id,
                    InvoiceReference.id.is_(None),
                )
            )
            or 0
        )

    @staticmethod
    def _delivery_view(
        event: OutboxEvent,
        statement: BillingPeriodStatement,
        account: BillingAccount,
        delivery: ProjectionDelivery | None,
        invoice: InvoiceReference | None,
    ) -> dict[str, Any]:
        return {
            "delivery_id": delivery.id if delivery else None,
            "event_id": event.id,
            "statement_id": statement.id,
            "statement_key": statement.statement_key,
            "billing_account_id": account.id,
            "billing_account_key": account.account_key,
            "billing_account_name": account.display_name,
            "state": delivery.state.value if delivery else "pending",
            "attempts": delivery.attempts if delivery else 0,
            "available_at": delivery.available_at if delivery else event.available_at,
            "lease_expires_at": delivery.lease_expires_at if delivery else None,
            "processed_at": delivery.processed_at if delivery else None,
            "last_error": delivery.last_error if delivery else None,
            "invoice_provider": invoice.provider if invoice else None,
            "external_invoice_id": invoice.external_invoice_id if invoice else None,
            "invoice_status": invoice.status if invoice else None,
            "created_at": event.created_at,
        }


def requeue_billing_delivery(
    session: Session,
    delivery: ProjectionDelivery,
    *,
    actor_type: str,
    actor_id: str,
    reason: str,
    request_id: str,
) -> None:
    previous_error_sha256 = (
        hashlib.sha256(delivery.last_error.encode("utf-8")).hexdigest() if delivery.last_error else None
    )
    delivery.state = ProjectionDeliveryState.RETRY
    delivery.available_at = datetime.now(UTC)
    delivery.lease_expires_at = None
    delivery.worker_id = None
    delivery.last_error = f"operator replay requested: {reason}"[:4000]
    session.add_all(
        [
            AuditEvent(
                tenant_id=delivery.tenant_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action="commercial.billing_delivery.replay",
                resource_type="projection_delivery",
                resource_id=delivery.id,
                outcome="success",
                request_id=request_id[:100],
                details={
                    "consumer_name": BILLING_CONSUMER_NAME,
                    "reason": reason,
                    "previous_error_sha256": previous_error_sha256,
                },
            ),
            OutboxEvent(
                tenant_id=delivery.tenant_id,
                aggregate_type="billing_provider_delivery",
                aggregate_id=delivery.id,
                event_type="commercial.billing_delivery_replayed.v1",
                payload={"reason": reason, "previous_error_sha256": previous_error_sha256},
            ),
        ]
    )


def _reference_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _masked_reference(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= 4:
        return "****"
    visible = value[-4:]
    return f"{'*' * min(max(len(value) - len(visible), 4), 12)}{visible}"
