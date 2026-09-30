from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.commercial.accounting import BillingStatementCommand, CommercialAccountingService
from pharma_intel.commercial.billing import (
    BillingProviderReceipt,
    BillingProviderTransientError,
    BillingStatementSigner,
    SignedBillingManifest,
)
from pharma_intel.commercial.billing_consumer import BillingProviderConsumer
from pharma_intel.config import Settings
from pharma_intel.models import (
    AuditEvent,
    BillingAccount,
    InvoiceReference,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
    Tenant,
)
from tests.support.commercial import seed_commercial_contract

SIGNING_SECRET = hashlib.sha256(b"billing-consumer-test-signing-key").hexdigest()


class RecordingAdapter:
    def __init__(self, *, transient_failures: int = 0) -> None:
        self.transient_failures = transient_failures
        self.calls: list[tuple[str, str, str]] = []

    def create_invoice(
        self,
        manifest: SignedBillingManifest,
        *,
        idempotency_key: str,
        customer_reference: str,
    ) -> BillingProviderReceipt:
        self.calls.append((manifest.sha256, idempotency_key, customer_reference))
        if len(self.calls) <= self.transient_failures:
            raise BillingProviderTransientError("provider temporarily unavailable")
        return BillingProviderReceipt(
            "approved-erp",
            "INV-CONSUMER-1",
            "issued",
            Decimal("12.50"),
            "CNY",
            {"provider_request_id": "provider-request-1"},
        )


def _settings(*, max_attempts: int = 3) -> Settings:
    return Settings(
        _env_file=None,
        internal_service_jwt_secret="internal-test-secret-with-more-than-32-bytes",  # noqa: S106
        billing_statement_signing_secret=SIGNING_SECRET,
        billing_statement_signing_key_id="billing-test-v1",
        billing_provider_enabled=True,
        billing_provider_name="approved-erp",
        billing_provider_max_attempts=max_attempts,
        billing_provider_retry_base_seconds=0.1,
    )


def _statement(session: Session, tenant: Tenant) -> str:
    contract = seed_commercial_contract(session, tenant)
    account = session.get(BillingAccount, contract.subscription.billing_account_id)
    assert account is not None
    account.external_customer_reference = "CUSTOMER-CONSUMER-1"
    session.commit()
    now = datetime.now(UTC)
    service = CommercialAccountingService(
        session,
        tenant,
        actor_id="FIN-CONSUMER-TEST",
        statement_signer=BillingStatementSigner(SIGNING_SECRET, key_id="billing-test-v1"),
    )
    statement = service.create_statement(
        BillingStatementCommand(
            "test-subscription",
            "statement-consumer-2026-07",
            now - timedelta(hours=1),
            now - timedelta(seconds=1),
            1,
            "statement-consumer-request",
        ),
        now=now,
    )
    return statement.id


def test_billing_consumer_delivers_once_and_recovers_after_local_completion_crash(
    session: Session,
    tenant: Tenant,
) -> None:
    statement_id = _statement(session, tenant)
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    adapter = RecordingAdapter()
    first = BillingProviderConsumer(factory, adapter, _settings(), worker_id="billing-worker-1")

    result = first.drain_once()

    assert result.succeeded == 1
    assert len(adapter.calls) == 1
    assert adapter.calls[0][1].startswith(f"statement:{statement_id}:")
    assert adapter.calls[0][2] == "CUSTOMER-CONSUMER-1"
    assert session.scalar(select(func.count()).select_from(InvoiceReference)) == 1

    delivery = session.scalar(select(ProjectionDelivery))
    assert delivery is not None
    delivery.state = ProjectionDeliveryState.PROCESSING
    delivery.worker_id = "crashed-worker"
    delivery.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()

    recovered = BillingProviderConsumer(factory, adapter, _settings(), worker_id="billing-worker-2").drain_once()

    assert recovered.succeeded == 1
    assert len(adapter.calls) == 1
    assert session.scalar(select(func.count()).select_from(InvoiceReference)) == 1
    session.refresh(delivery)
    assert delivery.state == ProjectionDeliveryState.SUCCEEDED


def test_billing_consumer_retries_transient_failure_then_dead_letters_at_bound(
    session: Session,
    tenant: Tenant,
) -> None:
    _statement(session, tenant)
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    adapter = RecordingAdapter(transient_failures=10)
    consumer = BillingProviderConsumer(factory, adapter, _settings(max_attempts=2), worker_id="billing-worker")

    first = consumer.drain_once()
    delivery = session.scalar(select(ProjectionDelivery))
    assert delivery is not None
    assert first.retried == 1
    assert delivery.state == ProjectionDeliveryState.RETRY
    delivery.available_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()

    second = consumer.drain_once()

    assert second.dead == 1
    assert len(adapter.calls) == 2
    completed_delivery = session.get(ProjectionDelivery, delivery.id, populate_existing=True)
    assert completed_delivery is not None
    assert completed_delivery.state == ProjectionDeliveryState.DEAD
    assert "temporarily unavailable" in str(completed_delivery.last_error)
    assert session.scalar(select(func.count()).select_from(InvoiceReference)) == 0
    assert (
        session.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "commercial.billing_delivery_dead.v1"))
        is not None
    )
    assert session.scalar(select(AuditEvent).where(AuditEvent.action == "commercial.billing_delivery.dead")) is not None

    assert consumer.retry_dead(tenant.id) == 1
    replayed = session.get(ProjectionDelivery, delivery.id, populate_existing=True)
    assert replayed is not None
    assert replayed.state == ProjectionDeliveryState.RETRY
    assert (
        session.scalar(select(AuditEvent).where(AuditEvent.action == "commercial.billing_delivery.replay")) is not None
    )
