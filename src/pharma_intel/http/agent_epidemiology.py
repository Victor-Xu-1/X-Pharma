from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.http.query_contracts import _sort_reads, _validated_sort
from pharma_intel.schemas import (
    EPIDEMIOLOGY_SORT_FIELDS,
    AgentPageResult,
    EpidemiologyObservationSearchItemRead,
    EpidemiologySortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/epidemiology-observations",
    response_model=AgentPageResult[EpidemiologyObservationSearchItemRead],
    tags=["internal-domain"],
)
def search_epidemiology_observations_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    disease_entity_id: str | None = Query(default=None, max_length=500),
    q: str | None = Query(default=None, max_length=500),
    measure: str | None = Query(default=None, max_length=40),
    geography: str | None = Query(default=None, max_length=160),
    unit: str | None = Query(default=None, max_length=120),
    population_scope: str | None = Query(default=None, max_length=500),
    patient_population_id: str | None = Query(default=None, max_length=36),
    age_group: str | None = Query(default=None, max_length=120),
    sex: str | None = Query(default=None, max_length=80),
    period_start_from: Annotated[datetime | None, Query()] = None,
    period_end_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: EpidemiologySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[EpidemiologyObservationSearchItemRead]:
    principal.require("epidemiology:read")
    effective_sort = _validated_sort(
        sort,
        EPIDEMIOLOGY_SORT_FIELDS,
        default_field="period_end",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    for name, value in (
        ("disease_entity_id", disease_entity_id),
        ("q", q),
        ("measure", measure),
        ("geography", geography),
        ("unit", unit),
        ("population_scope", population_scope),
        ("patient_population_id", patient_population_id),
        ("age_group", age_group),
        ("sex", sex),
        ("period_start_from", period_start_from.isoformat() if period_start_from else None),
        ("period_end_to", period_end_to.isoformat() if period_end_to else None),
        ("cursor", cursor),
    ):
        if value is not None:
            arguments[name] = value
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="epidemiology.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[disease_entity_id],
        fetch=lambda offset, fetch_limit: intelligence.epidemiology_search_items(
            disease_entity_id,
            q,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            period_start_from,
            period_end_to,
            fetch_limit,
            offset,
            patient_population_id=patient_population_id,
            sort=effective_sort,
        ),
        sort=_sort_reads(effective_sort),
    )
