from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.models import ReviewStatus
from pharma_intel.repository import EntityRepository
from pharma_intel.search.client import OpenSearchGateway, SearchProjectionError
from pharma_intel.search.contracts import EntitySearchPage
from pharma_intel.search.service import EntitySearchService


def test_opensearch_search_fails_closed_when_a_projected_entity_cannot_be_hydrated() -> None:
    gateway = MagicMock(spec=OpenSearchGateway)
    gateway.search_entities.return_value = EntitySearchPage(
        entity_ids=["stale-entity-id"],
        total=1,
        facets={"entity_type": {"target": 1}},
    )
    repository = MagicMock(spec=EntityRepository)
    repository.get_many.return_value = []
    service = EntitySearchService(
        MagicMock(spec=Session),
        "tenant-id",
        Settings(search_backend="opensearch"),
        gateway,
    )
    service.repository = repository

    with pytest.raises(SearchProjectionError, match="1 of 1 page entities are unavailable"):
        service.search("IFNA2", None, limit=25, offset=0, review_status=ReviewStatus.VERIFIED)

    assert gateway.search_entities.call_args.kwargs["facet_review_status"] == ReviewStatus.VERIFIED
