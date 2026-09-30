from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import ActivityMeasurement, Assay, Entity, EntityType, MeasurementRelation, Tenant
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.mark.integration
def test_sar_comparison_uses_postgresql_window_ranking_under_runtime_rls() -> None:
    database_url = os.getenv("TEST_SAR_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_SAR_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_SAR_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    compound_a_id = str(uuid.uuid4())
    compound_b_id = str(uuid.uuid4())

    try:
        with Session(engine, expire_on_commit=False) as session:
            set_tenant_context(session, tenant_id)
            session.add(Tenant(id=tenant_id, slug=f"sar-{tenant_id}", name="SAR PostgreSQL"))
            session.flush()
            session.add_all(
                [
                    Entity(
                        id=target_id,
                        tenant_id=tenant_id,
                        entity_type=EntityType.TARGET,
                        name="EGFR",
                        normalized_name="egfr",
                    ),
                    Entity(
                        id=compound_a_id,
                        tenant_id=tenant_id,
                        entity_type=EntityType.DRUG,
                        name="Compound A",
                        normalized_name="compound a",
                    ),
                    Entity(
                        id=compound_b_id,
                        tenant_id=tenant_id,
                        entity_type=EntityType.DRUG,
                        name="Compound B",
                        normalized_name="compound b",
                    ),
                ]
            )
            session.flush()
            assay = Assay(
                tenant_id=tenant_id,
                source_system="postgres_acceptance",
                source_assay_id="binding-1",
                target_entity_id=target_id,
                assay_type="binding",
                assay_format="biochemical",
                organism="Homo sapiens",
            )
            session.add(assay)
            session.flush()
            for source_id, compound_id, pchembl in (
                ("activity-a", compound_a_id, 8.2),
                ("activity-b", compound_b_id, 7.1),
            ):
                session.add(
                    ActivityMeasurement(
                        tenant_id=tenant_id,
                        source_system="postgres_acceptance",
                        source_activity_id=source_id,
                        assay_id=assay.id,
                        compound_entity_id=compound_id,
                        target_entity_id=target_id,
                        reported_type="IC50",
                        reported_relation=MeasurementRelation.EQUAL,
                        reported_value="10",
                        reported_units="nM",
                        standard_type="IC50",
                        standard_relation=MeasurementRelation.EQUAL,
                        standard_value=10,
                        standard_units="nM",
                        pchembl_value=pchembl,
                    )
                )
            session.commit()

            result = IntelligenceService(session, tenant_id).sar_comparison(
                target_id,
                standard_type="IC50",
                assay_type="binding",
                assay_format="biochemical",
                organism="Homo sapiens",
                cell_line=None,
                limit=50,
                offset=0,
            )

            assert result.total == 2
            assert [(item.compound_name, item.potency_rank) for item in result.items] == [
                ("Compound A", 1),
                ("Compound B", 2),
            ]
            assert result.items[1].delta_pchembl == pytest.approx(-1.1)
    finally:
        engine.dispose()
