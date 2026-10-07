from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError

from pharma_intel.http import runtime
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import (
    _assert_public_entity_visible,
    _can_view_unpublished_entities,
    _effective_public_review_status,
    _public_entity_read,
)
from pharma_intel.http.query_contracts import _normalize_entity_types, _sort_reads, _validated_sort
from pharma_intel.identity import IdentityError
from pharma_intel.intelligence.facets import _applied_filters
from pharma_intel.models import EntityType, ReviewStatus
from pharma_intel.repository import DuplicateEntityError, EntityRepository
from pharma_intel.research_activity import RESEARCH_ENTITY_RESOURCE_TYPE, RequestAuditResource
from pharma_intel.schemas import (
    ENTITY_SORT_FIELDS,
    AppliedFilterRead,
    EntityCreate,
    EntityRead,
    EntitySearchItemRead,
    EntitySortField,
    EntitySuggestionResult,
    SearchResult,
    SortDirection,
    SortToken,
)
from pharma_intel.search.client import SearchProjectionError
from pharma_intel.search.service import EntitySearchResultSet, EntitySearchService

router = APIRouter()
ENTITY_SEARCH_SCHEMA_VERSION = "pharma.entity.search.v3"


def _entity_search_applied_filters(
    q: str | None,
    selected_types: list[EntityType],
    review_status: ReviewStatus | None,
    include_related: bool = False,
) -> list[AppliedFilterRead]:
    """Build the server-normalized applied-filter echo for entity search responses.

    Mirrors the seven professional domains: only conditions the server actually applied
    are echoed, in normalized form, so clients never present draft input as applied
    state.
    """

    return _applied_filters(
        ("q", "contains", q.strip() if q else None),
        ("entity_types", "in", [item.value for item in selected_types]),
        ("review_status", "eq", review_status.value if review_status else None),
        ("include_related", "eq", True if include_related and q else None),
    )


def _entity_search_items(result: EntitySearchResultSet) -> list[EntitySearchItemRead]:
    items: list[EntitySearchItemRead] = []
    for entity in result.items:
        match = result.matches.get(entity.id)
        match_payload = (
            {
                "match_type": match.match_type,
                "match_relation": match.match_relation,
                "matched_value": match.matched_value,
                "namespace": match.namespace,
                "via_entity_id": match.via_entity_id,
                "predicate": match.predicate,
                "source_uri": match.source_uri,
            }
            if match is not None
            else None
        )
        entity_read = _public_entity_read(entity)
        items.append(
            EntitySearchItemRead(
                **{**entity_read.model_dump(), "aliases": entity_read.aliases[:20]},
                match=match_payload,
            )
        )
    return items


@router.get("/api/v1/entities", response_model=SearchResult, tags=["entities"])
def search_entities(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    entity_type: EntityType | None = None,
    review_status: ReviewStatus | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort_by: EntitySortField | None = None,
    sort_direction: SortDirection | None = None,
    entity_types: Annotated[list[EntityType] | None, Query()] = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
    include_related: bool = False,
) -> SearchResult:
    principal.require("entities:read")
    effective_review_status = _effective_public_review_status(principal, review_status)
    effective_sort = _validated_sort(
        sort,
        ENTITY_SORT_FIELDS,
        default_field="relevance",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    selected_types = _normalize_entity_types(entity_type, entity_types or [])
    try:
        result = EntitySearchService(session, principal.tenant_id, runtime.get_settings()).search(
            q,
            entity_type,
            limit,
            offset,
            effective_review_status,
            effective_sort[0].field,
            effective_sort[0].direction,
            selected_types,
            effective_sort,
            hide_unpublished_facets=not _can_view_unpublished_entities(principal),
            include_related=include_related,
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Entity search projection unavailable") from exc
    return SearchResult(
        query_schema_version=ENTITY_SEARCH_SCHEMA_VERSION,
        applied_filters=_entity_search_applied_filters(q, selected_types, effective_review_status, include_related),
        items=_entity_search_items(result),
        total=result.total,
        limit=limit,
        offset=offset,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_reads(effective_sort),
        facets=result.facets,
        suggestions=result.suggestions,
        engine=result.engine,
        took_ms=result.took_ms,
        warnings=list(result.warnings),
    )


@router.get("/api/v1/entities/suggestions", response_model=EntitySuggestionResult, tags=["entities"])
def suggest_entities(
    principal: PrincipalDep,
    session: SessionDep,
    q: str = Query(min_length=1, max_length=500),
    entity_type: EntityType | None = None,
    limit: int = Query(default=10, ge=1, le=25),
    entity_types: Annotated[list[EntityType] | None, Query()] = None,
) -> EntitySuggestionResult:
    principal.require("entities:read")
    effective_review_status = _effective_public_review_status(principal, None)
    selected_types = _normalize_entity_types(entity_type, entity_types or [])
    try:
        result = EntitySearchService(session, principal.tenant_id, runtime.get_settings()).search(
            q,
            entity_type,
            limit,
            0,
            effective_review_status,
            entity_types=selected_types,
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Entity search projection unavailable") from exc
    suggestions = result.suggestions or [item.name for item in result.items]
    return EntitySuggestionResult(suggestions=suggestions[:limit], engine=result.engine)


@router.get("/api/v1/entities/{entity_id}", response_model=EntityRead, tags=["entities"])
def get_entity(entity_id: str, request: Request, principal: PrincipalDep, session: SessionDep) -> EntityRead:
    principal.require("entities:read")
    entity = EntityRepository(session, principal.tenant_id).get(entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    _assert_public_entity_visible(entity, principal)
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=entity.id,
        details={"entity_type": entity.entity_type.value},
    )
    return _public_entity_read(entity)


@router.post(
    "/api/v1/entities",
    response_model=EntityRead,
    status_code=status.HTTP_201_CREATED,
    tags=["entities"],
)
def create_entity(payload: EntityCreate, principal: PrincipalDep, session: SessionDep) -> EntityRead:
    principal.require("entities:write")
    try:
        entity = EntityRepository(session, principal.tenant_id).create(payload)
    except (DuplicateEntityError, IntegrityError) as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Entity already exists") from exc
    except IdentityError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _public_entity_read(entity)
