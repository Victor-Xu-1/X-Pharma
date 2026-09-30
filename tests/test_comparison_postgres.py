from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.comparison.exports import WorkspaceComparisonExportService
from pharma_intel.comparison.service import ComparisonSetConflict, ComparisonSetService
from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    ComparisonSet,
    ComparisonSetVersion,
    EntityType,
    Tenant,
    User,
    UserRole,
    WorkspaceExportEvent,
)
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import ComparisonSetCreate, EntityCreate, WorkspaceExportCreate, WorkspaceExportPolicyUpsert
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.mark.integration
def test_comparison_concurrency_rls_and_export_history_immutability() -> None:
    database_url = os.getenv("TEST_COMPARISON_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMPARISON_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_COMPARISON_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"comparison-{tenant_id}", name="Comparison PostgreSQL")
        user = User(
            tenant_id=tenant_id,
            email=f"comparison-{tenant_id}@example.test",
            normalized_email=f"comparison-{tenant_id}@example.test",
            display_name="Comparison Owner",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ADMIN,
        )
        session.add_all([tenant, user])
        session.commit()
        first = EntityRepository(session, tenant_id).create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
        second = EntityRepository(session, tenant_id).create(EntityCreate(entity_type=EntityType.TARGET, name="KRAS"))
        comparison = ComparisonSetService(session, tenant_id, user.id).create_set(ComparisonSetCreate(name="Landscape"))
        set_id = comparison.item.id
        user_id = user.id

    barrier = threading.Barrier(2)

    def add(entity_id: str) -> str:
        with factory() as session:
            set_tenant_context(session, tenant_id)
            barrier.wait(timeout=10)
            try:
                ComparisonSetService(session, tenant_id, user_id).add_member(set_id, entity_id, expected_version=1)
                return "added"
            except ComparisonSetConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(add, (first.id, second.id)))
    assert sorted(outcomes) == ["added", "conflict"]

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        comparison = ComparisonSetService(session, tenant_id, user_id).get_set(set_id)
        assert comparison.item.version == 2
        assert comparison.member_count == 1
        export_service = WorkspaceComparisonExportService(session, tenant_id, user_id)
        export_service.upsert_policy(
            WorkspaceExportPolicyUpsert(
                policy_version="postgres-v1",
                enabled=True,
                allowed_formats=["json"],
                allowed_fields=["id", "entity_type", "name"],
                max_records_per_export=20,
                attribution="PostgreSQL integration test",
            )
        )
        artifact = export_service.export_comparison_set(
            set_id,
            WorkspaceExportCreate(
                expected_version=2,
                export_format="json",
                fields=["id", "entity_type", "name"],
                idempotency_key="postgres-comparison-export-0001",
            ),
        )
        assert artifact.content_sha256
        version = session.scalar(select(ComparisonSetVersion).where(ComparisonSetVersion.comparison_set_id == set_id))
        event = session.scalar(select(WorkspaceExportEvent).where(WorkspaceExportEvent.comparison_set_id == set_id))
        assert version is not None and event is not None
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("UPDATE comparison_set_versions SET version = 99 WHERE id = :id"), {"id": version.id})
            session.commit()
        session.rollback()
        with pytest.raises(DBAPIError, match="append-only"):
            session.execute(text("DELETE FROM workspace_export_events WHERE id = :id"), {"id": event.id})
            session.commit()
        session.rollback()

        set_tenant_context(session, other_tenant_id)
        session.add(Tenant(id=other_tenant_id, slug=f"comparison-{other_tenant_id}", name="Other tenant"))
        session.commit()
        assert session.scalar(select(func.count()).select_from(ComparisonSet)) == 0
        assert session.scalar(select(func.count()).select_from(WorkspaceExportEvent)) == 0
    engine.dispose()
