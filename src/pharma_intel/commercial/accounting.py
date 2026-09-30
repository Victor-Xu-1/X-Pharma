from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.commercial.billing import (
    BillingProviderReceipt,
    BillingStatementSigner,
    SignedBillingManifest,
    validate_billing_provider_receipt,
)
from pharma_intel.commercial.service import CommercialError, CommercialInvariantViolation
from pharma_intel.models import (
    AuditEvent,
    BillingAccount,
    BillingAdjustment,
    BillingPeriodStatement,
    CommercialLedgerEntry,
    CommercialLedgerEventType,
    CommercialReconciliationRun,
    CommercialSubscription,
    CreditGrant,
    InvoiceReference,
    OutboxEvent,
    Tenant,
    UsageEvent,
    UsageReservation,
    UsageReservationState,
    UsageSettlement,
)

UNIT_QUANTUM = Decimal("0.00000001")
ZERO_UNITS = Decimal("0.00000000")
KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,199}$")


class CommercialAccountingConflict(CommercialError):
    pass


class CommercialBalanceViolation(CommercialError):
    pass


@dataclass(frozen=True)
class UsageAdjustmentCommand:
    subscription_key: str
    adjustment_key: str
    units_delta: Decimal | str
    reason: str
    request_id: str
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReversalCommand:
    adjustment_key: str
    reason: str
    request_id: str


@dataclass(frozen=True)
class ExpirationOutcome:
    expired_reservations: int
    released_units: Decimal
    completed_at: datetime


@dataclass(frozen=True)
class BillingStatementCommand:
    subscription_key: str
    statement_key: str
    period_start: datetime
    period_end: datetime
    revision: int
    request_id: str


class CommercialAccountingService:
    def __init__(
        self,
        session: Session,
        tenant: Tenant,
        *,
        actor_id: str,
        statement_signer: BillingStatementSigner | None = None,
    ) -> None:
        if not actor_id or len(actor_id) > 500:
            raise ValueError("Accounting actor identity is invalid")
        self.session = session
        self.tenant = tenant
        self.actor_id = actor_id
        self.statement_signer = statement_signer

    def adjust_usage(self, command: UsageAdjustmentCommand) -> BillingAdjustment:
        return self._apply_adjustment(
            subscription_key=command.subscription_key,
            adjustment_key=command.adjustment_key,
            adjustment_kind="usage_adjustment",
            units_delta=_delta(command.units_delta),
            reason=command.reason,
            request_id=command.request_id,
            metadata=command.metadata or {},
        )

    def reverse_settlement(self, settlement_id: str, command: ReversalCommand) -> BillingAdjustment:
        settlement = self.session.scalar(
            select(UsageSettlement).where(
                UsageSettlement.tenant_id == self.tenant.id,
                UsageSettlement.id == settlement_id,
            )
        )
        if settlement is None:
            raise ValueError("Usage settlement does not exist")
        subscription = self._subscription_by_id(settlement.subscription_id, lock=True)
        settlement = self.session.scalar(
            select(UsageSettlement).where(
                UsageSettlement.tenant_id == self.tenant.id,
                UsageSettlement.id == settlement_id,
            )
        )
        if settlement is None:
            raise CommercialInvariantViolation("Usage settlement disappeared while locked")
        return self._apply_adjustment_locked(
            subscription,
            adjustment_key=command.adjustment_key,
            adjustment_kind="settlement_reversal",
            units_delta=-_quantize(settlement.charged_units),
            reason=command.reason,
            request_id=command.request_id,
            metadata={"settlement_key": settlement.settlement_key},
            reverses_settlement_id=settlement.id,
        )

    def reverse_adjustment(self, adjustment_id: str, command: ReversalCommand) -> BillingAdjustment:
        original = self.session.scalar(
            select(BillingAdjustment).where(
                BillingAdjustment.tenant_id == self.tenant.id,
                BillingAdjustment.id == adjustment_id,
            )
        )
        if original is None:
            raise ValueError("Billing adjustment does not exist")
        subscription = self._subscription_by_id(original.subscription_id, lock=True)
        original = self.session.scalar(
            select(BillingAdjustment).where(
                BillingAdjustment.tenant_id == self.tenant.id,
                BillingAdjustment.id == adjustment_id,
            )
        )
        if original is None:
            raise CommercialInvariantViolation("Billing adjustment disappeared while locked")
        return self._apply_adjustment_locked(
            subscription,
            adjustment_key=command.adjustment_key,
            adjustment_kind="adjustment_reversal",
            units_delta=-_quantize(original.units_delta),
            reason=command.reason,
            request_id=command.request_id,
            metadata={"original_adjustment_key": original.adjustment_key},
            reverses_adjustment_id=original.id,
        )

    def expire_stale_reservations(
        self,
        *,
        request_id: str,
        now: datetime | None = None,
        limit: int = 1000,
    ) -> ExpirationOutcome:
        _validate_request_id(request_id)
        if limit <= 0 or limit > 10_000:
            raise ValueError("Expiration batch limit must be between 1 and 10000")
        timestamp = _timestamp(now)
        subscription_ids = list(
            self.session.scalars(
                select(UsageReservation.subscription_id)
                .where(
                    UsageReservation.tenant_id == self.tenant.id,
                    UsageReservation.state == UsageReservationState.RESERVED,
                    UsageReservation.lease_expires_at <= timestamp,
                )
                .distinct()
                .order_by(UsageReservation.subscription_id)
            ).all()
        )
        expired = 0
        released = ZERO_UNITS
        for subscription_id in subscription_ids:
            if expired >= limit:
                break
            subscription = self._subscription_by_id(subscription_id, lock=True)
            remaining = limit - expired
            reservations = list(
                self.session.scalars(
                    select(UsageReservation)
                    .where(
                        UsageReservation.tenant_id == self.tenant.id,
                        UsageReservation.subscription_id == subscription.id,
                        UsageReservation.state == UsageReservationState.RESERVED,
                        UsageReservation.lease_expires_at <= timestamp,
                    )
                    .order_by(UsageReservation.lease_expires_at, UsageReservation.id)
                    .limit(remaining)
                    .with_for_update(skip_locked=True)
                ).all()
            )
            for reservation in reservations:
                next_reserved = _quantize(subscription.reserved_units - reservation.reserved_units)
                if next_reserved < ZERO_UNITS:
                    raise CommercialInvariantViolation(
                        "Reservation expiry would make the subscription reserved balance negative"
                    )
                subscription.reserved_units = next_reserved
                subscription.row_version += 1
                reservation.state = UsageReservationState.EXPIRED
                reservation.released_at = timestamp
                reservation.release_reason = "reservation lease expired during accounting sweep"
                self._ledger(
                    subscription,
                    event_key=f"expire:{reservation.id}",
                    event_type=CommercialLedgerEventType.RESERVATION_EXPIRED,
                    request_id=request_id,
                    reservation_id=reservation.id,
                    reserved_delta=-reservation.reserved_units,
                    details={"lease_expires_at": _iso(reservation.lease_expires_at)},
                )
                self._outbox(
                    reservation.id,
                    "commercial.reservation_expired.v1",
                    {
                        "subscription_id": subscription.id,
                        "released_units": _unit_string(reservation.reserved_units),
                    },
                )
                expired += 1
                released = _quantize(released + reservation.reserved_units)
        if expired:
            self._audit(
                "commercial.reservation.expire_batch",
                "usage_reservation",
                None,
                request_id,
                {"expired_reservations": expired, "released_units": _unit_string(released)},
            )
        self.session.commit()
        return ExpirationOutcome(expired, released, timestamp)

    def reconcile(
        self,
        subscription_key: str,
        *,
        run_key: str,
        request_id: str,
        now: datetime | None = None,
    ) -> CommercialReconciliationRun:
        _validate_key(run_key, "Reconciliation run key")
        _validate_request_id(request_id)
        started_at = _timestamp(now)
        subscription = self._subscription(subscription_key, lock=True)
        existing = self.session.scalar(
            select(CommercialReconciliationRun).where(
                CommercialReconciliationRun.tenant_id == self.tenant.id,
                CommercialReconciliationRun.run_key == run_key,
            )
        )
        if existing is not None:
            if existing.subscription_id != subscription.id:
                raise CommercialAccountingConflict("Reconciliation run key already belongs to another subscription")
            return existing

        ledger_granted, ledger_reserved, ledger_consumed = self._ledger_totals(subscription.id)
        source_granted = self._sum(
            select(func.sum(CreditGrant.granted_units)).where(
                CreditGrant.tenant_id == self.tenant.id,
                CreditGrant.subscription_id == subscription.id,
            )
        )
        source_reserved = self._sum(
            select(func.sum(UsageReservation.reserved_units)).where(
                UsageReservation.tenant_id == self.tenant.id,
                UsageReservation.subscription_id == subscription.id,
                UsageReservation.state == UsageReservationState.RESERVED,
            )
        )
        settlement_units = self._sum(
            select(func.sum(UsageSettlement.charged_units)).where(
                UsageSettlement.tenant_id == self.tenant.id,
                UsageSettlement.subscription_id == subscription.id,
            )
        )
        adjustment_units = self._sum(
            select(func.sum(BillingAdjustment.units_delta)).where(
                BillingAdjustment.tenant_id == self.tenant.id,
                BillingAdjustment.subscription_id == subscription.id,
            )
        )
        source_consumed = _quantize(settlement_units + adjustment_units)

        issues: list[dict[str, Any]] = []
        _compare_balance(issues, "snapshot_granted_vs_ledger", subscription.granted_units, ledger_granted)
        _compare_balance(issues, "snapshot_reserved_vs_ledger", subscription.reserved_units, ledger_reserved)
        _compare_balance(issues, "snapshot_consumed_vs_ledger", subscription.consumed_units, ledger_consumed)
        _compare_balance(issues, "snapshot_granted_vs_source", subscription.granted_units, source_granted)
        _compare_balance(issues, "snapshot_reserved_vs_source", subscription.reserved_units, source_reserved)
        _compare_balance(issues, "snapshot_consumed_vs_source", subscription.consumed_units, source_consumed)
        _compare_balance(issues, "source_granted_vs_ledger", source_granted, ledger_granted)
        _compare_balance(issues, "source_reserved_vs_ledger", source_reserved, ledger_reserved)
        _compare_balance(issues, "source_consumed_vs_ledger", source_consumed, ledger_consumed)
        if _quantize(subscription.consumed_units + subscription.reserved_units) > _quantize(subscription.granted_units):
            issues.append({"code": "credit_conservation_violation"})

        stale_reservations = int(
            self.session.scalar(
                select(func.count())
                .select_from(UsageReservation)
                .where(
                    UsageReservation.tenant_id == self.tenant.id,
                    UsageReservation.subscription_id == subscription.id,
                    UsageReservation.state == UsageReservationState.RESERVED,
                    UsageReservation.lease_expires_at <= started_at,
                )
            )
            or 0
        )
        if stale_reservations:
            issues.append({"code": "stale_reservations", "count": stale_reservations})

        settlement_count = self._count(UsageSettlement, subscription.id)
        usage_event_count = self._count(UsageEvent, subscription.id)
        settled_reservation_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(UsageReservation)
                .where(
                    UsageReservation.tenant_id == self.tenant.id,
                    UsageReservation.subscription_id == subscription.id,
                    UsageReservation.state == UsageReservationState.SETTLED,
                )
            )
            or 0
        )
        if len({settlement_count, usage_event_count, settled_reservation_count}) != 1:
            issues.append(
                {
                    "code": "settlement_cardinality_mismatch",
                    "settlements": settlement_count,
                    "usage_events": usage_event_count,
                    "settled_reservations": settled_reservation_count,
                }
            )

        completed_at = _timestamp(now)
        run = CommercialReconciliationRun(
            tenant_id=self.tenant.id,
            subscription_id=subscription.id,
            run_key=run_key,
            status="clean" if not issues else "drift",
            issue_count=len(issues),
            snapshot_granted_units=_quantize(subscription.granted_units),
            snapshot_reserved_units=_quantize(subscription.reserved_units),
            snapshot_consumed_units=_quantize(subscription.consumed_units),
            ledger_granted_units=ledger_granted,
            ledger_reserved_units=ledger_reserved,
            ledger_consumed_units=ledger_consumed,
            source_granted_units=source_granted,
            source_reserved_units=source_reserved,
            source_consumed_units=source_consumed,
            issues_json=issues,
            requested_by=self.actor_id,
            request_id=request_id,
            started_at=started_at,
            completed_at=completed_at,
        )
        self.session.add(run)
        self.session.flush()
        self._audit(
            "commercial.reconciliation.run",
            "commercial_reconciliation_run",
            run.id,
            request_id,
            {"status": run.status, "issue_count": run.issue_count, "subscription_id": subscription.id},
        )
        self._outbox(
            run.id,
            "commercial.reconciliation_completed.v1",
            {"subscription_id": subscription.id, "status": run.status, "issue_count": run.issue_count},
        )
        self.session.commit()
        return run

    def create_statement(
        self,
        command: BillingStatementCommand,
        *,
        now: datetime | None = None,
    ) -> BillingPeriodStatement:
        if self.statement_signer is None:
            raise CommercialInvariantViolation("Billing statement signing is not configured")
        _validate_key(command.statement_key, "Billing statement key")
        _validate_request_id(command.request_id)
        period_start = _timestamp(command.period_start)
        period_end = _timestamp(command.period_end)
        generated_at = _timestamp(now)
        if period_end <= period_start:
            raise ValueError("Billing statement period end must be after period start")
        if period_end > generated_at:
            raise ValueError("Billing statements can only close completed periods")
        if command.revision <= 0:
            raise ValueError("Billing statement revision must be positive")
        subscription = self._subscription(command.subscription_key, lock=True)
        existing = self.session.scalar(
            select(BillingPeriodStatement).where(
                BillingPeriodStatement.tenant_id == self.tenant.id,
                BillingPeriodStatement.statement_key == command.statement_key,
            )
        )
        if existing is not None:
            if (
                existing.subscription_id != subscription.id
                or _timestamp(existing.period_start) != period_start
                or _timestamp(existing.period_end) != period_end
                or existing.revision != command.revision
            ):
                raise CommercialAccountingConflict("Billing statement key already exists with different parameters")
            return existing

        account = self.session.scalar(
            select(BillingAccount).where(
                BillingAccount.tenant_id == self.tenant.id,
                BillingAccount.id == subscription.billing_account_id,
            )
        )
        if account is None:
            raise CommercialInvariantViolation("Subscription billing account is unavailable")
        settlement_rows = list(
            self.session.execute(
                select(UsageSettlement, UsageEvent)
                .join(UsageEvent, UsageEvent.id == UsageSettlement.usage_event_id)
                .where(
                    UsageSettlement.tenant_id == self.tenant.id,
                    UsageSettlement.subscription_id == subscription.id,
                    UsageSettlement.created_at >= period_start,
                    UsageSettlement.created_at < period_end,
                )
                .order_by(UsageSettlement.created_at, UsageSettlement.id)
            )
        )
        adjustments = list(
            self.session.scalars(
                select(BillingAdjustment)
                .where(
                    BillingAdjustment.tenant_id == self.tenant.id,
                    BillingAdjustment.subscription_id == subscription.id,
                    BillingAdjustment.created_at >= period_start,
                    BillingAdjustment.created_at < period_end,
                )
                .order_by(BillingAdjustment.created_at, BillingAdjustment.id)
            ).all()
        )
        settlement_units = _quantize(sum((row[0].charged_units for row in settlement_rows), ZERO_UNITS))
        adjustment_units = _quantize(sum((item.units_delta for item in adjustments), ZERO_UNITS))
        net_units = _quantize(settlement_units + adjustment_units)
        result_count = sum(row[1].result_count for row in settlement_rows)
        response_bytes = sum(row[1].response_bytes for row in settlement_rows)
        payload: dict[str, Any] = {
            "schema": "pharma.billing-statement.v1",
            "statement_key": command.statement_key,
            "revision": command.revision,
            "tenant_id": self.tenant.id,
            "subscription": {
                "id": subscription.id,
                "key": subscription.subscription_key,
                "billing_account_id": subscription.billing_account_id,
                "rate_card_version_id": subscription.rate_card_version_id,
            },
            "currency": account.currency,
            "period": {"start": _iso(period_start), "end": _iso(period_end)},
            "generated_at": _iso(generated_at),
            "settlements": [
                {
                    "id": settlement.id,
                    "settlement_key": settlement.settlement_key,
                    "reservation_id": settlement.reservation_id,
                    "usage_event_id": event.id,
                    "billing_class": event.billing_class,
                    "charged_units": _unit_string(settlement.charged_units),
                    "result_count": event.result_count,
                    "response_bytes": event.response_bytes,
                    "rate_card_version_id": settlement.rate_card_version_id,
                    "created_at": _iso(settlement.created_at),
                }
                for settlement, event in settlement_rows
            ],
            "adjustments": [
                {
                    "id": item.id,
                    "adjustment_key": item.adjustment_key,
                    "kind": item.adjustment_kind,
                    "reverses_settlement_id": item.reverses_settlement_id,
                    "reverses_adjustment_id": item.reverses_adjustment_id,
                    "units_delta": _unit_string(item.units_delta),
                    "reason": item.reason,
                    "created_at": _iso(item.created_at),
                }
                for item in adjustments
            ],
            "totals": {
                "settlement_units": _unit_string(settlement_units),
                "adjustment_units": _unit_string(adjustment_units),
                "net_consumed_units": _unit_string(net_units),
                "settlement_count": len(settlement_rows),
                "adjustment_count": len(adjustments),
                "result_count": result_count,
                "response_bytes": response_bytes,
            },
        }
        signed = self.statement_signer.sign(payload)
        statement = BillingPeriodStatement(
            tenant_id=self.tenant.id,
            subscription_id=subscription.id,
            billing_account_id=subscription.billing_account_id,
            statement_key=command.statement_key,
            revision=command.revision,
            period_start=period_start,
            period_end=period_end,
            settlement_units=settlement_units,
            adjustment_units=adjustment_units,
            net_consumed_units=net_units,
            settlement_count=len(settlement_rows),
            adjustment_count=len(adjustments),
            result_count=result_count,
            response_bytes=response_bytes,
            manifest_sha256=signed.sha256,
            signature_key_id=signed.key_id,
            manifest_signature=signed.signature,
            payload_json=payload,
            generated_by=self.actor_id,
            request_id=command.request_id,
            generated_at=generated_at,
        )
        self.session.add(statement)
        self.session.flush()
        self._audit(
            "commercial.billing_statement.create",
            "billing_period_statement",
            statement.id,
            command.request_id,
            {"manifest_sha256": statement.manifest_sha256, "revision": statement.revision},
        )
        self._outbox(
            statement.id,
            "commercial.billing_statement_created.v1",
            {
                "subscription_id": subscription.id,
                "manifest_sha256": statement.manifest_sha256,
                "net_consumed_units": _unit_string(net_units),
            },
        )
        self.session.commit()
        return statement

    def statement_manifest(self, statement: BillingPeriodStatement) -> SignedBillingManifest:
        if statement.tenant_id != self.tenant.id:
            raise ValueError("Billing statement does not exist")
        return SignedBillingManifest(
            payload=statement.payload_json,
            sha256=statement.manifest_sha256,
            key_id=statement.signature_key_id,
            signature=statement.manifest_signature,
        )

    def record_invoice(
        self,
        statement_id: str,
        receipt: BillingProviderReceipt,
        *,
        request_id: str,
    ) -> InvoiceReference:
        _validate_request_id(request_id)
        receipt = validate_billing_provider_receipt(receipt)
        statement = self.session.scalar(
            select(BillingPeriodStatement).where(
                BillingPeriodStatement.tenant_id == self.tenant.id,
                BillingPeriodStatement.id == statement_id,
            )
        )
        if statement is None:
            raise ValueError("Billing statement does not exist")
        existing = self.session.scalar(
            select(InvoiceReference).where(
                InvoiceReference.tenant_id == self.tenant.id,
                InvoiceReference.statement_id == statement.id,
            )
        )
        amount_due = _nonnegative_amount(receipt.amount_due)
        currency = receipt.currency.upper()
        if existing is not None:
            if (
                existing.external_invoice_id != receipt.external_invoice_id
                or existing.provider != receipt.provider
                or existing.amount_due != amount_due
                or existing.currency != currency
            ):
                raise CommercialAccountingConflict("Billing statement already has a different invoice reference")
            return existing
        if statement.net_consumed_units < ZERO_UNITS:
            raise CommercialBalanceViolation("Negative billing statements require a provider credit-note adapter")
        if currency != str(statement.payload_json.get("currency", "")).upper():
            raise ValueError("Invoice currency does not match the billing statement")
        reference = InvoiceReference(
            tenant_id=self.tenant.id,
            billing_account_id=statement.billing_account_id,
            statement_id=statement.id,
            external_invoice_id=receipt.external_invoice_id,
            provider=receipt.provider,
            status=receipt.status,
            period_start=statement.period_start,
            period_end=statement.period_end,
            total_units=statement.net_consumed_units,
            amount_due=amount_due,
            currency=currency,
            request_id=request_id,
            metadata_json=receipt.metadata,
        )
        self.session.add(reference)
        self.session.flush()
        self._audit(
            "commercial.invoice.record",
            "invoice_reference",
            reference.id,
            request_id,
            {"provider": receipt.provider, "external_invoice_id": receipt.external_invoice_id},
        )
        self._outbox(
            reference.id,
            "commercial.invoice_recorded.v1",
            {"statement_id": statement.id, "external_invoice_id": receipt.external_invoice_id},
        )
        self.session.commit()
        return reference

    def _apply_adjustment(
        self,
        *,
        subscription_key: str,
        adjustment_key: str,
        adjustment_kind: str,
        units_delta: Decimal,
        reason: str,
        request_id: str,
        metadata: dict[str, Any],
    ) -> BillingAdjustment:
        subscription = self._subscription(subscription_key, lock=True)
        return self._apply_adjustment_locked(
            subscription,
            adjustment_key=adjustment_key,
            adjustment_kind=adjustment_kind,
            units_delta=units_delta,
            reason=reason,
            request_id=request_id,
            metadata=metadata,
        )

    def _apply_adjustment_locked(
        self,
        subscription: CommercialSubscription,
        *,
        adjustment_key: str,
        adjustment_kind: str,
        units_delta: Decimal,
        reason: str,
        request_id: str,
        metadata: dict[str, Any],
        reverses_adjustment_id: str | None = None,
        reverses_settlement_id: str | None = None,
    ) -> BillingAdjustment:
        _validate_key(adjustment_key, "Adjustment key")
        _validate_request_id(request_id)
        if not reason.strip() or len(reason) > 1000:
            raise ValueError("Adjustment reason must contain 1-1000 characters")
        if len(_canonical_json(metadata)) > 16_384:
            raise ValueError("Adjustment metadata exceeds 16384 bytes")
        existing = self.session.scalar(
            select(BillingAdjustment).where(
                BillingAdjustment.tenant_id == self.tenant.id,
                BillingAdjustment.adjustment_key == adjustment_key,
            )
        )
        if existing is not None:
            if (
                existing.subscription_id != subscription.id
                or existing.adjustment_kind != adjustment_kind
                or existing.units_delta != units_delta
                or existing.reverses_adjustment_id != reverses_adjustment_id
                or existing.reverses_settlement_id != reverses_settlement_id
                or existing.reason != reason
            ):
                raise CommercialAccountingConflict("Adjustment key already exists with different values")
            return existing
        if reverses_settlement_id is not None:
            prior = self.session.scalar(
                select(BillingAdjustment).where(
                    BillingAdjustment.tenant_id == self.tenant.id,
                    BillingAdjustment.reverses_settlement_id == reverses_settlement_id,
                )
            )
            if prior is not None:
                raise CommercialAccountingConflict("Usage settlement has already been reversed")
        if reverses_adjustment_id is not None:
            prior = self.session.scalar(
                select(BillingAdjustment).where(
                    BillingAdjustment.tenant_id == self.tenant.id,
                    BillingAdjustment.reverses_adjustment_id == reverses_adjustment_id,
                )
            )
            if prior is not None:
                raise CommercialAccountingConflict("Billing adjustment has already been reversed")
        projected_consumed = _quantize(subscription.consumed_units + units_delta)
        if projected_consumed < ZERO_UNITS:
            raise CommercialBalanceViolation("Adjustment would make consumed units negative")
        if _quantize(projected_consumed + subscription.reserved_units) > _quantize(subscription.granted_units):
            raise CommercialBalanceViolation("Adjustment would exceed the granted credit balance")
        adjustment = BillingAdjustment(
            tenant_id=self.tenant.id,
            subscription_id=subscription.id,
            adjustment_key=adjustment_key,
            adjustment_kind=adjustment_kind,
            reverses_adjustment_id=reverses_adjustment_id,
            reverses_settlement_id=reverses_settlement_id,
            units_delta=units_delta,
            reason=reason,
            created_by=self.actor_id,
            request_id=request_id,
            metadata_json=metadata,
        )
        self.session.add(adjustment)
        self.session.flush()
        subscription.consumed_units = projected_consumed
        subscription.row_version += 1
        event_type = (
            CommercialLedgerEventType.ADJUSTMENT
            if adjustment_kind == "usage_adjustment"
            else CommercialLedgerEventType.REVERSAL
        )
        self._ledger(
            subscription,
            event_key=f"adjustment:{adjustment.id}",
            event_type=event_type,
            request_id=request_id,
            adjustment_id=adjustment.id,
            settlement_id=reverses_settlement_id,
            consumed_delta=units_delta,
            details={
                "adjustment_key": adjustment_key,
                "adjustment_kind": adjustment_kind,
                "reason": reason,
            },
        )
        self._audit(
            f"commercial.billing.{adjustment_kind}",
            "billing_adjustment",
            adjustment.id,
            request_id,
            {"units_delta": _unit_string(units_delta), "subscription_id": subscription.id},
        )
        self._outbox(
            adjustment.id,
            "commercial.billing_adjustment_recorded.v1",
            {
                "subscription_id": subscription.id,
                "adjustment_kind": adjustment_kind,
                "units_delta": _unit_string(units_delta),
            },
        )
        self.session.commit()
        return adjustment

    def _subscription(self, subscription_key: str, *, lock: bool) -> CommercialSubscription:
        statement = select(CommercialSubscription).where(
            CommercialSubscription.tenant_id == self.tenant.id,
            CommercialSubscription.subscription_key == subscription_key,
        )
        if lock:
            statement = statement.with_for_update()
        subscription = self.session.scalar(statement)
        if subscription is None:
            raise ValueError("Commercial subscription does not exist")
        return subscription

    def _subscription_by_id(self, subscription_id: str, *, lock: bool) -> CommercialSubscription:
        statement = select(CommercialSubscription).where(
            CommercialSubscription.tenant_id == self.tenant.id,
            CommercialSubscription.id == subscription_id,
        )
        if lock:
            statement = statement.with_for_update()
        subscription = self.session.scalar(statement)
        if subscription is None:
            raise CommercialInvariantViolation("Commercial subscription is unavailable")
        return subscription

    def _ledger_totals(self, subscription_id: str) -> tuple[Decimal, Decimal, Decimal]:
        row = self.session.execute(
            select(
                func.sum(CommercialLedgerEntry.granted_delta),
                func.sum(CommercialLedgerEntry.reserved_delta),
                func.sum(CommercialLedgerEntry.consumed_delta),
            ).where(
                CommercialLedgerEntry.tenant_id == self.tenant.id,
                CommercialLedgerEntry.subscription_id == subscription_id,
            )
        ).one()
        return tuple(_quantize(value or ZERO_UNITS) for value in row)  # type: ignore[return-value]

    def _sum(self, statement: Any) -> Decimal:
        return _quantize(self.session.scalar(statement) or ZERO_UNITS)

    def _count(self, model: type[UsageSettlement] | type[UsageEvent], subscription_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    model.tenant_id == self.tenant.id,
                    model.subscription_id == subscription_id,
                )
            )
            or 0
        )

    def _ledger(
        self,
        subscription: CommercialSubscription,
        *,
        event_key: str,
        event_type: CommercialLedgerEventType,
        request_id: str,
        reservation_id: str | None = None,
        settlement_id: str | None = None,
        adjustment_id: str | None = None,
        granted_delta: Decimal = ZERO_UNITS,
        reserved_delta: Decimal = ZERO_UNITS,
        consumed_delta: Decimal = ZERO_UNITS,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            CommercialLedgerEntry(
                tenant_id=self.tenant.id,
                subscription_id=subscription.id,
                reservation_id=reservation_id,
                settlement_id=settlement_id,
                adjustment_id=adjustment_id,
                event_key=event_key,
                event_type=event_type,
                granted_delta=_quantize(granted_delta),
                reserved_delta=_quantize(reserved_delta),
                consumed_delta=_quantize(consumed_delta),
                request_id=request_id,
                details=details or {},
            )
        )

    def _audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None,
        request_id: str,
        details: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=self.tenant.id,
                actor_type="operator",
                actor_id=self.actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                request_id=request_id,
                details=details,
            )
        )

    def _outbox(self, aggregate_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.session.add(
            OutboxEvent(
                tenant_id=self.tenant.id,
                aggregate_type="commercial_accounting",
                aggregate_id=aggregate_id,
                event_type=event_type,
                payload=payload,
            )
        )


def _delta(value: Decimal | str) -> Decimal:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Adjustment units must be a decimal number") from exc
    if not parsed.is_finite() or parsed == ZERO_UNITS:
        raise ValueError("Adjustment units must be finite and non-zero")
    return _quantize(parsed)


def _nonnegative_amount(value: Decimal) -> Decimal:
    if not value.is_finite() or value < ZERO_UNITS:
        raise ValueError("Invoice amount must be finite and non-negative")
    return _quantize(value)


def _quantize(value: Decimal | int) -> Decimal:
    return Decimal(value).quantize(UNIT_QUANTUM, rounding=ROUND_HALF_UP)


def _unit_string(value: Decimal) -> str:
    return format(_quantize(value), "f")


def _timestamp(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)
    return timestamp.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _timestamp(value).isoformat().replace("+00:00", "Z")


def _validate_key(value: str, label: str) -> None:
    if not KEY_PATTERN.fullmatch(value):
        raise ValueError(f"{label} must contain 8-200 safe characters")


def _validate_request_id(value: str) -> None:
    if not value or len(value) > 100:
        raise ValueError("Request ID is invalid")


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Accounting metadata is not valid JSON") from exc


def _compare_balance(issues: list[dict[str, Any]], code: str, expected: Decimal, actual: Decimal) -> None:
    normalized_expected = _quantize(expected)
    normalized_actual = _quantize(actual)
    if normalized_expected != normalized_actual:
        issues.append(
            {
                "code": code,
                "expected": _unit_string(normalized_expected),
                "actual": _unit_string(normalized_actual),
                "delta": _unit_string(normalized_actual - normalized_expected),
            }
        )
