from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.knowledge.search import search_published_knowledge
from pharma_intel.models import (
    DealAssetAssociation,
    DealProfile,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    Tenant,
)
from tests.support.postgres_safety import require_disposable_postgres_url
from tests.test_knowledge_search import _published_page


@pytest.mark.integration
def test_postgres_explicit_stages_and_paging_use_real_rls_and_persistence() -> None:
    value = os.getenv("TEST_RESEARCH_AUDIT_DATABASE_URL")
    if not value:
        pytest.skip("TEST_RESEARCH_AUDIT_DATABASE_URL is not configured")
    engine = create_engine(require_disposable_postgres_url(value, "TEST_RESEARCH_AUDIT_DATABASE_URL"))
    identifier = str(uuid.uuid4())
    other = str(uuid.uuid4())
    with Session(engine) as session:
        set_tenant_context(session, identifier)
        role = session.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")).one()
        assert not role.rolsuper and not role.rolbypassrls
        session.add_all(
            [
                Tenant(id=identifier, slug=f"audit-{identifier}", name="Audit fixture"),
                Tenant(id=other, slug=f"audit-{other}", name="Other fixture"),
            ]
        )
        session.flush()
        drug = Entity(tenant_id=identifier, entity_type=EntityType.DRUG, name="Test drug", normalized_name="test drug")
        session.add(drug)
        session.flush()
        program = DevelopmentProgram(
            tenant_id=identifier,
            drug_entity_id=drug.id,
            phase=DevelopmentPhase.EARLY_PHASE_1,
            global_phase="early_phase_1",
            china_phase="unknown",
        )
        session.add(program)
        deal_entity = Entity(
            tenant_id=identifier, entity_type=EntityType.TRANSACTION, name="Test deal", normalized_name="test deal"
        )
        session.add(deal_entity)
        session.flush()
        deal = DealProfile(tenant_id=identifier, entity_id=deal_entity.id, deal_type="license")
        session.add(deal)
        session.flush()
        asset = DealAssetAssociation(
            tenant_id=identifier,
            deal_id=deal.id,
            asset_entity_id=drug.id,
            development_phase_at_transaction="early_phase_1",
        )
        session.add(asset)
        for index in range(503):
            _published_page(session, identifier, f"Drug {index:04d}")
        session.commit()
        program_id = program.id
        set_tenant_context(session, identifier)
        page = search_published_knowledge(session, tenant_id=identifier, limit=50, offset=500)
        assert page.total == 503 and len(page.items) == 3 and page.items[0].title == "Drug 0500"
        assert (
            session.scalar(
                select(DealAssetAssociation.development_phase_at_transaction).where(DealAssetAssociation.id == asset.id)
            )
            == "early_phase_1"
        )
        assert (
            session.scalar(select(DevelopmentProgram.phase).where(DevelopmentProgram.id == program_id))
            == DevelopmentPhase.EARLY_PHASE_1
        )
        session.rollback()
        set_tenant_context(session, other)
        assert search_published_knowledge(session, tenant_id=other).total == 0
        assert session.scalar(select(DevelopmentProgram.id).where(DevelopmentProgram.id == program_id)) is None
    engine.dispose()
