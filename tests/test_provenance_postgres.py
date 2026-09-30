from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    GovernanceStatus,
    ReviewStatus,
    RunState,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    StagedFact,
    Tenant,
)
from tests.support.postgres_safety import require_disposable_postgres_url

pytestmark = pytest.mark.integration


def test_fact_provenance_signed_tenant_rls_and_forged_context() -> None:
    database_url = os.getenv("TEST_PROVENANCE_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_PROVENANCE_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_PROVENANCE_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"provenance-{tenant_id}", name="Provenance PostgreSQL")
        session.add(tenant)
        session.flush()
        source = DataSource(
            tenant_id=tenant_id,
            name="Provenance PostgreSQL source",
            source_type=DataSourceType.FOLDER,
            root_uri=f"/provenance-postgres/{tenant_id}",
            owner="Research Operations",
            authorization_scopes=["contract:provenance-postgres"],
            dataset_key="literature",
        )
        subject = Entity(
            tenant_id=tenant_id,
            entity_type=EntityType.TARGET,
            name="EGFR PostgreSQL",
            normalized_name="egfr postgresql",
            review_status=ReviewStatus.VERIFIED,
        )
        session.add_all([source, subject])
        session.flush()
        asset = SourceAsset(
            tenant_id=tenant_id,
            data_source_id=source.id,
            logical_path="egfr.pdf",
            source_uri=f"file:///provenance-postgres/{tenant_id}/egfr.pdf",
            file_name="egfr.pdf",
            extension=".pdf",
            processing_mode="parse",
        )
        document = SourceDocument(
            tenant_id=tenant_id,
            title="EGFR PostgreSQL evidence",
            source_type="folder",
            source_uri=asset.source_uri,
            content_sha256="a" * 64,
        )
        session.add_all([asset, document])
        session.flush()
        version = SourceVersion(
            tenant_id=tenant_id,
            source_asset_id=asset.id,
            version_number=1,
            content_sha256="a" * 64,
            size_bytes=2048,
            source_document_id=document.id,
        )
        session.add(version)
        session.flush()
        extraction = ExtractionRun(
            tenant_id=tenant_id,
            source_version_id=version.id,
            schema_name="pharma_document_facts",
            schema_version="2.2.0",
            model_provider="postgres-test",
            model_name="postgres-test",
            prompt_sha256="b" * 64,
            policy_sha256="d" * 64,
            input_sha256="c" * 64,
            status=RunState.SUCCEEDED,
        )
        session.add(extraction)
        session.flush()
        staged = StagedFact(
            tenant_id=tenant_id,
            extraction_run_id=extraction.id,
            fact_kind="target_profile",
            fact_key="egfr-postgres-profile",
            raw_payload={"gene_symbol": "EGFR"},
            payload={"gene_symbol": "EGFR"},
            source_document_id=document.id,
            source_locator="page=9",
            source_quote="EGFR is a receptor tyrosine kinase.",
            confidence=0.99,
            status=GovernanceStatus.PUBLISHED,
        )
        session.add(staged)
        session.flush()
        claim = EvidenceClaim(
            tenant_id=tenant_id,
            subject_id=subject.id,
            predicate="has_target_profile",
            value={"gene_symbol": "EGFR"},
            source_document_id=document.id,
            source_locator=staged.source_locator,
            quote=staged.source_quote,
            confidence=staged.confidence,
            review_status=ReviewStatus.VERIFIED,
        )
        session.add(claim)
        session.flush()
        link = FactProvenanceLink(
            tenant_id=tenant_id,
            resource_type="target_profile",
            resource_id=str(uuid.uuid4()),
            staged_fact_id=staged.id,
            evidence_claim_id=claim.id,
            source_asset_id=asset.id,
            source_version_id=version.id,
            source_document_id=document.id,
            dataset_key=source.dataset_key,
            source_locator=staged.source_locator,
        )
        session.add(link)
        session.commit()
        link_id = link.id
        assert session.scalar(select(func.count()).select_from(FactProvenanceLink)) == 1

    with Session(engine) as session:
        set_tenant_context(session, other_tenant_id)
        session.add(Tenant(id=other_tenant_id, slug=f"provenance-{other_tenant_id}", name="Other Provenance"))
        session.commit()
        assert session.get(FactProvenanceLink, link_id) is None
        assert session.scalar(select(func.count()).select_from(FactProvenanceLink)) == 0

    with engine.connect() as connection:
        connection.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant_id, true), "
                "set_config('app.tenant_signature', 'forged', true)"
            ),
            {"tenant_id": tenant_id},
        )
        assert connection.scalar(text("SELECT public.app_current_tenant_id()")) is None
        assert connection.scalar(select(func.count()).select_from(FactProvenanceLink)) == 0
    engine.dispose()
