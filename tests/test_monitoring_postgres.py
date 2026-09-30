from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    EntityType,
    MonitoringAlert,
    MonitoringAlertReceipt,
    MonitoringTopic,
    SavedSearchVersion,
    SavedSearchVisibility,
    Tenant,
    User,
    UserRole,
)
from pharma_intel.monitoring.consumer import MonitoringConsumer
from pharma_intel.monitoring.service import MonitoringService
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate, EntitySearchQuery, SavedSearchCreate, SavedSearchUpdate
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.mark.integration
def test_monitoring_delivery_is_concurrent_idempotent_rls_isolated_and_alerts_are_immutable() -> None:
    database_url = os.getenv("TEST_MONITORING_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_MONITORING_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_MONITORING_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"monitoring-{tenant_id}", name="Monitoring PostgreSQL")
        user = User(
            tenant_id=tenant_id,
            email=f"monitoring-{tenant_id}@example.test",
            normalized_email=f"monitoring-{tenant_id}@example.test",
            display_name="Monitoring Owner",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ANALYST,
        )
        session.add_all([tenant, user])
        session.commit()
        service = MonitoringService(session, tenant_id, user.id)
        saved = service.create_saved_search(SavedSearchCreate(name="BRAF", query=EntitySearchQuery(q="BRAF")))
        service.create_topic("BRAF changes", saved.id)
        EntityRepository(session, tenant_id).create(EntityCreate(entity_type=EntityType.TARGET, name="BRAF"))

    consumers = [
        MonitoringConsumer(factory, Settings(), worker_id=f"postgres-monitoring-{index}") for index in range(2)
    ]
    barrier = threading.Barrier(2)

    def drain(consumer: MonitoringConsumer) -> int:
        barrier.wait(timeout=10)
        return consumer.drain_once().succeeded

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(drain, consumers))
    assert sum(outcomes) == 1

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        alert = session.scalar(select(MonitoringAlert))
        assert alert is not None
        assert session.scalar(select(func.count()).select_from(MonitoringAlert)) == 1
        receipt = MonitoringAlertReceipt(
            tenant_id=tenant_id,
            alert_id=alert.id,
            user_id=alert.recipient_user_id,
            read_at=datetime.now(UTC),
        )
        session.add(receipt)
        session.commit()
        session.execute(text("UPDATE monitoring_alert_receipts SET read_at = now() WHERE id = :id"), {"id": receipt.id})
        session.commit()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("UPDATE monitoring_alerts SET title = 'tampered' WHERE id = :id"), {"id": alert.id})
            session.commit()
        session.rollback()
        saved_version = session.scalar(select(SavedSearchVersion))
        assert saved_version is not None
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(
                text("UPDATE saved_search_versions SET query_type = 'tampered' WHERE id = :id"),
                {"id": saved_version.id},
            )
            session.commit()
        session.rollback()

        set_tenant_context(session, other_tenant_id)
        other = Tenant(id=other_tenant_id, slug=f"monitoring-{other_tenant_id}", name="Other tenant")
        session.add(other)
        session.commit()
        assert session.scalar(select(func.count()).select_from(MonitoringAlert)) == 0
    engine.dispose()


@pytest.mark.integration
def test_shared_monitoring_revocation_stops_cross_owner_delivery() -> None:
    database_url = os.getenv("TEST_MONITORING_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_MONITORING_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_MONITORING_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = str(uuid.uuid4())

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"monitoring-revoke-{tenant_id}", name="Monitoring Revocation")
        owner = User(
            tenant_id=tenant_id,
            email=f"monitoring-owner-{tenant_id}@example.test",
            normalized_email=f"monitoring-owner-{tenant_id}@example.test",
            display_name="Monitoring Owner",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ANALYST,
        )
        colleague = User(
            tenant_id=tenant_id,
            email=f"monitoring-colleague-{tenant_id}@example.test",
            normalized_email=f"monitoring-colleague-{tenant_id}@example.test",
            display_name="Monitoring Colleague",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ANALYST,
        )
        session.add_all([tenant, owner, colleague])
        session.commit()
        owner_service = MonitoringService(session, tenant_id, owner.id)
        saved = owner_service.create_saved_search(
            SavedSearchCreate(
                name="Shared KRAS",
                query=EntitySearchQuery(q="KRAS"),
                visibility=SavedSearchVisibility.TENANT,
            )
        )
        colleague_service = MonitoringService(session, tenant_id, colleague.id)
        topic = colleague_service.create_topic("Shared KRAS changes", saved.id)

        owner_service.update_saved_search(
            saved.id,
            SavedSearchUpdate(visibility=SavedSearchVisibility.PRIVATE),
        )
        session.refresh(topic)
        assert topic.active is False

        # Simulate stale state from an older deployment; the consumer must still enforce current visibility.
        session.execute(
            text("UPDATE monitoring_topics SET active = true WHERE id = :topic_id"),
            {"topic_id": topic.id},
        )
        session.commit()
        EntityRepository(session, tenant_id).create(EntityCreate(entity_type=EntityType.TARGET, name="KRAS"))

    result = MonitoringConsumer(factory, Settings(), worker_id="postgres-revocation").drain()

    assert result.succeeded == 1
    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        assert session.scalar(select(func.count()).select_from(MonitoringAlert)) == 0
        assert session.scalar(select(MonitoringTopic.active).where(MonitoringTopic.id == topic.id)) is True
    engine.dispose()
