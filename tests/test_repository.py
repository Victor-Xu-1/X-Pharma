from __future__ import annotations

from sqlalchemy.orm import Session

from pharma_intel.models import EntityType, Tenant
from pharma_intel.repository import EntityRepository, normalize_name
from pharma_intel.schemas import EntityCreate
from pharma_intel.sorting import SortClause


def test_normalize_name_handles_case_and_whitespace() -> None:
    assert normalize_name("  PD-1   Inhibitor ") == "pd-1 inhibitor"


def test_searches_primary_name_and_alias(session: Session, tenant: Tenant) -> None:
    repository = EntityRepository(session, tenant.id)
    created = repository.create(
        EntityCreate(
            entity_type=EntityType.TARGET,
            name="Programmed cell death protein 1",
            aliases=["PD-1", "CD279"],
            external_ids={"uniprot": "Q15116"},
        )
    )

    items, total = repository.search("pd-1", EntityType.TARGET, 10, 0)

    assert total == 1
    assert items[0].id == created.id


def test_relevance_search_ranks_exact_alias_and_identifier_before_partial_names(
    session: Session,
    tenant: Tenant,
) -> None:
    repository = EntityRepository(session, tenant.id)
    primary = repository.create(
        EntityCreate(
            entity_type=EntityType.TARGET,
            name="Epidermal growth factor receptor",
            aliases=["EGFR"],
            external_ids={"uniprot": "P00533"},
        )
    )
    repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR amplification"))
    repository.create(EntityCreate(entity_type=EntityType.TARGET, name="P00533 signaling pathway"))

    alias_items, _ = repository.search("EGFR", EntityType.TARGET, 10, 0)
    identifier_items, _ = repository.search("P00533", EntityType.TARGET, 10, 0)

    assert alias_items[0].id == primary.id
    assert identifier_items[0].id == primary.id


def test_relevance_search_ranks_anchored_alias_before_unanchored_exact_name(
    session: Session,
    tenant: Tenant,
) -> None:
    repository = EntityRepository(session, tenant.id)
    misleading_exact_name = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="EGFR"))
    authoritative_target = repository.create(
        EntityCreate(
            entity_type=EntityType.TARGET,
            name="Epidermal growth factor receptor",
            aliases=["EGFR"],
            external_ids={"uniprot": "P00533"},
        )
    )

    items, _ = repository.search("EGFR", None, 10, 0)

    assert [item.id for item in items[:2]] == [authoritative_target.id, misleading_exact_name.id]


def test_searches_multiple_entity_types_and_external_identifiers(session: Session, tenant: Tenant) -> None:
    repository = EntityRepository(session, tenant.id)
    target = repository.create(
        EntityCreate(entity_type=EntityType.TARGET, name="Portfolio target", external_ids={"UNIPROT": "P12345"})
    )
    drug = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="Portfolio drug", aliases=["P12345"]))
    repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="P12345 Holdings"))

    items, total = repository.search("P12345", [EntityType.TARGET, EntityType.DRUG], 10, 0)

    assert total == 2
    assert {item.id for item in items} == {target.id, drug.id}


def test_tenant_isolation(session: Session, tenant: Tenant) -> None:
    other = Tenant(slug="other", name="Other")
    session.add(other)
    session.commit()
    EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.DRUG, name="Pembrolizumab"))

    items, total = EntityRepository(session, other.id).search("pembro", None, 10, 0)

    assert total == 0
    assert items == []


def test_search_applies_full_result_sort_before_pagination(session: Session, tenant: Tenant) -> None:
    repository = EntityRepository(session, tenant.id)
    for name in ["Alpha Target", "Gamma Target", "Beta Target"]:
        repository.create(EntityCreate(entity_type=EntityType.TARGET, name=name))

    items, total = repository.search(
        "target",
        EntityType.TARGET,
        1,
        1,
        sort_by="name",
        sort_direction="desc",
    )

    assert total == 3
    assert [item.name for item in items] == ["Beta Target"]

    multi_sorted, _ = repository.search(
        "target",
        EntityType.TARGET,
        3,
        0,
        sort=(SortClause(field="entity_type", direction="asc"), SortClause(field="name", direction="desc")),
    )
    assert [item.name for item in multi_sorted] == ["Gamma Target", "Beta Target", "Alpha Target"]
