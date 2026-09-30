from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.models import Entity, EntityType, ReviewStatus
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import ENTITY_SORT_FIELDS, EntitySortField, SortDirection
from pharma_intel.search.client import OpenSearchGateway, SearchProjectionError, get_opensearch_gateway
from pharma_intel.search.contracts import EntitySearchMatch
from pharma_intel.sorting import SortClause, validate_sort_clauses


@dataclass(frozen=True)
class EntitySearchResultSet:
    items: list[Entity]
    matches: dict[str, EntitySearchMatch]
    total: int
    facets: dict[str, dict[str, int]]
    suggestions: list[str]
    engine: str
    took_ms: int | None
    sort_by: EntitySortField
    sort_direction: SortDirection
    sort: tuple[SortClause[EntitySortField], ...]


class EntitySearchService:
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        settings: Settings,
        gateway: OpenSearchGateway | None = None,
    ) -> None:
        self.repository = EntityRepository(session, tenant_id)
        self.tenant_id = tenant_id
        self.settings = settings
        self.gateway = gateway

    def search(
        self,
        query: str | None,
        entity_type: EntityType | None,
        limit: int,
        offset: int,
        review_status: ReviewStatus | None = None,
        sort_by: EntitySortField = "relevance",
        sort_direction: SortDirection = "desc",
        entity_types: list[EntityType] | None = None,
        sort: Sequence[SortClause[EntitySortField]] | None = None,
        hide_unpublished_facets: bool = False,
    ) -> EntitySearchResultSet:
        effective_sort = validate_sort_clauses(
            sort,
            ENTITY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        selected_types = list(dict.fromkeys(([entity_type] if entity_type is not None else []) + (entity_types or [])))
        if self.settings.search_backend == "database":
            items, total = self.repository.search(
                query,
                selected_types,
                limit,
                offset,
                review_status,
                sort=effective_sort,
            )
            facets = self.repository.search_facets(
                query,
                review_status if hide_unpublished_facets else None,
            )
            return EntitySearchResultSet(
                items,
                self._explain_matches(items, query),
                total,
                facets,
                [],
                "database",
                None,
                effective_sort[0].field,
                effective_sort[0].direction,
                effective_sort,
            )
        gateway = self.gateway or get_opensearch_gateway()
        facet_review_status = (
            review_status if review_status is not None else ReviewStatus.VERIFIED if hide_unpublished_facets else None
        )
        page = gateway.search_entities(
            self.tenant_id,
            query,
            selected_types,
            limit,
            offset,
            review_status,
            sort=effective_sort,
            facet_review_status=facet_review_status,
        )
        items = self.repository.get_many(page.entity_ids)
        if len(items) != len(page.entity_ids):
            missing_count = len(page.entity_ids) - len(items)
            raise SearchProjectionError(
                "OpenSearch entity projection is inconsistent with the authoritative database "
                f"({missing_count} of {len(page.entity_ids)} page entities are unavailable)"
            )
        return EntitySearchResultSet(
            items,
            self._explain_matches(items, query),
            page.total,
            page.facets,
            page.suggestions,
            page.engine,
            page.took_ms,
            effective_sort[0].field,
            effective_sort[0].direction,
            effective_sort,
        )

    @staticmethod
    def _explain_matches(entities: list[Entity], query: str | None) -> dict[str, EntitySearchMatch]:
        if not query:
            return {}
        normalized = query.strip().casefold()
        matches: dict[str, EntitySearchMatch] = {}
        for entity in entities:
            canonical = entity.name.strip().casefold()
            identifiers = [
                (namespace, str(value), str(value).strip().casefold())
                for namespace, value in entity.external_ids.items()
            ]
            known_identifiers = {(namespace.casefold(), value.casefold()) for namespace, value, _ in identifiers}
            identifiers.extend(
                (item.namespace, item.value, item.normalized_value)
                for item in entity.identity_identifiers
                if (item.namespace.casefold(), item.value.casefold()) not in known_identifiers
            )
            if canonical == normalized:
                matches[entity.id] = EntitySearchMatch("canonical_name", "exact", entity.name)
                continue
            exact_identifier = next((item for item in identifiers if item[2] == normalized), None)
            if exact_identifier is not None:
                matches[entity.id] = EntitySearchMatch(
                    "external_id",
                    "exact",
                    exact_identifier[1],
                    exact_identifier[0],
                )
                continue
            exact_alias = next((alias for alias in entity.aliases if alias.normalized_alias == normalized), None)
            if exact_alias is not None:
                matches[entity.id] = EntitySearchMatch("alias", "exact", exact_alias.alias)
                continue
            if normalized in canonical:
                matches[entity.id] = EntitySearchMatch("canonical_name", "partial", entity.name)
                continue
            partial_alias = next((alias for alias in entity.aliases if normalized in alias.normalized_alias), None)
            if partial_alias is not None:
                matches[entity.id] = EntitySearchMatch("alias", "partial", partial_alias.alias)
                continue
            partial_identifier = next((item for item in identifiers if normalized in item[2]), None)
            if partial_identifier is not None:
                matches[entity.id] = EntitySearchMatch(
                    "external_id",
                    "partial",
                    partial_identifier[1],
                    partial_identifier[0],
                )
                continue
            if entity.description and normalized in entity.description.casefold():
                matches[entity.id] = EntitySearchMatch("description", "partial")
                continue
            matches[entity.id] = EntitySearchMatch("semantic", "semantic")
        return matches
