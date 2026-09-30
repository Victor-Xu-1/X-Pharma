from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.commercial.accounting import (
    BillingStatementCommand,
    CommercialAccountingService,
    CommercialBalanceViolation,
    UsageAdjustmentCommand,
)
from pharma_intel.commercial.billing import BillingStatementSigner
from pharma_intel.commercial.disputes import (
    BillingDisputeConflict,
    BillingDisputeNotFound,
    BillingDisputeService,
    CreateBillingDisputeCommand,
    TransitionBillingDisputeCommand,
)
from pharma_intel.db import get_session
from pharma_intel.models import (
    AuditEvent,
    BillingAdjustment,
    BillingDispute,
    BillingDisputeEvent,
    BillingPeriodStatement,
    OutboxEvent,
    Tenant,
)
from pharma_intel.security import Principal, require_principal
from tests.support.commercial import CommercialContractFixture, seed_commercial_contract

SIGNING_SECRET = hashlib.sha256(b"billing-dispute-test-signing-key").hexdigest()


def _operator(tenant: Tenant) -> Principal:
    return Principal(tenant.id, "finance-operator", "user", frozenset({"commercial:read", "commercial:write"}))


def _test_key(label: str) -> str:
    return f"test.{label}.00000000"


def _statement(session: Session, tenant: Tenant) -> tuple[CommercialContractFixture, BillingPeriodStatement, datetime]:
    contract = seed_commercial_contract(session, tenant, granted_units=Decimal("100"))
    accounting = CommercialAccountingService(
        session,
        tenant,
        actor_id="billing-dispute-seed",
        statement_signer=BillingStatementSigner(SIGNING_SECRET, key_id="billing-dispute-v1"),
    )
    accounting.adjust_usage(
        UsageAdjustmentCommand(
            contract.subscription.subscription_key,
            "dispute.seed.usage.0001",
            "10",
            "Seed consumed units for a credit decision",
            "dispute-seed-request",
        )
    )
    now = datetime.now(UTC)
    statement = accounting.create_statement(
        BillingStatementCommand(
            contract.subscription.subscription_key,
            "dispute.statement.2026.07",
            now - timedelta(days=1),
            now,
            1,
            "dispute-statement-request",
        ),
        now=now,
    )
    return contract, statement, now


def _create(service: BillingDisputeService, statement_id: str, now: datetime) -> dict[str, Any]:
    return service.create(
        CreateBillingDisputeCommand(
            dispute_key="dispute.customer.0001",
            statement_id=statement_id,
            invoice_reference_id=None,
            category="usage",
            disputed_units="3.5",
            subject="Unexpected usage charge",
            description="Customer requests validation of metered target searches.",
        ),
        request_id="dispute-open-request",
        now=now,
    )


def test_dispute_lifecycle_is_idempotent_versioned_audited_and_posts_atomic_credit(
    session: Session,
    tenant: Tenant,
) -> None:
    contract, statement, now = _statement(session, tenant)
    service = BillingDisputeService(session, _operator(tenant), sla_hours=120)
    opened = _create(service, statement.id, now)
    replayed = _create(service, statement.id, now)
    assert replayed["id"] == opened["id"]
    assert opened["status"] == "open"
    assert opened["due_at"] == now + timedelta(hours=120)
    assert service.list(now=now + timedelta(hours=121))[0]["overdue"] is True

    investigating = service.transition(
        opened["id"],
        TransitionBillingDisputeCommand(
            operation_key=_test_key("investigate"),
            expected_version=1,
            action="investigate",
            notes="Finance owner accepted the case for investigation.",
            assigned_to="finance-owner@example.test",
        ),
        request_id="dispute-investigate-request",
        now=now + timedelta(hours=1),
    )
    assert investigating["status"] == "investigating"
    assert investigating["version"] == 2
    assert investigating["assigned_to"] == "finance-owner@example.test"
    replay = service.transition(
        opened["id"],
        TransitionBillingDisputeCommand(
            operation_key=_test_key("investigate"),
            expected_version=1,
            action="investigate",
            notes="Finance owner accepted the case for investigation.",
            assigned_to="finance-owner@example.test",
        ),
        request_id="dispute-investigate-replay",
    )
    assert replay["version"] == 2
    with pytest.raises(BillingDisputeConflict, match="another transition"):
        service.transition(
            opened["id"],
            TransitionBillingDisputeCommand(
                operation_key=_test_key("investigate"),
                expected_version=1,
                action="investigate",
                notes="A changed command must not replay under the same operation key.",
                assigned_to="finance-owner@example.test",
            ),
            request_id="dispute-investigate-conflict",
        )

    with pytest.raises(BillingDisputeConflict, match="version is stale"):
        service.transition(
            opened["id"],
            TransitionBillingDisputeCommand(
                operation_key=_test_key("resolve-stale"),
                expected_version=1,
                action="resolve_no_credit",
                notes="Stale operator decision must not be accepted.",
            ),
            request_id="dispute-stale-request",
        )

    resolved = service.transition(
        opened["id"],
        TransitionBillingDisputeCommand(
            operation_key=_test_key("resolve-credit"),
            expected_version=2,
            action="resolve_credit",
            notes="Metering review confirmed two units should be credited.",
            adjustment_key="dispute.credit.adjustment.0001",
            credit_units="2",
        ),
        request_id="dispute-credit-request",
        now=now + timedelta(hours=2),
    )
    assert resolved["status"] == "resolved"
    assert resolved["resolution_code"] == "credit"
    assert resolved["resolution_adjustment_key"] == "dispute.credit.adjustment.0001"
    session.refresh(contract.subscription)
    assert contract.subscription.consumed_units == Decimal("8.00000000")
    adjustment = session.scalar(
        select(BillingAdjustment).where(BillingAdjustment.adjustment_key == "dispute.credit.adjustment.0001")
    )
    assert adjustment is not None
    assert adjustment.units_delta == Decimal("-2.00000000")
    assert adjustment.metadata_json["billing_dispute_id"] == opened["id"]
    assert session.scalar(select(func.count()).select_from(BillingDisputeEvent)) == 3
    assert (
        session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.resource_type == "billing_dispute")
        )
        == 3
    )
    assert (
        session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.aggregate_type == "billing_dispute")
        )
        == 3
    )


def test_disputes_reject_cross_tenant_statement_and_conflicting_idempotency(
    session: Session,
    tenant: Tenant,
) -> None:
    _, statement, now = _statement(session, tenant)
    service = BillingDisputeService(session, _operator(tenant))
    _create(service, statement.id, now)
    with pytest.raises(BillingDisputeConflict, match="different values"):
        service.create(
            CreateBillingDisputeCommand(
                dispute_key="dispute.customer.0001",
                statement_id=statement.id,
                invoice_reference_id=None,
                category="pricing",
                disputed_units="3.5",
                subject="Unexpected usage charge",
                description="Customer requests validation of metered target searches.",
            ),
            request_id="dispute-conflict-request",
        )
    with pytest.raises(ValueError, match="cannot exceed"):
        service.create(
            CreateBillingDisputeCommand(
                dispute_key=_test_key("excessive-units"),
                statement_id=statement.id,
                invoice_reference_id=None,
                category="usage",
                disputed_units="11",
                subject="Excessive disputed units",
                description="The requested units exceed the signed statement net units.",
            ),
            request_id="dispute-excessive-request",
        )

    other = Tenant(slug="billing-dispute-other", name="Billing Dispute Other")
    session.add(other)
    session.commit()
    with pytest.raises(BillingDisputeNotFound):
        BillingDisputeService(session, _operator(other)).create(
            CreateBillingDisputeCommand(
                dispute_key=_test_key("other-dispute"),
                statement_id=statement.id,
                invoice_reference_id=None,
                category="usage",
                disputed_units="1",
                subject="Cross tenant attempt",
                description="The referenced statement belongs to another tenant.",
            ),
            request_id="cross-tenant-dispute",
        )
    assert session.scalar(select(func.count()).select_from(BillingDispute)) == 1


def test_failed_credit_rolls_back_dispute_decision_and_event(
    session: Session,
    tenant: Tenant,
) -> None:
    contract, statement, now = _statement(session, tenant)
    service = BillingDisputeService(session, _operator(tenant))
    opened = _create(service, statement.id, now)
    service.transition(
        opened["id"],
        TransitionBillingDisputeCommand(
            operation_key=_test_key("rollback-investigate"),
            expected_version=1,
            action="investigate",
            notes="Finance accepted the case before the balance changed.",
        ),
        request_id="rollback-investigate-request",
        now=now + timedelta(minutes=1),
    )
    CommercialAccountingService(session, tenant, actor_id="concurrent-finance").adjust_usage(
        UsageAdjustmentCommand(
            contract.subscription.subscription_key,
            "dispute.concurrent.credit.0001",
            "-10",
            "A separate approved credit consumed the remaining balance",
            "concurrent-credit-request",
        )
    )
    with pytest.raises(CommercialBalanceViolation):
        service.transition(
            opened["id"],
            TransitionBillingDisputeCommand(
                operation_key=_test_key("rollback-credit"),
                expected_version=2,
                action="resolve_credit",
                notes="This credit can no longer be posted against the current balance.",
                adjustment_key="dispute.rollback.credit.0001",
                credit_units="2",
            ),
            request_id="rollback-credit-request",
            now=now + timedelta(minutes=2),
        )
    session.expire_all()
    dispute = session.get(BillingDispute, opened["id"])
    assert dispute is not None
    assert dispute.status == "investigating"
    assert dispute.version == 2
    assert dispute.resolution_adjustment_key is None
    assert session.scalar(select(func.count()).select_from(BillingDisputeEvent)) == 2
    assert (
        session.scalar(
            select(func.count())
            .select_from(BillingAdjustment)
            .where(BillingAdjustment.adjustment_key == "dispute.rollback.credit.0001")
        )
        == 0
    )


def test_human_billing_dispute_http_contract_and_conflict_mapping(
    session: Session,
    tenant: Tenant,
) -> None:
    _, statement, _ = _statement(session, tenant)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_principal] = lambda: _operator(tenant)
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/commercial/billing-disputes",
                json={
                    "dispute_key": "dispute.http.0001",
                    "statement_id": statement.id,
                    "category": "pricing",
                    "disputed_units": "2.5",
                    "subject": "Unexpected rate application",
                    "description": "The customer requests a review of the contracted unit rate.",
                },
            )
            assert created.status_code == 201
            dispute = created.json()
            assert dispute["statement_key"] == statement.statement_key
            assert dispute["status"] == "open"
            listed = client.get("/api/v1/commercial/billing-disputes?dispute_status=open")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [dispute["id"]]

            investigated = client.post(
                f"/api/v1/commercial/billing-disputes/{dispute['id']}/transition",
                json={
                    "operation_key": _test_key("http-investigate"),
                    "expected_version": 1,
                    "action": "investigate",
                    "notes": "Finance accepted the dispute and assigned an owner.",
                    "assigned_to": "finance-owner@example.test",
                },
            )
            assert investigated.status_code == 200
            assert investigated.json()["status"] == "investigating"
            stale = client.post(
                f"/api/v1/commercial/billing-disputes/{dispute['id']}/transition",
                json={
                    "operation_key": _test_key("http-stale"),
                    "expected_version": 1,
                    "action": "resolve_no_credit",
                    "notes": "This decision uses a stale browser version.",
                },
            )
            assert stale.status_code == 409
            assert "reload" in stale.json()["detail"]
    finally:
        app.dependency_overrides.clear()
