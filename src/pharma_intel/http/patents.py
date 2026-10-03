from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible, _intelligence_service
from pharma_intel.http.query_contracts import _validated_sort, _validated_utc_datetime_range
from pharma_intel.schemas import (
    PATENT_SORT_FIELDS,
    PatentFamilyRead,
    PatentFamilySearchItemRead,
    PatentFamilySearchResult,
    PatentSortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get("/api/v1/patents", response_model=list[PatentFamilyRead], tags=["patents"])
def search_patents(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[PatentFamilyRead]:
    principal.require("patents:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).patents(entity_id, q, limit)


@router.get("/api/v1/patent-families", response_model=PatentFamilySearchResult, tags=["patents"])
def search_patent_families(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    entity_id: str | None = Query(default=None, max_length=36),
    applicant: str | None = Query(default=None, max_length=300),
    legal_status: str | None = Query(default=None, max_length=120),
    priority_from: Annotated[datetime | None, Query()] = None,
    priority_to: Annotated[datetime | None, Query()] = None,
    expiration_from: Annotated[datetime | None, Query()] = None,
    expiration_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: PatentSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> PatentFamilySearchResult:
    principal.require("patents:read")
    effective_sort = _validated_sort(
        sort,
        PATENT_SORT_FIELDS,
        default_field="priority_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    priority_from, priority_to = _validated_utc_datetime_range(
        priority_from, priority_to, start_field="priority_from", end_field="priority_to"
    )
    expiration_from, expiration_to = _validated_utc_datetime_range(
        expiration_from, expiration_to, start_field="expiration_from", end_field="expiration_to"
    )
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).search_patent_families(
        q,
        applicant,
        legal_status,
        limit,
        offset,
        entity_id=entity_id,
        priority_from=priority_from,
        priority_to=priority_to,
        expiration_from=expiration_from,
        expiration_to=expiration_to,
        sort=effective_sort,
    )


@router.get(
    "/api/v1/patent-families/{family_id}",
    response_model=PatentFamilySearchItemRead,
    tags=["patents"],
)
def get_patent_family(
    family_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> PatentFamilySearchItemRead:
    principal.require("patents:read")
    family = _intelligence_service(session, principal).patent_family_detail(family_id)
    if family is None:
        raise HTTPException(status_code=404, detail="Patent family not found")
    return family
