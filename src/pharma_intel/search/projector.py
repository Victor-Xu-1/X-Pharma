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

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    DataSource,
    EvidenceClaim,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
    RetrievalProjection,
    SourceAsset,
    SourceVersion,
    SourceVersionState,
    StageStatus,
    Tenant,
    TenantDataset,
)
from pharma_intel.object_store import ObjectStore
from pharma_intel.operational_metrics import operational_metrics
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.documents import (
    evidence_claim_projection,
    knowledge_page_projection,
    load_entity_projection,
    source_chunk_projections,
)
from pharma_intel.search.mappings import EVIDENCE_INDEX

logger = structlog.get_logger(__name__)

CONSUMER_NAME = "opensearch-v1"
SUPPORTED_EVENT_TYPES = (
    "canonical.entity.upserted",
    "governance.fact.published",
    "governance.fact.withdrawn",
    "knowledge.page.compiled",
    "source.version.parsed",
    "source.asset.deleted",
    "source.asset.reauthorized",
)


@dataclass(frozen=True)
class ClaimedEvent:
    delivery_id: str
    event_id: str
    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict[str, object]
    attempts: int


@dataclass(frozen=True)
class ProjectionBatchResult:
    processed: int
    succeeded: int
    retried: int
    dead: int


class SearchProjectionConsumer:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        gateway: OpenSearchGateway,
        object_store: ObjectStore,
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.gateway = gateway
        self.object_store = object_store
        self.settings = settings
        self.worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4()}"

    def drain_once(self, batch_size: int | None = None) -> ProjectionBatchResult:
        remaining = batch_size or self.settings.search_projection_batch_size
        succeeded = retried = dead = processed = 0
        for tenant_id in self._tenant_ids():
            if remaining <= 0:
                break
            candidate_ids = self._candidate_ids(tenant_id, remaining)
            for event_id in candidate_ids:
                claimed = self._claim(tenant_id, event_id)
                if claimed is None:
                    continue
                processed += 1
                remaining -= 1
                started = time.perf_counter()
                try:
                    self._project(claimed)
                except Exception as exc:
                    is_dead = self._mark_failed(claimed, exc)
                    operational_metrics().record_projection(
                        "opensearch",
                        "dead" if is_dead else "retry",
                        time.perf_counter() - started,
                    )
                    dead += int(is_dead)
                    retried += int(not is_dead)
                    logger.warning(
                        "search_projection_failed",
                        event_id=claimed.event_id,
                        event_type=claimed.event_type,
                        attempts=claimed.attempts,
                        dead=is_dead,
                        error=str(exc),
                    )
                else:
                    self._mark_succeeded(claimed)
                    operational_metrics().record_projection("opensearch", "succeeded", time.perf_counter() - started)
                    succeeded += 1
                if remaining <= 0:
                    break
        return ProjectionBatchResult(processed, succeeded, retried, dead)

    def drain(self, max_batches: int = 1000) -> ProjectionBatchResult:
        total = ProjectionBatchResult(0, 0, 0, 0)
        for _ in range(max_batches):
            current = self.drain_once()
            total = ProjectionBatchResult(
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
                set_tenant_context(session, tenant_id)
                rows = session.execute(
                    select(ProjectionDelivery.state, func.count())
                    .where(
                        ProjectionDelivery.tenant_id == tenant_id,
                        ProjectionDelivery.consumer_name == CONSUMER_NAME,
                    )
                    .group_by(ProjectionDelivery.state)
                )
                for state, count in rows:
                    counts[state.value] += int(count)
        return counts

    def retry_dead(self, tenant_id: str | None = None) -> int:
        now = datetime.now(UTC)
        reset = 0
        tenant_ids = [tenant_id] if tenant_id else self._tenant_ids()
        for current_tenant_id in tenant_ids:
            with self.session_factory() as session:
                set_tenant_context(session, current_tenant_id)
                deliveries = session.scalars(
                    select(ProjectionDelivery).where(
                        ProjectionDelivery.tenant_id == current_tenant_id,
                        ProjectionDelivery.consumer_name == CONSUMER_NAME,
                        ProjectionDelivery.state == ProjectionDeliveryState.DEAD,
                    )
                )
                for delivery in deliveries:
                    delivery.state = ProjectionDeliveryState.RETRY
                    delivery.available_at = now
                    delivery.lease_expires_at = None
                    delivery.worker_id = None
                    delivery.last_error = f"operator replay after: {delivery.last_error or 'unknown failure'}"[:4000]
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
            ProjectionDelivery.consumer_name == CONSUMER_NAME,
        )
        with self.session_factory() as session:
            set_tenant_context(session, tenant_id)
            statement = (
                select(OutboxEvent.id)
                .outerjoin(ProjectionDelivery, delivery_match)
                .where(
                    OutboxEvent.tenant_id == tenant_id,
                    OutboxEvent.event_type.in_(SUPPORTED_EVENT_TYPES),
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

    def _claim(self, tenant_id: str, event_id: str) -> ClaimedEvent | None:
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=self.settings.search_projection_lease_seconds)
        with self.session_factory() as session:
            set_tenant_context(session, tenant_id)
            event = session.scalar(
                select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id, OutboxEvent.id == event_id)
            )
            if event is None or event.event_type not in SUPPORTED_EVENT_TYPES:
                return None
            delivery = session.scalar(
                select(ProjectionDelivery)
                .where(
                    ProjectionDelivery.tenant_id == tenant_id,
                    ProjectionDelivery.consumer_name == CONSUMER_NAME,
                    ProjectionDelivery.outbox_event_id == event.id,
                )
                .with_for_update()
            )
            if delivery is None:
                delivery = ProjectionDelivery(
                    tenant_id=tenant_id,
                    consumer_name=CONSUMER_NAME,
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
            return ClaimedEvent(
                delivery.id,
                event.id,
                event.tenant_id,
                event.aggregate_type,
                event.aggregate_id,
                event.event_type,
                dict(event.payload),
                delivery.attempts,
            )

    def _project(self, event: ClaimedEvent) -> None:
        with self.session_factory() as session:
            set_tenant_context(session, event.tenant_id)
            if event.event_type == "canonical.entity.upserted":
                document = load_entity_projection(session, event.tenant_id, event.aggregate_id)
                if document is not None:
                    self.gateway.bulk_index([document])
                return
            if event.event_type == "source.version.parsed":
                source_version_id = str(event.payload.get("source_version_id") or event.aggregate_id)
                asset_id, documents = source_chunk_projections(
                    session,
                    self.object_store,
                    self.settings,
                    event.tenant_id,
                    source_version_id,
                )
                if asset_id is not None and documents:
                    self.gateway.replace_source_chunks(event.tenant_id, asset_id, source_version_id, documents)
                return
            if event.event_type == "source.asset.deleted":
                source_asset_id = str(event.payload.get("source_asset_id") or event.aggregate_id)
                self.gateway.delete_source_asset_evidence(event.tenant_id, source_asset_id)
                return
            if event.event_type == "source.asset.reauthorized":
                # Keep the withdrawal tombstone until a newly parsed version atomically replaces its chunks.
                return
            if event.event_type == "governance.fact.published":
                claim_id = str(event.payload.get("evidence_claim_id") or event.aggregate_id)
                claim = session.scalar(
                    select(EvidenceClaim).where(
                        EvidenceClaim.tenant_id == event.tenant_id,
                        EvidenceClaim.id == claim_id,
                    )
                )
                documents = []
                claim_document = evidence_claim_projection(session, event.tenant_id, claim_id)
                if claim_document is not None:
                    documents.append(claim_document)
                if claim is not None:
                    for entity_id in dict.fromkeys([claim.subject_id, claim.object_id]):
                        if entity_id:
                            entity_document = load_entity_projection(session, event.tenant_id, entity_id)
                            if entity_document is not None:
                                documents.append(entity_document)
                self.gateway.bulk_index(documents)
                return
            if event.event_type == "governance.fact.withdrawn":
                claim_id = str(event.payload.get("evidence_claim_id") or "")
                if not claim_id:
                    raise ValueError("Governance withdrawal event is missing evidence_claim_id")
                self.gateway.delete_evidence_claim(event.tenant_id, claim_id)
                return
            if event.event_type == "knowledge.page.compiled":
                page_id = str(event.payload.get("knowledge_page_id") or event.aggregate_id)
                document = knowledge_page_projection(session, event.tenant_id, page_id)
                if document is not None:
                    self.gateway.bulk_index([document])
                return
        raise ValueError(f"Unsupported search projection event: {event.event_type}")

    def _mark_succeeded(self, event: ClaimedEvent) -> None:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            set_tenant_context(session, event.tenant_id)
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
                raise RuntimeError("Projection delivery lease was lost before success could be recorded")
            delivery.state = ProjectionDeliveryState.SUCCEEDED
            delivery.processed_at = now
            delivery.lease_expires_at = None
            delivery.last_error = None
            if event.event_type == "source.version.parsed":
                self._record_source_projection(session, event, now, succeeded=True)
            session.commit()

    def _mark_failed(self, event: ClaimedEvent, exc: Exception) -> bool:
        now = datetime.now(UTC)
        is_dead = event.attempts >= self.settings.search_projection_max_attempts
        backoff = min(
            self.settings.search_projection_retry_base_seconds * (2 ** max(event.attempts - 1, 0)),
            self.settings.search_projection_retry_max_seconds,
        )
        with self.session_factory() as session:
            set_tenant_context(session, event.tenant_id)
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
                raise RuntimeError("Projection delivery lease was lost before failure could be recorded")
            delivery.state = ProjectionDeliveryState.DEAD if is_dead else ProjectionDeliveryState.RETRY
            delivery.available_at = now if is_dead else now + timedelta(seconds=backoff)
            delivery.lease_expires_at = None
            delivery.last_error = f"{type(exc).__name__}: {exc}"[:4000]
            if event.event_type == "source.version.parsed":
                self._record_source_projection(session, event, now, succeeded=False)
            session.commit()
        return is_dead

    def _record_source_projection(
        self,
        session: Session,
        event: ClaimedEvent,
        now: datetime,
        *,
        succeeded: bool,
    ) -> None:
        source_version_id = str(event.payload.get("source_version_id") or event.aggregate_id)
        version = session.scalar(
            select(SourceVersion).where(
                SourceVersion.tenant_id == event.tenant_id,
                SourceVersion.id == source_version_id,
            )
        )
        if version is None:
            return
        version.retrieval_status = StageStatus.SUCCEEDED if succeeded else StageStatus.FAILED
        if succeeded and version.state == SourceVersionState.PARSED:
            version.state = SourceVersionState.INDEXED
        metadata = dict(version.metadata_json)
        metadata["retrieval_projection"] = {
            "engine": "opensearch",
            "status": "succeeded" if succeeded else "retry_pending",
            "outbox_event_id": event.event_id,
            "updated_at": now.isoformat(),
        }
        version.metadata_json = metadata
        asset = session.scalar(
            select(SourceAsset).where(
                SourceAsset.tenant_id == event.tenant_id,
                SourceAsset.id == version.source_asset_id,
            )
        )
        if asset is None or version.source_document_id is None:
            return
        data_source = session.scalar(
            select(DataSource).where(
                DataSource.tenant_id == event.tenant_id,
                DataSource.id == asset.data_source_id,
            )
        )
        if data_source is None:
            return
        dataset = session.scalar(
            select(TenantDataset).where(
                TenantDataset.tenant_id == event.tenant_id,
                TenantDataset.dataset_key == data_source.dataset_key,
                TenantDataset.active.is_(True),
            )
        )
        if dataset is None:
            return
        projection = session.scalar(
            select(RetrievalProjection).where(
                RetrievalProjection.tenant_id == event.tenant_id,
                RetrievalProjection.source_document_id == version.source_document_id,
                RetrievalProjection.tenant_dataset_id == dataset.id,
                RetrievalProjection.engine == "opensearch",
            )
        )
        if projection is None:
            projection = RetrievalProjection(
                tenant_id=event.tenant_id,
                source_document_id=version.source_document_id,
                tenant_dataset_id=dataset.id,
                engine="opensearch",
                external_dataset_id=self.gateway.read_alias(EVIDENCE_INDEX),
            )
            session.add(projection)
            session.flush()
        projection.external_document_id = version.id
        projection.status = StageStatus.SUCCEEDED if succeeded else StageStatus.FAILED
        projection.progress = 1.0 if succeeded else 0.0
        projection.last_error = None if succeeded else "Projection delivery is awaiting a bounded retry"
        projection.last_reconciled_at = now
        version.retrieval_projection_id = projection.id


def _timestamp(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
