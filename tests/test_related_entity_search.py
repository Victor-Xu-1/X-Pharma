from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.service import GovernanceService
from pharma_intel.models import (
    Entity,
    EntityType,
    GovernanceStatus,
    ReviewStatus,
    SavedSearchVersion,
    StagedFact,
    Tenant,
)
from pharma_intel.monitoring.consumer import saved_search_matches_entity
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.contracts import EntitySearchPage
from pharma_intel.search.service import EntitySearchService
from tests.test_chembl_governance import _version


def _govern(session: Session, tenant: Tenant, tmp_path: Path) -> Entity:
    store, version = _version(session, tenant, tmp_path)
    GovernanceService(session, Settings(ai_governance_enabled=False), store, tenant.id).govern_version(version.id)
    drug = session.scalar(select(Entity).where(Entity.entity_type == EntityType.DRUG))
    assert drug is not None
    return drug


def test_related_target_search_returns_drug_with_evidence_and_consistent_facets(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    drug = _govern(session, tenant, tmp_path)
    service = EntitySearchService(session, tenant.id, Settings(search_backend="database"))
    direct = service.search("EGFR", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED)
    related = service.search("EGFR", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED, include_related=True)
    assert direct.total == 0
    assert related.total == 1
    assert related.items[0].id == drug.id
    assert related.facets["entity_type"] == {"drug": 1, "target": 1}
    match = related.matches[drug.id]
    assert match.match_type == "relationship"
    assert match.matched_value == "Epidermal growth factor receptor"
    assert match.predicate == "has_target"
    assert match.source_uri is not None and match.source_uri.startswith("https://www.ebi.ac.uk/")


def test_related_search_excludes_withdrawn_facts_and_hidden_entities(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    drug = _govern(session, tenant, tmp_path)
    service = EntitySearchService(session, tenant.id, Settings(search_backend="database"))
    fact = session.scalar(select(StagedFact).where(StagedFact.fact_kind == "program"))
    assert fact is not None
    fact.status = GovernanceStatus.WITHDRAWN
    session.commit()
    assert service.search("EGFR", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED, include_related=True).total == 0
    fact.status = GovernanceStatus.PUBLISHED
    drug.review_status = ReviewStatus.DRAFT
    session.commit()
    assert service.search("EGFR", EntityType.DRUG, 10, 0, ReviewStatus.VERIFIED, include_related=True).total == 0


def test_opensearch_receives_authorized_related_ids_without_replacing_its_pagination(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    drug = _govern(session, tenant, tmp_path)
    gateway = MagicMock(spec=OpenSearchGateway)
    gateway.search_entities.return_value = EntitySearchPage([drug.id], 1, {"entity_type": {"drug": 1, "target": 1}})
    result = EntitySearchService(session, tenant.id, Settings(search_backend="opensearch"), gateway).search(
        "EGFR", EntityType.DRUG, 1, 4, ReviewStatus.VERIFIED, include_related=True
    )
    assert gateway.search_entities.call_args.args[3:5] == (1, 4)
    assert gateway.search_entities.call_args.kwargs["additional_entity_ids"] == [drug.id]
    assert result.matches[drug.id].match_type == "relationship"


def test_related_search_is_tenant_scoped(session: Session, tenant: Tenant, tmp_path: Path) -> None:
    _govern(session, tenant, tmp_path)
    other = Tenant(slug="other", name="Other")
    session.add(other)
    session.commit()
    result = EntitySearchService(session, other.id, Settings(search_backend="database")).search(
        "EGFR", None, 10, 0, ReviewStatus.VERIFIED, include_related=True
    )
    assert result.total == 0 and not result.items


def test_saved_related_query_uses_the_same_published_relationships_as_interactive_search(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    drug = _govern(session, tenant, tmp_path)
    version = SavedSearchVersion(
        version=1,
        query_type="entity_search",
        query_json={
            "q": "EGFR",
            "entity_type": "drug",
            "review_status": "verified",
            "include_related": True,
        },
    )
    assert saved_search_matches_entity(session, tenant.id, drug, version)
    version.query_json = {**version.query_json, "entity_type": "organization"}
    assert not saved_search_matches_entity(session, tenant.id, drug, version)
