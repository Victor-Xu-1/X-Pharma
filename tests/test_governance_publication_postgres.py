from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.db import set_tenant_context
from pharma_intel.governance.publication import GovernancePublicationService
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    EvidenceClaim,
    ExtractionRun,
    FactWithdrawalTombstone,
    GovernancePublicationBatch,
    GovernanceStatus,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    StagedFact,
    Tenant,
    User,
    UserRole,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.search.maintenance import ProjectionMaintenanceError, ProjectionMaintenanceService
from tests.support.postgres_safety import require_disposable_postgres_url

pytestmark = pytest.mark.integration


def _seed_claims(session: Session, tenant_id: str, reviewer_id: str) -> list[StagedFact]:
    source = DataSource(
        tenant_id=tenant_id,
        name="PostgreSQL publication acceptance",
        source_type=DataSourceType.FOLDER,
        root_uri="/publication-acceptance",
        owner="Data Governance",
        authorization_scopes=["contract:publication-acceptance"],
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    digest = hashlib.sha256(tenant_id.encode()).hexdigest()
    asset = SourceAsset(
        tenant_id=tenant_id,
        data_source_id=source.id,
        logical_path="publication.md",
        source_uri="file:///publication-acceptance/publication.md",
        file_name="publication.md",
        extension=".md",
        processing_mode="parse",
    )
    document = SourceDocument(
        tenant_id=tenant_id,
        title="PostgreSQL publication acceptance",
        source_type="folder",
        source_uri=asset.source_uri,
        content_sha256=digest,
    )
    session.add_all([asset, document])
    session.flush()
    version = SourceVersion(
        tenant_id=tenant_id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=digest,
        size_bytes=1024,
        source_document_id=document.id,
    )
    session.add(version)
    session.flush()
    extraction = ExtractionRun(
        tenant_id=tenant_id,
        source_version_id=version.id,
        schema_name="pharma_document_facts",
        schema_version="2.12.0",
        model_provider="postgres-acceptance",
        model_name="postgres-acceptance",
        prompt_sha256="a" * 64,
        policy_sha256="b" * 64,
        input_sha256="c" * 64,
        status=RunState.SUCCEEDED,
    )
    session.add(extraction)
    session.flush()
    facts: list[StagedFact] = []
    for index in range(2):
        fact = StagedFact(
            tenant_id=tenant_id,
            extraction_run_id=extraction.id,
            fact_kind="claim",
            fact_key=f"postgres-publication-{index}",
            raw_payload={"value": index},
            payload={
                "subject": {"entity_type": "target", "name": "PostgreSQL EGFR"},
                "predicate": f"has_postgres_marker_{index}",
                "value": {"index": index},
            },
            source_document_id=document.id,
            source_locator=f"page={index + 1}",
            source_quote=f"PostgreSQL publication evidence {index}",
            confidence=0.95,
            status=GovernanceStatus.REVIEW_PENDING,
        )
        session.add(fact)
        session.flush()
        session.add(
            ReviewTask(
                tenant_id=tenant_id,
                staged_fact_id=fact.id,
                status=GovernanceStatus.REVIEW_PENDING,
                assigned_user_id=reviewer_id,
                reasons=[{"code": "human_review_required"}],
            )
        )
        facts.append(fact)
    session.commit()
    return facts


def test_publication_is_atomic_tenant_scoped_append_only_and_globally_exclusive(tmp_path: Path) -> None:
    database_url = os.getenv("TEST_GOVERNANCE_PUBLICATION_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_GOVERNANCE_PUBLICATION_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_GOVERNANCE_PUBLICATION_DATABASE_URL")

    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    batch_id = ""
    tombstone_id = ""
    try:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            tenant = Tenant(id=tenant_id, slug=f"publication-{tenant_id}", name="Publication acceptance")
            reviewer = User(
                tenant_id=tenant_id,
                email=f"publication-{tenant_id}@example.test",
                normalized_email=f"publication-{tenant_id}@example.test",
                display_name="Publication reviewer",
                password_hash="not-used",  # noqa: S106
                role=UserRole.ADMIN,
            )
            session.add_all([tenant, reviewer])
            session.commit()
            facts = _seed_claims(session, tenant_id, reviewer.id)
            settings = Settings(
                object_store_root=tmp_path / "objects",
                search_allow_global_rebuild=False,
            )
            service = GovernancePublicationService(
                session,
                settings,
                FileSystemObjectStore(settings.object_store_root),
                tenant_id,
            )
            publication = service.preview(
                operation="publish",
                staged_fact_ids=[fact.id for fact in facts],
                idempotency_key="postgres-publication",
                user_id=reviewer.id,
                reason="Both citations verified against the source",
            )
            service.commit(publication.id, publication.preview_sha256, reviewer.id)
            assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 2

            withdrawal = service.preview(
                operation="withdraw",
                staged_fact_ids=[fact.id for fact in facts],
                idempotency_key="postgres-withdrawal",
                user_id=reviewer.id,
                reason="The source publisher issued a formal correction",
            )
            service.commit(withdrawal.id, withdrawal.preview_sha256, reviewer.id)
            batch_id = withdrawal.id
            tombstone_id = session.scalar(select(FactWithdrawalTombstone.id)) or ""
            assert tombstone_id
            assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 0
            assert session.scalar(select(func.count()).select_from(FactWithdrawalTombstone)) == 2
            stored_facts = [session.get(StagedFact, fact.id) for fact in facts]
            assert all(fact is not None for fact in stored_facts)
            assert {fact.status for fact in stored_facts if fact is not None} == {GovernanceStatus.WITHDRAWN}

            with pytest.raises(DBAPIError, match="append-only"):
                session.execute(
                    update(FactWithdrawalTombstone)
                    .where(FactWithdrawalTombstone.id == tombstone_id)
                    .values(reason="tampered")
                )
                session.commit()
            session.rollback()

            maintenance = ProjectionMaintenanceService(session, settings, tenant_id)
            maintenance.request("consistency_check", reviewer.id, "postgres-maintenance")

        with Session(engine, expire_on_commit=False) as other_session:
            set_tenant_context(other_session, other_tenant_id)
            other_tenant = Tenant(
                id=other_tenant_id,
                slug=f"publication-{other_tenant_id}",
                name="Other publication tenant",
            )
            other_reviewer = User(
                tenant_id=other_tenant_id,
                email=f"publication-{other_tenant_id}@example.test",
                normalized_email=f"publication-{other_tenant_id}@example.test",
                display_name="Other publication reviewer",
                password_hash="not-used",  # noqa: S106
                role=UserRole.ADMIN,
            )
            other_session.add_all([other_tenant, other_reviewer])
            other_session.commit()
            assert other_session.get(GovernancePublicationBatch, batch_id) is None
            assert other_session.get(FactWithdrawalTombstone, tombstone_id) is None
            with pytest.raises(ProjectionMaintenanceError, match="already active"):
                ProjectionMaintenanceService(other_session, settings, other_tenant_id).request(
                    "consistency_check",
                    other_reviewer.id,
                    "postgres-maintenance-conflict",
                )

        with engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT set_config('app.tenant_id', :tenant_id, true), "
                    "set_config('app.tenant_signature', 'forged', true)"
                ),
                {"tenant_id": tenant_id},
            )
            assert connection.scalar(text("SELECT public.app_current_tenant_id()")) is None
            assert connection.scalar(select(func.count()).select_from(FactWithdrawalTombstone)) == 0
    finally:
        engine.dispose()
