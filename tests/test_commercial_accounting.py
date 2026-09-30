from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.commercial.accounting import (
    BillingStatementCommand,
    CommercialAccountingConflict,
    CommercialAccountingService,
    CommercialBalanceViolation,
    ReversalCommand,
    UsageAdjustmentCommand,
)
from pharma_intel.commercial.billing import BillingProviderReceipt, BillingStatementSigner
from pharma_intel.commercial.service import CommercialUsageService, ReserveCommand, SettleCommand
from pharma_intel.models import (
    BillingAdjustment,
    CommercialLedgerEntry,
    CommercialLedgerEventType,
    InvoiceReference,
    OutboxEvent,
    Tenant,
    UsageReservationState,
)
from tests.support.commercial import seed_commercial_contract

SIGNING_SECRET = "billing-statement-test-secret-with-more-than-thirty-two-bytes"  # noqa: S105


def _accounting(session: Session, tenant: Tenant) -> CommercialAccountingService:
    return CommercialAccountingService(
        session,
        tenant,
        actor_id="FIN-TEST",
        statement_signer=BillingStatementSigner(SIGNING_SECRET, key_id="billing-test-v1"),
    )


def _settle_one(session: Session, tenant: Tenant, *, now: datetime | None = None) -> tuple[str, Decimal]:
    contract = seed_commercial_contract(session, tenant)
    usage = CommercialUsageService(session, contract.principal)
    timestamp = now or datetime.now(UTC)
    reservation = usage.reserve(
        ReserveCommand(
            "entity.search",
            "accounting-settle-0001",
            {"q": "EGFR", "limit": 1},
            1,
            "5",
            "accounting-reserve",
        ),
        now=timestamp,
    ).reservation
    outcome = usage.settle(
        SettleCommand(
            reservation.id,
            1,
            {"items": [{"id": "entity-egfr", "private_payload": "must-not-enter-billing"}]},
            {},
            "accounting-settle",
        ),
        now=timestamp,
    )
    return outcome.settlement.id, outcome.settlement.charged_units


def test_adjustments_and_reversals_are_idempotent_append_only(session: Session, tenant: Tenant) -> None:
    settlement_id, charged_units = _settle_one(session, tenant)
    accounting = _accounting(session, tenant)

    reversal = accounting.reverse_settlement(
        settlement_id,
        ReversalCommand("settlement-reversal-0001", "approved duplicate delivery", "reverse-request-1"),
    )
    assert reversal.adjustment_kind == "settlement_reversal"
    assert reversal.units_delta == -charged_units
    assert (
        accounting.reverse_settlement(
            settlement_id,
            ReversalCommand("settlement-reversal-0001", "approved duplicate delivery", "reverse-request-2"),
        ).id
        == reversal.id
    )
    with pytest.raises(CommercialAccountingConflict, match="already been reversed"):
        accounting.reverse_settlement(
            settlement_id,
            ReversalCommand("settlement-reversal-0002", "second reversal denied", "reverse-request-3"),
        )

    restored = accounting.reverse_adjustment(
        reversal.id,
        ReversalCommand("adjustment-reversal-0001", "reopen valid charge", "reverse-request-4"),
    )
    assert restored.adjustment_kind == "adjustment_reversal"
    assert restored.units_delta == charged_units
    with pytest.raises(CommercialAccountingConflict, match="already been reversed"):
        accounting.reverse_adjustment(
            reversal.id,
            ReversalCommand("adjustment-reversal-0002", "duplicate denied", "reverse-request-5"),
        )

    debit = accounting.adjust_usage(
        UsageAdjustmentCommand(
            "test-subscription",
            "manual-debit-0001",
            "2.5",
            "approved under-billing correction",
            "adjust-request-1",
        )
    )
    assert debit.units_delta == Decimal("2.50000000")
    with pytest.raises(CommercialBalanceViolation, match="negative"):
        accounting.adjust_usage(
            UsageAdjustmentCommand(
                "test-subscription",
                "manual-credit-too-large",
                "-100",
                "invalid oversized credit",
                "adjust-request-2",
            )
        )

    adjustments = list(session.scalars(select(BillingAdjustment).order_by(BillingAdjustment.created_at)).all())
    assert len(adjustments) == 3
    adjustment_ledger = list(
        session.scalars(select(CommercialLedgerEntry).where(CommercialLedgerEntry.adjustment_id.is_not(None))).all()
    )
    assert len(adjustment_ledger) == 3
    assert {entry.event_type for entry in adjustment_ledger} == {
        CommercialLedgerEventType.ADJUSTMENT,
        CommercialLedgerEventType.REVERSAL,
    }


def test_expiry_sweep_is_reentrant_and_reconciliation_is_clean(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant)
    usage = CommercialUsageService(session, contract.principal, reservation_lease_seconds=15)
    now = datetime.now(UTC)
    reservation = usage.reserve(
        ReserveCommand(
            "entity.search",
            "expiry-sweep-0001",
            {"q": "KRAS", "limit": 1},
            1,
            "5",
            "expiry-reserve",
        ),
        now=now,
    ).reservation
    accounting = _accounting(session, tenant)

    first = accounting.expire_stale_reservations(request_id="expiry-sweep-1", now=now + timedelta(seconds=16))
    second = accounting.expire_stale_reservations(request_id="expiry-sweep-2", now=now + timedelta(seconds=17))
    session.refresh(reservation)
    session.refresh(contract.subscription)
    assert first.expired_reservations == 1
    assert first.released_units == reservation.reserved_units
    assert second.expired_reservations == 0
    assert reservation.state == UsageReservationState.EXPIRED
    assert contract.subscription.reserved_units == Decimal("0E-8")

    reconciliation = accounting.reconcile(
        contract.subscription.subscription_key,
        run_key="reconciliation-clean-0001",
        request_id="reconcile-request-1",
        now=now + timedelta(seconds=18),
    )
    assert reconciliation.status == "clean"
    assert reconciliation.issue_count == 0
    assert reconciliation.ledger_reserved_units == Decimal("0E-8")
    assert (
        accounting.reconcile(
            contract.subscription.subscription_key,
            run_key="reconciliation-clean-0001",
            request_id="reconcile-request-2",
        ).id
        == reconciliation.id
    )


def test_reconciliation_records_drift_without_repairing_balance(session: Session, tenant: Tenant) -> None:
    contract = seed_commercial_contract(session, tenant)
    contract.subscription.consumed_units = Decimal("1.00000000")
    session.commit()

    run = _accounting(session, tenant).reconcile(
        contract.subscription.subscription_key,
        run_key="reconciliation-drift-0001",
        request_id="reconcile-drift-request",
    )
    assert run.status == "drift"
    assert run.issue_count >= 2
    assert {item["code"] for item in run.issues_json} >= {
        "snapshot_consumed_vs_ledger",
        "snapshot_consumed_vs_source",
    }
    session.refresh(contract.subscription)
    assert contract.subscription.consumed_units == Decimal("1.00000000")


def test_signed_statement_excludes_results_and_records_provider_reference(session: Session, tenant: Tenant) -> None:
    now = datetime.now(UTC)
    settlement_id, charged_units = _settle_one(session, tenant, now=now)
    accounting = _accounting(session, tenant)
    accounting.reverse_settlement(
        settlement_id,
        ReversalCommand("statement-reversal-0001", "approved full credit", "statement-reverse"),
    )
    statement = accounting.create_statement(
        BillingStatementCommand(
            subscription_key="test-subscription",
            statement_key="statement-2026-07-r1",
            period_start=now - timedelta(hours=1),
            period_end=now + timedelta(minutes=1),
            revision=1,
            request_id="statement-request-1",
        ),
        now=now + timedelta(minutes=2),
    )
    manifest = accounting.statement_manifest(statement)
    signer = BillingStatementSigner(SIGNING_SECRET, key_id="billing-test-v1")

    assert signer.verify(manifest)
    assert statement.settlement_units == charged_units
    assert statement.adjustment_units == -charged_units
    assert statement.net_consumed_units == Decimal("0E-8")
    assert statement.settlement_count == 1
    assert statement.adjustment_count == 1
    serialized = json.dumps(statement.payload_json, sort_keys=True)
    assert "must-not-enter-billing" not in serialized
    assert "private_payload" not in serialized
    assert (
        accounting.create_statement(
            BillingStatementCommand(
                subscription_key="test-subscription",
                statement_key="statement-2026-07-r1",
                period_start=now - timedelta(hours=1),
                period_end=now + timedelta(minutes=1),
                revision=1,
                request_id="statement-request-retry",
            ),
            now=now + timedelta(minutes=3),
        ).id
        == statement.id
    )

    invoice = accounting.record_invoice(
        statement.id,
        BillingProviderReceipt("approved-erp", "INV-TEST-1", "issued", Decimal("0"), "CNY", {}),
        request_id="invoice-request-1",
    )
    assert invoice.statement_id == statement.id
    assert (
        accounting.record_invoice(
            statement.id,
            BillingProviderReceipt("approved-erp", "INV-TEST-1", "issued", Decimal("0"), "CNY", {}),
            request_id="invoice-request-2",
        ).id
        == invoice.id
    )
    assert session.scalar(select(func.count()).select_from(InvoiceReference)) == 1
    assert (session.scalar(select(func.count()).select_from(OutboxEvent)) or 0) >= 5


def test_statement_signer_rejects_tampering() -> None:
    signer = BillingStatementSigner(SIGNING_SECRET, key_id="billing-test-v1")
    signed = signer.sign({"schema": "test", "units": "1.00000000"})
    tampered = type(signed)({"schema": "test", "units": "2.00000000"}, signed.sha256, signed.key_id, signed.signature)
    assert signer.verify(signed)
    assert not signer.verify(tampered)
    with pytest.raises(ValueError, match="at least 32 bytes"):
        BillingStatementSigner("short", key_id="billing-test-v1")
