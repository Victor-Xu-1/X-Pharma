from __future__ import annotations

from dataclasses import asdict

import pytest

from pharma_intel.models import Entity, EntityIdentifier, EntityType, ReviewStatus
from pharma_intel.search.service import EntitySearchService


def _entity_with_identifier(namespace: str, value: str, storage: str) -> Entity:
    entity = Entity(
        id="test-entity",
        tenant_id="test-tenant",
        entity_type=EntityType.TARGET,
        name="Canonical target",
        normalized_name="canonical target",
        description=None,
        external_ids={namespace: value} if storage == "external_ids" else {},
        review_status=ReviewStatus.VERIFIED,
        attributes={},
    )
    entity.aliases = []
    entity.identity_identifiers = (
        [
            EntityIdentifier(
                tenant_id=entity.tenant_id,
                entity_type=entity.entity_type,
                namespace=namespace,
                value=value,
                normalized_value=value.casefold(),
                review_status=ReviewStatus.VERIFIED,
            )
        ]
        if storage == "identity_identifiers"
        else []
    )
    return entity


@pytest.mark.parametrize("storage", ["external_ids", "identity_identifiers"])
@pytest.mark.parametrize(
    "namespace", ["internal", " Internal-Row ", "source_record", "ingestion_job", "pharmcube_target"]
)
@pytest.mark.parametrize("query", ["private-routing-value", "private-routing"])
def test_search_explanations_do_not_disclose_hidden_identifier_values(
    storage: str,
    namespace: str,
    query: str,
) -> None:
    entity = _entity_with_identifier(namespace, "private-routing-value", storage)

    match = EntitySearchService._explain_matches([entity], query)[entity.id]

    assert match.match_type == "semantic"
    assert match.namespace is None and match.matched_value is None
    assert "private-routing-value" not in str(asdict(match))


@pytest.mark.parametrize("storage", ["external_ids", "identity_identifiers"])
@pytest.mark.parametrize("query,relation", [("P00533", "exact"), ("P005", "partial")])
def test_public_scientific_identifier_explanations_are_preserved(
    storage: str,
    query: str,
    relation: str,
) -> None:
    entity = _entity_with_identifier("uniprot", "P00533", storage)

    match = EntitySearchService._explain_matches([entity], query)[entity.id]

    assert match.match_type == "external_id"
    assert match.match_relation == relation
    assert match.namespace == "uniprot" and match.matched_value == "P00533"


def test_a_hidden_duplicate_does_not_shadow_a_public_identifier_explanation() -> None:
    entity = _entity_with_identifier("uniprot", "P00533", "identity_identifiers")
    entity.external_ids = {"internal_row": "P00533"}

    match = EntitySearchService._explain_matches([entity], "P00533")[entity.id]

    assert match.match_type == "external_id"
    assert match.namespace == "uniprot" and match.matched_value == "P00533"
