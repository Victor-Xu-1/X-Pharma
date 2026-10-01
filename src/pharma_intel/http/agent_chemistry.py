from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query

from pharma_intel.chemistry import ChemistryValidationError
from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.chemistry import _chemistry_arguments, _execute_chemistry_search
from pharma_intel.http.commercial_policy import _commercial_service
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.schemas import (
    AgentChemistrySearchRead,
    AgentPageResult,
    ChemistrySearchRequest,
    CompoundStructureRead,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/structures",
    response_model=AgentPageResult[CompoundStructureRead],
    tags=["internal-domain"],
)
def search_structures_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
    inchi_key: str | None = Query(default=None, max_length=27),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[CompoundStructureRead]:
    principal.require("structures:read")
    arguments: dict[str, object] = {"limit": limit}
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if inchi_key is not None:
        arguments["inchi_key"] = inchi_key
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="structure.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[entity_id],
        fetch=lambda offset, fetch_limit: intelligence.structures(
            entity_id,
            inchi_key,
            fetch_limit,
            offset,
        ),
    )


@router.post(
    "/internal/v1/domain/chemistry/search",
    response_model=AgentChemistrySearchRead,
    tags=["internal-domain"],
)
def search_chemistry_for_agent(
    payload: ChemistrySearchRequest,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentChemistrySearchRead:
    principal.require("structures:read")
    result_cap = 20 if payload.mode == "exact" else 50
    if payload.limit > result_cap:
        raise ChemistryValidationError(
            "agent_result_limit",
            f"Agent {payload.mode} searches are limited to {result_cap} records per request",
        )
    billing_class = f"structure.{payload.mode}"
    arguments = _chemistry_arguments(payload)
    if cursor is not None:
        arguments["cursor"] = cursor
    commercial_service = _commercial_service(session, principal)
    reservation = commercial_service.authorize_paginated_query(
        reservation_id,
        billing_class=billing_class,
        request_arguments=arguments,
        page_size=payload.limit,
        required_compute_units="1",
    )
    result = _execute_chemistry_search(
        session,
        principal.tenant_id,
        payload,
        limit=payload.limit + 1,
        offset=reservation.page_offset,
    )
    items = result.items[: payload.limit]
    next_cursor = commercial_service.issue_next_cursor(
        reservation,
        next_offset=reservation.page_offset + len(items),
        has_more=len(result.items) > payload.limit,
    )
    return AgentChemistrySearchRead(
        **result.model_dump(exclude={"items", "count"}),
        items=items,
        count=len(items),
        limit=payload.limit,
        page_depth=reservation.page_depth,
        next_cursor=next_cursor,
    )
