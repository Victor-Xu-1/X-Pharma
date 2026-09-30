from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    CompoundStructure,
    Entity,
    EntityType,
    MeasurementRelation,
    ReviewStatus,
    Tenant,
)
from pharma_intel.security import Principal, require_principal


def _entity(session: Session, tenant: Tenant, entity_type: EntityType, name: str) -> Entity:
    entity = Entity(
        tenant_id=tenant.id,
        entity_type=entity_type,
        name=name,
        normalized_name=name.casefold(),
        review_status=ReviewStatus.VERIFIED,
    )
    session.add(entity)
    session.flush()
    return entity


def _activity(
    session: Session,
    tenant: Tenant,
    *,
    assay: Assay,
    compound: Entity,
    target: Entity,
    source_id: str,
    pchembl: float | None,
    relation: MeasurementRelation = MeasurementRelation.EQUAL,
) -> ActivityMeasurement:
    activity = ActivityMeasurement(
        tenant_id=tenant.id,
        source_system="governed_ai",
        source_activity_id=source_id,
        assay_id=assay.id,
        compound_entity_id=compound.id,
        target_entity_id=target.id,
        reported_type="IC50",
        reported_relation=relation,
        reported_value="10",
        reported_units="nM",
        standard_type="IC50",
        standard_relation=relation,
        standard_value=10,
        standard_units="nM",
        pchembl_value=pchembl,
    )
    session.add(activity)
    return activity


def _seed_sar_data(session: Session, tenant: Tenant) -> tuple[Entity, Entity, Entity]:
    target = _entity(session, tenant, EntityType.TARGET, "EGFR")
    compound_a = _entity(session, tenant, EntityType.DRUG, "Compound A")
    compound_b = _entity(session, tenant, EntityType.DRUG, "Compound B")
    compound_c = _entity(session, tenant, EntityType.DRUG, "Compound C")
    binding = Assay(
        tenant_id=tenant.id,
        source_system="governed_ai",
        source_assay_id="binding-1",
        target_entity_id=target.id,
        assay_type="binding",
        assay_format="biochemical",
        organism="Homo sapiens",
    )
    cellular = Assay(
        tenant_id=tenant.id,
        source_system="governed_ai",
        source_assay_id="cellular-1",
        target_entity_id=target.id,
        assay_type="functional",
        assay_format="cellular",
        organism="Homo sapiens",
        cell_line="A549",
    )
    incomplete = Assay(
        tenant_id=tenant.id,
        source_system="governed_ai",
        source_assay_id="incomplete-1",
        target_entity_id=target.id,
        assay_type=None,
        assay_format=None,
    )
    session.add_all([binding, cellular, incomplete])
    session.flush()
    _activity(session, tenant, assay=binding, compound=compound_a, target=target, source_id="a", pchembl=8.0)
    _activity(session, tenant, assay=binding, compound=compound_b, target=target, source_id="b", pchembl=7.0)
    _activity(
        session,
        tenant,
        assay=binding,
        compound=compound_c,
        target=target,
        source_id="censored",
        pchembl=9.0,
        relation=MeasurementRelation.LESS_THAN,
    )
    _activity(session, tenant, assay=cellular, compound=compound_b, target=target, source_id="cell", pchembl=6.5)
    _activity(session, tenant, assay=incomplete, compound=compound_c, target=target, source_id="missing", pchembl=None)
    session.add_all(
        [
            CompoundStructure(
                tenant_id=tenant.id,
                entity_id=compound_a.id,
                canonical_smiles="CCO",
                standard_inchi_key="LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
            ),
            CompoundStructure(
                tenant_id=tenant.id,
                entity_id=compound_b.id,
                canonical_smiles="CCN",
                standard_inchi_key="QUSNBJAOOMFDIB-UHFFFAOYSA-N",
            ),
        ]
    )
    other_tenant = Tenant(slug="other-sar", name="Other SAR Tenant")
    session.add(other_tenant)
    session.flush()
    hidden_target = _entity(session, other_tenant, EntityType.TARGET, "EGFR")
    hidden_compound = _entity(session, other_tenant, EntityType.DRUG, "Hidden Compound")
    hidden_assay = Assay(
        tenant_id=other_tenant.id,
        source_system="governed_ai",
        source_assay_id="hidden",
        target_entity_id=hidden_target.id,
        assay_type="binding",
        assay_format="biochemical",
    )
    session.add(hidden_assay)
    session.flush()
    _activity(
        session,
        other_tenant,
        assay=hidden_assay,
        compound=hidden_compound,
        target=hidden_target,
        source_id="hidden",
        pchembl=10.0,
    )
    session.commit()
    return target, compound_a, compound_b


def test_sar_comparison_groups_only_compatible_real_activity_rows(session: Session, tenant: Tenant) -> None:
    target, compound_a, compound_b = _seed_sar_data(session, tenant)

    result = IntelligenceService(session, tenant.id).sar_comparison(
        target.id,
        standard_type=None,
        assay_type=None,
        assay_format=None,
        organism=None,
        cell_line=None,
        limit=100,
        offset=0,
    )

    assert result.total == 5
    by_source = {item.source_activity_id: item for item in result.items}
    assert by_source["a"].compound_entity_id == compound_a.id
    assert by_source["a"].potency_rank == 1
    assert by_source["a"].delta_pchembl == 0
    assert by_source["a"].canonical_smiles == "CCO"
    assert by_source["b"].compound_entity_id == compound_b.id
    assert by_source["b"].potency_rank == 2
    assert by_source["b"].delta_pchembl == -1
    assert by_source["cell"].potency_rank == 1
    assert by_source["cell"].comparison_group != by_source["a"].comparison_group
    assert by_source["censored"].comparable is False
    assert by_source["censored"].potency_rank is None
    assert by_source["censored"].comparability_reasons == ["censored_or_approximate_relation"]
    assert set(by_source["missing"].comparability_reasons) == {
        "pchembl_missing",
        "assay_type_missing",
        "assay_format_missing",
    }
    assert result.facets["assay_type"] == {"binding": 3, "functional": 1}


def test_sar_comparison_api_is_typed_filterable_and_scope_protected(session: Session, tenant: Tenant) -> None:
    target, _, _ = _seed_sar_data(session, tenant)

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "sar-user",
        "api_key",
        frozenset({"activities:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/targets/{target.id}/sar-comparison",
                params={"assay_type": "binding", "assay_format": "biochemical"},
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["total"] == 3
            assert {item["source_activity_id"] for item in payload["items"]} == {"a", "b", "censored"}
            assert payload["items"][0]["compound_name"] == "Compound A"
            assert payload["warnings"]

        app.dependency_overrides[require_principal] = lambda: Principal(
            tenant.id,
            "no-sar-scope",
            "api_key",
            frozenset({"entities:read"}),
        )
        with TestClient(app) as client:
            assert client.get(f"/api/v1/targets/{target.id}/sar-comparison").status_code == 403
    finally:
        app.dependency_overrides.clear()
