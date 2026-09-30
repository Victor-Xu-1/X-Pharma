from __future__ import annotations

import socket
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.commercial.accounting import CommercialAccountingService
from pharma_intel.commercial.billing import (
    BillingProviderAdapter,
    BillingProviderPermanentError,
    BillingStatementSigner,
    SignedBillingManifest,
)
from pharma_intel.commercial.billing_operations import (
    BILLING_CONSUMER_NAME,
    BILLING_STATEMENT_EVENT_TYPE,
    requeue_billing_delivery,
)
from pharma_intel.commercial.service import CommercialError
from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    AuditEvent,
    BillingAccount,
    BillingPeriodStatement,
    InvoiceReference,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
    Tenant,
)
from pharma_intel.operational_metrics import operational_metrics

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ClaimedBillingEvent:
    delivery_id: str
    event_id: str
    tenant_id: str
    statement_id: str
    attempts: int


@dataclass(frozen=True)
class BillingDeliveryBatchResult:
    processed: int
    succeeded: int
    retried: int
    dead: int


class BillingProviderConsumer:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        adapter: BillingProviderAdapter,
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.adapter = adapter
        self.settings = settings
        self.worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4()}"
        self.signer = BillingStatementSigner(
            settings.effective_billing_statement_signing_secret,
            key_id=settings.billing_statement_signing_key_id,
        )

    def drain_once(self, batch_size: int | None = None) -> BillingDeliveryBatchResult:
        remaining = batch_size or self.settings.billing_provider_batch_size
        processed = succeeded = retried = dead = 0
        for tenant_id in self._tenant_ids():
            if remaining <= 0:
                break
            for event_id in self._candidate_ids(tenant_id, remaining):
                claimed = self._claim(tenant_id, event_id)
                if claimed is None:
                    continue
                processed += 1
                remaining -= 1
                started = time.perf_counter()
                try:
                    self._deliver(claimed)
                except BillingProviderPermanentError as exc:
                    self._mark_failed(claimed, exc, permanent=True)
                    operational_metrics().record_projection("billing_provider", "dead", time.perf_counter() - started)
                    dead += 1
                    logger.error(
                        "billing_provider_delivery_dead",
                        event_id=claimed.event_id,
                        attempts=claimed.attempts,
                        error=str(exc),
                    )
                except Exception as exc:
                    is_dead = self._mark_failed(claimed, exc, permanent=False)
                    operational_metrics().record_projection(
                        "billing_provider",
                        "dead" if is_dead else "retry",
                        time.perf_counter() - started,
                    )
                    dead += int(is_dead)
                    retried += int(not is_dead)
                    logger.warning(
                        "billing_provider_delivery_failed",
                        event_id=claimed.event_id,
                        attempts=claimed.attempts,
                        dead=is_dead,
                        error=str(exc),
                    )
                else:
                    self._mark_succeeded(claimed)
                    operational_metrics().record_projection(
                        "billing_provider", "succeeded", time.perf_counter() - started
                    )
                    succeeded += 1
                if remaining <= 0:
                    break
        return BillingDeliveryBatchResult(processed, succeeded, retried, dead)

    def drain(self, max_batches: int = 1000) -> BillingDeliveryBatchResult:
        total = BillingDeliveryBatchResult(0, 0, 0, 0)
        for _ in range(max_batches):
            current = self.drain_once()
            total = BillingDeliveryBatchResult(
                total.processed + current.processed,
                total.succeeded + current.succeeded,
                total.retried + current.retried,
                total.dead + current.dead,
            )
            if current.processed == 0:
                break
        return total

    def delivery_counts(self) -> dict[str, int]:
        counts = {state.value: 0 for state in ProjectionDeliveryState}
        for tenant_id in self._tenant_ids():
            with self.session_factory() as session:
                self._set_tenant_context(session, tenant_id)
                rows = session.execute(
                    select(ProjectionDelivery.state, func.count())
                    .where(
                        ProjectionDelivery.tenant_id == tenant_id,
                        ProjectionDelivery.consumer_name == BILLING_CONSUMER_NAME,
                    )
                    .group_by(ProjectionDelivery.state)
                )
                for state, count in rows:
                    counts[state.value] += int(count)
        return counts

    def retry_dead(self, tenant_id: str | None = None) -> int:
        reset = 0
        for current_tenant_id in [tenant_id] if tenant_id else self._tenant_ids():
            with self.session_factory() as session:
                self._set_tenant_context(session, current_tenant_id)
                deliveries = session.scalars(
                    select(ProjectionDelivery).where(
                        ProjectionDelivery.tenant_id == current_tenant_id,
                        ProjectionDelivery.consumer_name == BILLING_CONSUMER_NAME,
                        ProjectionDelivery.state == ProjectionDeliveryState.DEAD,
                    )
                )
                for delivery in deliveries:
                    requeue_billing_delivery(
                        session,
                        delivery,
                        actor_type="operator",
                        actor_id="billing-provider-operator",
                        reason="billing worker bulk dead-letter replay",
                        request_id=f"billing-replay:{delivery.id}",
                    )
                    reset += 1
                session.commit()
        return reset

    def _tenant_ids(self) -> list[str]:
        with self.session_factory() as session:
            return list(session.scalars(select(Tenant.id).where(Tenant.active.is_(True)).order_by(Tenant.id)))

    def _candidate_ids(self, tenant_id: str, limit: int) -> list[str]:
        now = datetime.now(UTC)
        delivery_match = and_(
            ProjectionDelivery.outbox_event_id == OutboxEvent.id,
            ProjectionDelivery.consumer_name == BILLING_CONSUMER_NAME,
        )
        with self.session_factory() as session:
            self._set_tenant_context(session, tenant_id)
            statement = (
                select(OutboxEvent.id)
                .outerjoin(ProjectionDelivery, delivery_match)
                .where(
                    OutboxEvent.tenant_id == tenant_id,
                    OutboxEvent.event_type == BILLING_STATEMENT_EVENT_TYPE,
                    or_(
                        ProjectionDelivery.id.is_(None),
                        and_(
                            ProjectionDelivery.state == ProjectionDeliveryState.RETRY,
                            ProjectionDelivery.available_at <= now,
                        ),
                        and_(
                            ProjectionDelivery.state == ProjectionDeliveryState.PROCESSING,
                            ProjectionDelivery.lease_expires_at.is_not(None),
                            ProjectionDelivery.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(OutboxEvent.created_at, OutboxEvent.id)
                .limit(limit)
            )
            return list(session.scalars(statement))

    def _claim(self, tenant_id: str, event_id: str) -> ClaimedBillingEvent | None:
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=self.settings.billing_provider_lease_seconds)
        with self.session_factory() as session:
            self._set_tenant_context(session, tenant_id)
            event = session.scalar(
                select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id, OutboxEvent.id == event_id)
            )
            if event is None or event.event_type != BILLING_STATEMENT_EVENT_TYPE:
                return None
            delivery = session.scalar(
                select(ProjectionDelivery)
                .where(
                    ProjectionDelivery.tenant_id == tenant_id,
                    ProjectionDelivery.consumer_name == BILLING_CONSUMER_NAME,
                    ProjectionDelivery.outbox_event_id == event.id,
                )
                .with_for_update()
            )
            if delivery is None:
                delivery = ProjectionDelivery(
                    tenant_id=tenant_id,
                    consumer_name=BILLING_CONSUMER_NAME,
                    outbox_event_id=event.id,
                    state=ProjectionDeliveryState.PROCESSING,
                    attempts=1,
                    available_at=now,
                    lease_expires_at=lease_expires_at,
                    worker_id=self.worker_id,
                )
                session.add(delivery)
                try:
                    session.flush()
                except IntegrityError:
                    session.rollback()
                    return None
            else:
                retry_due = delivery.state == ProjectionDeliveryState.RETRY and _timestamp(delivery.available_at) <= now
                lease_expired = (
                    delivery.state == ProjectionDeliveryState.PROCESSING
                    and delivery.lease_expires_at is not None
                    and _timestamp(delivery.lease_expires_at) <= now
                )
                if not retry_due and not lease_expired:
                    return None
                delivery.state = ProjectionDeliveryState.PROCESSING
                delivery.attempts += 1
                delivery.lease_expires_at = lease_expires_at
                delivery.worker_id = self.worker_id
                delivery.last_error = None
            session.commit()
            return ClaimedBillingEvent(delivery.id, event.id, tenant_id, event.aggregate_id, delivery.attempts)

    def _deliver(self, event: ClaimedBillingEvent) -> None:
        with self.session_factory() as session:
            self._set_tenant_context(session, event.tenant_id)
            existing = session.scalar(
                select(InvoiceReference).where(
                    InvoiceReference.tenant_id == event.tenant_id,
                    InvoiceReference.statement_id == event.statement_id,
                )
            )
            if existing is not None:
                if existing.provider != self.settings.billing_provider_name:
                    raise BillingProviderPermanentError("Statement is bound to a different billing provider")
                return
            tenant = session.scalar(select(Tenant).where(Tenant.id == event.tenant_id))
            statement = session.scalar(
                select(BillingPeriodStatement).where(
                    BillingPeriodStatement.tenant_id == event.tenant_id,
                    BillingPeriodStatement.id == event.statement_id,
                )
            )
            if tenant is None or statement is None:
                raise BillingProviderPermanentError("Billing statement authority is unavailable")
            account = session.scalar(
                select(BillingAccount).where(
                    BillingAccount.tenant_id == event.tenant_id,
                    BillingAccount.id == statement.billing_account_id,
                )
            )
            if account is None or not account.external_customer_reference:
                raise BillingProviderPermanentError("Billing customer mapping is unavailable")
            manifest = SignedBillingManifest(
                payload=statement.payload_json,
                sha256=statement.manifest_sha256,
                key_id=statement.signature_key_id,
                signature=statement.manifest_signature,
            )
            if not self.signer.verify(manifest):
                raise BillingProviderPermanentError("Billing statement signature verification failed")
            receipt = self.adapter.create_invoice(
                manifest,
                idempotency_key=f"statement:{statement.id}:{statement.manifest_sha256[:16]}",
                customer_reference=account.external_customer_reference,
            )
            accounting = CommercialAccountingService(
                session,
                tenant,
                actor_id=f"billing-provider:{self.settings.billing_provider_name}",
                statement_signer=self.signer,
            )
            try:
                accounting.record_invoice(statement.id, receipt, request_id=f"billing:{event.event_id}")
            except (CommercialError, ValueError) as exc:
                raise BillingProviderPermanentError(
                    "Billing provider receipt conflicts with accounting authority"
                ) from exc

    def _mark_succeeded(self, event: ClaimedBillingEvent) -> None:
        with self.session_factory() as session:
            self._set_tenant_context(session, event.tenant_id)
            delivery = self._locked_delivery(session, event)
            delivery.state = ProjectionDeliveryState.SUCCEEDED
            delivery.processed_at = datetime.now(UTC)
            delivery.lease_expires_at = None
            delivery.last_error = None
            session.commit()

    def _mark_failed(self, event: ClaimedBillingEvent, exc: Exception, *, permanent: bool) -> bool:
        now = datetime.now(UTC)
        is_dead = permanent or event.attempts >= self.settings.billing_provider_max_attempts
        backoff = min(
            self.settings.billing_provider_retry_base_seconds * (2 ** max(event.attempts - 1, 0)),
            self.settings.billing_provider_retry_max_seconds,
        )
        with self.session_factory() as session:
            self._set_tenant_context(session, event.tenant_id)
            delivery = self._locked_delivery(session, event)
            delivery.state = ProjectionDeliveryState.DEAD if is_dead else ProjectionDeliveryState.RETRY
            delivery.available_at = now if is_dead else now + timedelta(seconds=backoff)
            delivery.lease_expires_at = None
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:4000]
            if is_dead:
                session.add_all(
                    [
                        AuditEvent(
                            tenant_id=event.tenant_id,
                            actor_type="service",
                            actor_id=self.worker_id,
                            action="commercial.billing_delivery.dead",
                            resource_type="projection_delivery",
                            resource_id=delivery.id,
                            outcome="failure",
                            request_id=f"billing-dead:{event.event_id}"[:100],
                            details={"event_id": event.event_id, "attempts": event.attempts},
                        ),
                        OutboxEvent(
                            tenant_id=event.tenant_id,
                            aggregate_type="billing_provider_delivery",
                            aggregate_id=delivery.id,
                            event_type="commercial.billing_delivery_dead.v1",
                            payload={"statement_id": event.statement_id, "attempts": event.attempts},
                        ),
                    ]
                )
            session.commit()
        return is_dead

    def _locked_delivery(self, session: Session, event: ClaimedBillingEvent) -> ProjectionDelivery:
        delivery = session.scalar(
            select(ProjectionDelivery)
            .where(
                ProjectionDelivery.tenant_id == event.tenant_id,
                ProjectionDelivery.id == event.delivery_id,
                ProjectionDelivery.worker_id == self.worker_id,
                ProjectionDelivery.state == ProjectionDeliveryState.PROCESSING,
            )
            .with_for_update()
        )
        if delivery is None:
            raise RuntimeError("Billing provider delivery lease was lost")
        return delivery

    def _set_tenant_context(self, session: Session, tenant_id: str) -> None:
        set_tenant_context(
            session,
            tenant_id,
            signing_secret=self.settings.effective_tenant_context_signing_secret,
        )


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
