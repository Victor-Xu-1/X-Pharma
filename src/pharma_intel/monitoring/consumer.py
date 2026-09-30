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
from sqlalchemy.orm import Session, selectinload

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    AuditEvent,
    Entity,
    EvidenceClaim,
    KnowledgePage,
    MonitoringAlert,
    MonitoringTopic,
    OutboxEvent,
    ProjectionDelivery,
    ProjectionDeliveryState,
    SavedSearch,
    SavedSearchVersion,
    SavedSearchVisibility,
    Tenant,
)
from pharma_intel.operational_metrics import operational_metrics
from pharma_intel.repository import normalize_name
from pharma_intel.schemas import (
    ClinicalTrialSavedSearchQuery,
    DealSavedSearchQuery,
    EpidemiologySavedSearchQuery,
    NewsSavedSearchQuery,
    PatentSavedSearchQuery,
    PipelineSavedSearchQuery,
    RegulatorySavedSearchQuery,
)

logger = structlog.get_logger(__name__)
CONSUMER_NAME = "monitoring-v1"
SUPPORTED_EVENT_TYPES = (
    "canonical.entity.upserted",
    "governance.fact.published",
    "knowledge.page.compiled",
)


@dataclass(frozen=True)
class ClaimedMonitoringEvent:
    delivery_id: str
    event_id: str
    tenant_id: str
    aggregate_id: str
    event_type: str
    created_at: datetime
    attempts: int


@dataclass(frozen=True)
class MonitoringBatchResult:
    processed: int
    succeeded: int
    retried: int
    dead: int


def entity_matches_saved_search_version(entity: Entity, saved_search_version: SavedSearchVersion) -> bool:
    if saved_search_version.query_type != "entity_search" or saved_search_version.version < 1:
        raise ValueError(
            f"Unsupported saved search contract: {saved_search_version.query_type}@{saved_search_version.version}"
        )
    query = saved_search_version.query_json
    entity_type = query.get("entity_type")
    if entity_type and entity.entity_type.value != entity_type:
        return False
    entity_types = query.get("entity_types")
    if isinstance(entity_types, list) and entity_types and entity.entity_type.value not in entity_types:
        return False
    raw_query = query.get("q")
    if not raw_query:
        return True
    term = normalize_name(str(raw_query))
    searchable = [entity.normalized_name]
    searchable.extend(alias.normalized_alias for alias in entity.aliases)
    searchable.extend(normalize_name(str(value)) for value in entity.external_ids.values())
    return any(term in value for value in searchable)


def saved_search_matches_entity(
    session: Session,
    tenant_id: str,
    entity: Entity,
    saved_search_version: SavedSearchVersion,
) -> bool:
    if saved_search_version.query_type == "entity_search":
        return entity_matches_saved_search_version(entity, saved_search_version)
    if saved_search_version.query_type == "pipeline_search" and saved_search_version.version >= 1:
        pipeline_query = PipelineSavedSearchQuery.model_validate(saved_search_version.query_json)
        return IntelligenceService(session, tenant_id).program_saved_search_matches_entity(entity.id, pipeline_query)
    if saved_search_version.query_type == "clinical_trial_search" and saved_search_version.version >= 1:
        trial_query = ClinicalTrialSavedSearchQuery.model_validate(saved_search_version.query_json)
        return IntelligenceService(session, tenant_id).clinical_trial_saved_search_matches_entity(
            entity.id,
            trial_query,
        )
    if saved_search_version.query_type == "patent_search" and saved_search_version.version >= 1:
        patent_query = PatentSavedSearchQuery.model_validate(saved_search_version.query_json)
        return IntelligenceService(session, tenant_id).patent_saved_search_matches_entity(entity.id, patent_query)
    if saved_search_version.query_type == "deal_search" and saved_search_version.version >= 1:
        deal_query = DealSavedSearchQuery.model_validate(saved_search_version.query_json)
        return IntelligenceService(session, tenant_id).deal_saved_search_matches_entity(entity.id, deal_query)
    if saved_search_version.query_type == "regulatory_search" and saved_search_version.version >= 1:
        regulatory_query = RegulatorySavedSearchQuery.model_validate(saved_search_version.query_json)
        return IntelligenceService(session, tenant_id).regulatory_saved_search_matches_entity(
            entity.id,
            regulatory_query,
        )
    if saved_search_version.query_type == "epidemiology_search" and saved_search_version.version >= 1:
        epidemiology_query = EpidemiologySavedSearchQuery.model_validate(saved_search_version.query_json)
        return IntelligenceService(session, tenant_id).epidemiology_saved_search_matches_entity(
            entity.id,
            epidemiology_query,
        )
    if saved_search_version.query_type == "news_search" and saved_search_version.version >= 1:
        news_query = NewsSavedSearchQuery.model_validate(saved_search_version.query_json)
        return IntelligenceService(session, tenant_id).news_saved_search_matches_entity(entity.id, news_query)
    raise ValueError(
        f"Unsupported saved search contract: {saved_search_version.query_type}@{saved_search_version.version}"
    )


class MonitoringConsumer:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4()}"

    def drain_once(self, batch_size: int | None = None) -> MonitoringBatchResult:
        remaining = batch_size or self.settings.monitoring_batch_size
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
                    self._project(claimed)
                except Exception as exc:
                    is_dead = self._mark_failed(claimed, exc)
                    operational_metrics().record_projection(
                        "monitoring", "dead" if is_dead else "retry", time.perf_counter() - started
                    )
                    dead += int(is_dead)
                    retried += int(not is_dead)
                    logger.warning(
                        "monitoring_delivery_failed",
                        event_id=claimed.event_id,
                        attempts=claimed.attempts,
                        dead=is_dead,
                        error=str(exc),
                    )
                else:
                    self._mark_succeeded(claimed)
                    operational_metrics().record_projection("monitoring", "succeeded", time.perf_counter() - started)
                    succeeded += 1
                if remaining <= 0:
                    break
        return MonitoringBatchResult(processed, succeeded, retried, dead)

    def drain(self, max_batches: int = 1000) -> MonitoringBatchResult:
        total = MonitoringBatchResult(0, 0, 0, 0)
        for _ in range(max_batches):
            current = self.drain_once()
            total = MonitoringBatchResult(
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
        for current_tenant_id in [tenant_id] if tenant_id else self._tenant_ids():
            tenant_reset = 0
            with self.session_factory() as session:
                set_tenant_context(session, current_tenant_id)
                deliveries = session.scalars(
                    select(ProjectionDelivery)
                    .where(
                        ProjectionDelivery.tenant_id == current_tenant_id,
                        ProjectionDelivery.consumer_name == CONSUMER_NAME,
                        ProjectionDelivery.state == ProjectionDeliveryState.DEAD,
                    )
                    .with_for_update()
                )
                for delivery in deliveries:
                    delivery.state = ProjectionDeliveryState.RETRY
                    delivery.available_at = now
                    delivery.lease_expires_at = None
                    delivery.worker_id = None
                    delivery.last_error = f"operator replay after: {delivery.last_error or 'unknown failure'}"[:4000]
                    reset += 1
                    tenant_reset += 1
                if tenant_reset:
                    session.add(
                        AuditEvent(
                            tenant_id=current_tenant_id,
                            actor_type="system",
                            actor_id="monitoring-operator",
                            action="monitoring.delivery.replay",
                            resource_type="projection_delivery",
                            resource_id=None,
                            outcome="success",
                            request_id=str(uuid.uuid4()),
                            details={"count": tenant_reset},
                        )
                    )
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
            earliest_topic = session.scalar(
                select(func.min(MonitoringTopic.created_at)).where(MonitoringTopic.tenant_id == tenant_id)
            )
            if earliest_topic is None:
                return []
            return list(
                session.scalars(
                    select(OutboxEvent.id)
                    .outerjoin(ProjectionDelivery, delivery_match)
                    .where(
                        OutboxEvent.tenant_id == tenant_id,
                        OutboxEvent.event_type.in_(SUPPORTED_EVENT_TYPES),
                        OutboxEvent.created_at >= earliest_topic,
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
            )

    def _claim(self, tenant_id: str, event_id: str) -> ClaimedMonitoringEvent | None:
        now = datetime.now(UTC)
        lease_expires_at = now + timedelta(seconds=self.settings.monitoring_lease_seconds)
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
                retry_due = delivery.state == ProjectionDeliveryState.RETRY and _utc(delivery.available_at) <= now
                lease_expired = (
                    delivery.state == ProjectionDeliveryState.PROCESSING
                    and delivery.lease_expires_at is not None
                    and _utc(delivery.lease_expires_at) <= now
                )
                if not retry_due and not lease_expired:
                    return None
                delivery.state = ProjectionDeliveryState.PROCESSING
                delivery.attempts += 1
                delivery.lease_expires_at = lease_expires_at
                delivery.worker_id = self.worker_id
                delivery.last_error = None
            session.commit()
            return ClaimedMonitoringEvent(
                delivery.id,
                event.id,
                event.tenant_id,
                event.aggregate_id,
                event.event_type,
                _utc(event.created_at),
                delivery.attempts,
            )

    def _project(self, event: ClaimedMonitoringEvent) -> None:
        with self.session_factory() as session:
            set_tenant_context(session, event.tenant_id)
            entity_ids = self._affected_entity_ids(session, event)
            entities = session.scalars(
                select(Entity)
                .options(selectinload(Entity.aliases))
                .where(Entity.tenant_id == event.tenant_id, Entity.id.in_(entity_ids))
            )
            entities_by_id = {entity.id: entity for entity in entities}
            affected_entities = [entities_by_id[entity_id] for entity_id in entity_ids if entity_id in entities_by_id]
            if not affected_entities:
                return
            topics = session.execute(
                select(MonitoringTopic, SavedSearchVersion)
                .join(
                    SavedSearch,
                    and_(
                        SavedSearch.id == MonitoringTopic.saved_search_id,
                        SavedSearch.tenant_id == MonitoringTopic.tenant_id,
                    ),
                )
                .join(
                    SavedSearchVersion,
                    and_(
                        SavedSearchVersion.tenant_id == MonitoringTopic.tenant_id,
                        SavedSearchVersion.saved_search_id == MonitoringTopic.saved_search_id,
                        SavedSearchVersion.version == MonitoringTopic.query_version,
                    ),
                )
                .where(
                    MonitoringTopic.tenant_id == event.tenant_id,
                    MonitoringTopic.active.is_(True),
                    MonitoringTopic.created_at <= event.created_at,
                    or_(
                        SavedSearch.owner_user_id == MonitoringTopic.owner_user_id,
                        SavedSearch.visibility == SavedSearchVisibility.TENANT,
                    ),
                )
            )
            for topic, saved_search_version in topics:
                for entity in affected_entities:
                    if not saved_search_matches_entity(session, event.tenant_id, entity, saved_search_version):
                        continue
                    exists = session.scalar(
                        select(MonitoringAlert.id).where(
                            MonitoringAlert.tenant_id == event.tenant_id,
                            MonitoringAlert.topic_id == topic.id,
                            MonitoringAlert.source_outbox_event_id == event.event_id,
                        )
                    )
                    if exists is not None:
                        break
                    session.add(
                        MonitoringAlert(
                            tenant_id=event.tenant_id,
                            topic_id=topic.id,
                            recipient_user_id=topic.owner_user_id,
                            entity_id=entity.id,
                            source_outbox_event_id=event.event_id,
                            event_type=event.event_type,
                            title=f"{topic.name}: {entity.name} 数据已更新",
                            summary=f"{entity.entity_type.value} 实体 {entity.name} 匹配监控条件。",
                            payload_json={
                                "saved_search_id": saved_search_version.saved_search_id,
                                "query_version": saved_search_version.version,
                                "entity_type": entity.entity_type.value,
                            },
                        )
                    )
                    break
            session.commit()

    @staticmethod
    def _affected_entity_ids(session: Session, event: ClaimedMonitoringEvent) -> list[str]:
        if event.event_type == "canonical.entity.upserted":
            return [event.aggregate_id]
        if event.event_type == "governance.fact.published":
            claim = session.scalar(
                select(EvidenceClaim).where(
                    EvidenceClaim.tenant_id == event.tenant_id,
                    EvidenceClaim.id == event.aggregate_id,
                )
            )
            return list(
                dict.fromkeys(
                    entity_id
                    for entity_id in ([claim.subject_id, claim.object_id] if claim is not None else [])
                    if entity_id
                )
            )
        if event.event_type == "knowledge.page.compiled":
            page = session.scalar(
                select(KnowledgePage).where(
                    KnowledgePage.tenant_id == event.tenant_id,
                    KnowledgePage.id == event.aggregate_id,
                )
            )
            return [page.subject_entity_id] if page is not None and page.subject_entity_id else []
        raise ValueError(f"Unsupported monitoring event: {event.event_type}")

    def _mark_succeeded(self, event: ClaimedMonitoringEvent) -> None:
        self._complete(event, None)

    def _mark_failed(self, event: ClaimedMonitoringEvent, exc: Exception) -> bool:
        return self._complete(event, exc)

    def _complete(self, event: ClaimedMonitoringEvent, exc: Exception | None) -> bool:
        now = datetime.now(UTC)
        is_dead = exc is not None and event.attempts >= self.settings.monitoring_max_attempts
        backoff = min(
            self.settings.monitoring_retry_base_seconds * (2 ** max(event.attempts - 1, 0)),
            self.settings.monitoring_retry_max_seconds,
        )
        with self.session_factory() as session:
            set_tenant_context(session, event.tenant_id)
            delivery = session.scalar(
                select(ProjectionDelivery)
                .where(
                    ProjectionDelivery.id == event.delivery_id,
                    ProjectionDelivery.tenant_id == event.tenant_id,
                    ProjectionDelivery.worker_id == self.worker_id,
                    ProjectionDelivery.state == ProjectionDeliveryState.PROCESSING,
                )
                .with_for_update()
            )
            if delivery is None:
                raise RuntimeError("Monitoring delivery lease was lost")
            delivery.lease_expires_at = None
            if exc is None:
                delivery.state = ProjectionDeliveryState.SUCCEEDED
                delivery.processed_at = now
                delivery.last_error = None
            else:
                delivery.state = ProjectionDeliveryState.DEAD if is_dead else ProjectionDeliveryState.RETRY
                delivery.available_at = now if is_dead else now + timedelta(seconds=backoff)
                delivery.last_error = f"{type(exc).__name__}: {exc}"[:4000]
                if is_dead:
                    session.add(
                        AuditEvent(
                            tenant_id=event.tenant_id,
                            actor_type="system",
                            actor_id=self.worker_id,
                            action="monitoring.delivery.dead",
                            resource_type="projection_delivery",
                            resource_id=delivery.id,
                            outcome="failure",
                            request_id=event.event_id,
                            details={"attempts": event.attempts, "error": delivery.last_error},
                        )
                    )
            session.commit()
        return is_dead


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
