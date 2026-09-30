from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.commercial.accounting import BillingStatementCommand, CommercialAccountingService
from pharma_intel.commercial.billing import BillingStatementSigner
from pharma_intel.commercial.billing_operations import (
    BILLING_CONSUMER_NAME,
    BILLING_STATEMENT_EVENT_TYPE,
    BillingOperationsService,
)
from pharma_intel.commercial.operations import CommercialOperationsConflict
from pharma_intel.commercial.service import CommercialAccessDenied
from pharma_intel.models import (
    AuditEvent,
    BillingAccount,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
    Tenant,
)
from pharma_intel.security import Principal
from tests.support.commercial import seed_commercial_contract

SIGNING_SECRET = hashlib.sha256(b"billing-operations-signing-key").hexdigest()


def _operator(tenant: Tenant, scopes: set[str] | None = None) -> Principal:
    return Principal(
        tenant.id,
        "billing-operator",
        "user",
        frozenset(scopes or {"commercial:read", "commercial:write"}),
    )


def _create_statement(session: Session, tenant: Tenant) -> tuple[BillingAccount, OutboxEvent]:
    contract = seed_commercial_contract(session, tenant)
    account = session.get(BillingAccount, contract.subscription.billing_account_id)
    assert account is not None
    now = datetime.now(UTC)
    statement = CommercialAccountingService(
        session,
        tenant,
        actor_id="billing-operations-test",
        statement_signer=BillingStatementSigner(SIGNING_SECRET, key_id="billing-operations-v1"),
    ).create_statement(
        BillingStatementCommand(
            contract.subscription.subscription_key,
            "statement-operations-2026-07",
            now - timedelta(hours=1),
            now - timedelta(seconds=1),
            1,
            "billing-operations-statement",
        ),
        now=now,
    )
    event = session.scalar(
        select(OutboxEvent).where(
            OutboxEvent.aggregate_id == statement.id,
            OutboxEvent.event_type == BILLING_STATEMENT_EVENT_TYPE,
        )
    )
    assert event is not None
    return account, event


def test_customer_mapping_is_audited_masked_and_never_emitted_as_plaintext(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    account = session.get(BillingAccount, contract.subscription.billing_account_id)
    assert account is not None
    service = BillingOperationsService(session, _operator(tenant))

    before = service.list_accounts()
    assert before[0]["mapping_configured"] is False
    assert before[0]["statement_count"] == 0

    updated = service.set_customer_mapping(
        account.id,
        external_customer_reference="ERP-CUSTOMER-000042",
        reason="Approved ERP account binding",
        request_id="mapping-request-1",
    )

    assert updated["mapping_configured"] is True
    assert updated["external_customer_reference_masked"].endswith("0042")
    assert "ERP-CUSTOMER" not in updated["external_customer_reference_masked"]
    audit = session.scalar(select(AuditEvent).where(AuditEvent.action == "commercial.billing_customer_mapping.update"))
    outbox = session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "commercial.billing_customer_mapping_updated.v1")
    )
    assert audit is not None and outbox is not None
    assert "ERP-CUSTOMER-000042" not in json.dumps(audit.details)
    assert "ERP-CUSTOMER-000042" not in json.dumps(outbox.payload)
    assert audit.request_id == "mapping-request-1"

    short_reference = service.set_customer_mapping(
        account.id,
        external_customer_reference="A",
        reason="Provider reassigned a short account code",
        request_id="mapping-request-short",
    )
    assert short_reference["external_customer_reference_masked"] == "****"


def test_unresolved_statement_blocks_mapping_rotation_and_dead_delivery_can_be_replayed(
    session: Session,
    tenant: Tenant,
) -> None:
    account, event = _create_statement(session, tenant)
    account.external_customer_reference = "ERP-ORIGINAL-1000"
    dead = ProjectionDelivery(
        tenant_id=tenant.id,
        consumer_name=BILLING_CONSUMER_NAME,
        outbox_event_id=event.id,
        state=ProjectionDeliveryState.DEAD,
        attempts=4,
        available_at=datetime.now(UTC),
        last_error="provider rejected customer mapping",
    )
    session.add(dead)
    session.commit()
    service = BillingOperationsService(session, _operator(tenant))

    accounts = service.list_accounts()
    assert accounts[0]["statement_count"] == 1
    assert accounts[0]["unresolved_statement_count"] == 1
    with pytest.raises(CommercialOperationsConflict):
        service.set_customer_mapping(
            account.id,
            external_customer_reference="ERP-ROTATED-2000",
            reason="Rotate stale provider mapping",
            request_id="mapping-request-2",
        )

    deliveries = service.list_deliveries(state="dead")
    assert len(deliveries) == 1
    assert deliveries[0]["last_error"] == "provider rejected customer mapping"
    replayed = service.replay_delivery(
        dead.id,
        reason="Provider mapping repaired and verified",
        request_id="replay-request-1",
    )
    assert replayed["state"] == "retry"
    assert replayed["attempts"] == 4
    assert replayed["lease_expires_at"] is None
    assert session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "commercial.billing_delivery_replayed.v1")
    )

    with pytest.raises(CommercialOperationsConflict):
        service.replay_delivery(
            dead.id,
            reason="Duplicate replay must be rejected",
            request_id="replay-request-2",
        )


def test_billing_operations_require_human_scopes_and_tenant_partition(
    session: Session,
    tenant: Tenant,
) -> None:
    contract = seed_commercial_contract(session, tenant)
    account = session.get(BillingAccount, contract.subscription.billing_account_id)
    assert account is not None

    with pytest.raises(CommercialAccessDenied):
        BillingOperationsService(session, contract.principal)
    reader = BillingOperationsService(session, _operator(tenant, {"commercial:read"}))
    assert [item["id"] for item in reader.list_accounts()] == [account.id]
    with pytest.raises(HTTPException, match="Insufficient scope"):
        reader.set_customer_mapping(
            account.id,
            external_customer_reference="ERP-READONLY-1000",
            reason="Write should require an explicit scope",
            request_id="readonly-mapping",
        )

    other_tenant = Tenant(slug="billing-operations-other", name="Billing Operations Other")
    session.add(other_tenant)
    session.commit()
    other_reader = BillingOperationsService(session, _operator(other_tenant, {"commercial:read"}))
    assert other_reader.list_accounts() == []
    assert other_reader.list_deliveries() == []
