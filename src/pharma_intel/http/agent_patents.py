from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.http.query_contracts import _sort_reads, _validated_sort
from pharma_intel.schemas import (
    PATENT_SORT_FIELDS,
    AgentPageResult,
    PatentFamilySearchItemRead,
    PatentSortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/patents",
    response_model=AgentPageResult[PatentFamilySearchItemRead],
    tags=["internal-domain"],
)
def search_patents_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    applicant: str | None = Query(default=None, max_length=300),
    legal_status: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: PatentSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[PatentFamilySearchItemRead]:
    principal.require("patents:read")
    effective_sort = _validated_sort(
        sort,
        PATENT_SORT_FIELDS,
        default_field="priority_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if q is not None:
        arguments["q"] = q
    if applicant is not None:
        arguments["applicant"] = applicant
    if legal_status is not None:
        arguments["legal_status"] = legal_status
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="patent.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.patent_search_items(
            entity_id,
            q,
            applicant,
            legal_status,
            fetch_limit,
            offset,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )
