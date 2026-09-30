from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    DealProfile,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    Relationship,
    Tenant,
)
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.mark.integration
def test_company_timeline_uses_postgresql_union_and_runtime_rls() -> None:
    database_url = os.getenv("TEST_COMPANY_TIMELINE_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_COMPANY_TIMELINE_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_COMPANY_TIMELINE_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    company_id = str(uuid.uuid4())
    drug_id = str(uuid.uuid4())
    deal_entity_id = str(uuid.uuid4())

    try:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            session.add(Tenant(id=tenant_id, slug=f"company-{tenant_id}", name="Company Timeline PostgreSQL"))
            session.flush()
            session.add_all(
                [
                    Entity(
                        id=company_id,
                        tenant_id=tenant_id,
                        entity_type=EntityType.ORGANIZATION,
                        name="Victor Therapeutics",
                        normalized_name="victor therapeutics",
                    ),
                    Entity(
                        id=drug_id,
                        tenant_id=tenant_id,
                        entity_type=EntityType.DRUG,
                        name="VX-101",
                        normalized_name="vx-101",
                    ),
                    Entity(
                        id=deal_entity_id,
                        tenant_id=tenant_id,
                        entity_type=EntityType.TRANSACTION,
                        name="VX-101 license",
                        normalized_name="vx-101 license",
                    ),
                ]
            )
            session.flush()
            session.add(
                DevelopmentProgram(
                    tenant_id=tenant_id,
                    drug_entity_id=drug_id,
                    organization_entity_id=company_id,
                    phase=DevelopmentPhase.PHASE_1,
                    status_date=datetime(2026, 1, 1, tzinfo=UTC),
                )
            )
            deal = DealProfile(
                tenant_id=tenant_id,
                entity_id=deal_entity_id,
                deal_type="license",
                announced_at=datetime(2026, 2, 1, tzinfo=UTC),
                parties=[{"entity_id": company_id, "name": "Victor Therapeutics", "entity_type": "organization"}],
                asset_entity_ids=[drug_id],
                terms={},
            )
            session.add(deal)
            session.flush()
            session.add_all(
                [
                    Relationship(
                        tenant_id=tenant_id,
                        subject_id=deal_entity_id,
                        predicate="deal_party",
                        object_id=company_id,
                    ),
                    Relationship(
                        tenant_id=tenant_id,
                        subject_id=deal_entity_id,
                        predicate="deal_asset",
                        object_id=drug_id,
                    ),
                ]
            )
            session.commit()

            result = IntelligenceService(session, tenant_id).company_timeline(company_id, 50, 0)

            assert result is not None
            assert result.total == 2
            assert [item.event_type for item in result.items] == ["deal_announced", "program_status"]
            assert result.items[0].deal is not None
            assert result.items[0].deal.name == "VX-101 license"
            assert result.items[1].program is not None
            assert result.items[1].program.drug_name == "VX-101"
    finally:
        engine.dispose()
