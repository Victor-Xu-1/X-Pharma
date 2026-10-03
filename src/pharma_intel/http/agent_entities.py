from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Query

from pharma_intel.dossier import dossier_result_capacity
from pharma_intel.http import runtime
from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.commercial_policy import _commercial_service
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.entities import (
    ENTITY_SEARCH_SCHEMA_VERSION,
    _entity_search_applied_filters,
    _entity_search_items,
)
from pharma_intel.http.public_read_policy import (
    _assert_public_entity_visible,
    _can_view_unpublished_entities,
    _effective_public_review_status,
    _intelligence_service,
)
from pharma_intel.http.query_contracts import _normalize_entity_types, _sort_reads, _validated_sort
from pharma_intel.models import EntityType, ReviewStatus
from pharma_intel.schemas import (
    ENTITY_SORT_FIELDS,
    AgentEntitySearchResult,
    AgentPageResult,
    BioactivityRead,
    EntityDossierResponse,
    EntitySortField,
    SarActivityRead,
    SortDirection,
    SortToken,
    TargetEvidenceRead,
)
from pharma_intel.search.client import SearchProjectionError
from pharma_intel.search.service import EntitySearchService

router = APIRouter()


@router.get(
    "/internal/v1/domain/entities",
    response_model=AgentEntitySearchResult,
    tags=["internal-domain"],
)
def search_entities_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    billing_class: Literal["entity.search", "entity.resolve"],
    q: str = Query(min_length=1, max_length=500),
    entity_type: EntityType | None = None,
    review_status: ReviewStatus | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: EntitySortField | None = None,
    sort_direction: SortDirection | None = None,
    entity_types: Annotated[list[EntityType] | None, Query()] = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentEntitySearchResult:
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
    arguments: dict[str, object] = {"q": q, "limit": limit}
    if len(selected_types) == 1:
        arguments["entity_type"] = selected_types[0].value
    elif selected_types:
        arguments["entity_types"] = [item.value for item in selected_types]
    if effective_review_status is not None:
        arguments["review_status"] = effective_review_status.value
    if cursor is not None:
        arguments["cursor"] = cursor
    arguments["sort"] = [clause.token for clause in effective_sort]
    service = _commercial_service(session, principal)
    reservation = service.authorize_paginated_query(
        reservation_id,
        billing_class=billing_class,
        request_arguments=arguments,
        page_size=limit,
    )
    try:
        result = EntitySearchService(session, principal.tenant_id, runtime.get_settings()).search(
            q,
            entity_type,
            limit,
            reservation.page_offset,
            effective_review_status,
            effective_sort[0].field,
            effective_sort[0].direction,
            selected_types,
            effective_sort,
            hide_unpublished_facets=not _can_view_unpublished_entities(principal),
        )
    except SearchProjectionError as exc:
        raise HTTPException(status_code=503, detail="Entity search projection unavailable") from exc
    next_offset = reservation.page_offset + len(result.items)
    next_cursor = service.issue_next_cursor(
        reservation,
        next_offset=next_offset,
        has_more=next_offset < result.total,
    )
    return AgentEntitySearchResult(
        query_schema_version=ENTITY_SEARCH_SCHEMA_VERSION,
        applied_filters=_entity_search_applied_filters(q, selected_types, effective_review_status),
        items=_entity_search_items(result),
        limit=limit,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_reads(effective_sort),
        engine=result.engine,
        facets=result.facets,
    )


@router.get(
    "/internal/v1/domain/entities/{entity_id}/dossier",
    response_model=EntityDossierResponse,
    tags=["internal-domain"],
)
def get_entity_dossier_for_agent(
    entity_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=50, ge=1, le=100),
) -> EntityDossierResponse:
    principal.require("dossiers:read")
    result_limit = dossier_result_capacity(limit)
    _commercial_service(session, principal).authorize_paginated_query(
        reservation_id,
        billing_class="entity.dossier",
        request_arguments={"entity_id": entity_id, "domain_limit": limit, "limit": result_limit},
        page_size=result_limit,
    )
    dossier = _intelligence_service(session, principal).entity_dossier(entity_id, limit)
    if dossier is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    _assert_public_entity_visible(dossier.entity, principal)
    return dossier


@router.get(
    "/internal/v1/domain/targets/{target_id}/evidence",
    response_model=AgentPageResult[TargetEvidenceRead],
    tags=["internal-domain"],
)
def search_target_evidence_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    evidence_type: Literal[
        "genetic_association",
        "expression",
        "functional",
        "translational",
        "biomarker",
        "safety",
    ]
    | None = Query(default=None),
    direction: Literal["supports", "opposes", "neutral", "unknown"] | None = Query(default=None),
    disease_entity_id: str | None = Query(default=None, min_length=1, max_length=36),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[TargetEvidenceRead]:
    principal.require("targets:read")
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    for name, value in (
        ("evidence_type", evidence_type),
        ("direction", direction),
        ("disease_entity_id", disease_entity_id),
        ("cursor", cursor),
    ):
        if value is not None:
            arguments[name] = value
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="target.evidence.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id, disease_entity_id],
        fetch=lambda offset, fetch_limit: intelligence.target_evidence_for_entity(
            target_id,
            fetch_limit,
            offset,
            evidence_type=evidence_type,
            direction=direction,
            disease_entity_id=disease_entity_id,
        ),
    )


@router.get(
    "/internal/v1/domain/targets/{target_id}/bioactivities",
    response_model=AgentPageResult[BioactivityRead],
    tags=["internal-domain"],
)
def search_bioactivities_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    standard_type: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[BioactivityRead]:
    principal.require("activities:read")
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    if standard_type is not None:
        arguments["standard_type"] = standard_type
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="bioactivity.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id],
        fetch=lambda offset, fetch_limit: intelligence.bioactivities(target_id, standard_type, fetch_limit, offset),
    )


@router.get(
    "/internal/v1/domain/targets/{target_id}/sar-comparison",
    response_model=AgentPageResult[SarActivityRead],
    tags=["internal-domain"],
)
def compare_target_sar_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    standard_type: str | None = Query(default=None, max_length=120),
    assay_type: str | None = Query(default=None, max_length=120),
    assay_format: str | None = Query(default=None, max_length=160),
    organism: str | None = Query(default=None, max_length=160),
    cell_line: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[SarActivityRead]:
    principal.require("activities:read")
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    filters = {
        "standard_type": standard_type,
        "assay_type": assay_type,
        "assay_format": assay_format,
        "organism": organism,
        "cell_line": cell_line,
    }
    arguments.update({key: value for key, value in filters.items() if value is not None})
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="sar.compare",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id],
        fetch=lambda offset, fetch_limit: (
            intelligence.sar_comparison(
                target_id,
                standard_type=standard_type,
                assay_type=assay_type,
                assay_format=assay_format,
                organism=organism,
                cell_line=cell_line,
                limit=fetch_limit,
                offset=offset,
            ).items
        ),
    )
