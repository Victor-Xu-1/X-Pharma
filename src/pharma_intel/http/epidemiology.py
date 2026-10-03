from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible, _intelligence_service
from pharma_intel.http.query_contracts import _validated_sort
from pharma_intel.schemas import (
    EPIDEMIOLOGY_SORT_FIELDS,
    EpidemiologyObservationSearchResult,
    EpidemiologySortField,
    EpidemiologyTrendResult,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/api/v1/epidemiology-observations",
    response_model=EpidemiologyObservationSearchResult,
    tags=["epidemiology"],
)
def search_epidemiology_observations(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    disease_entity_id: str | None = Query(default=None, max_length=36),
    measure: str | None = Query(default=None, max_length=40),
    geography: str | None = Query(default=None, max_length=160),
    unit: str | None = Query(default=None, max_length=120),
    population_scope: str | None = Query(default=None, max_length=500),
    patient_population_id: str | None = Query(default=None, max_length=36),
    age_group: str | None = Query(default=None, max_length=120),
    sex: str | None = Query(default=None, max_length=80),
    period_start_from: Annotated[datetime | None, Query()] = None,
    period_end_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: EpidemiologySortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> EpidemiologyObservationSearchResult:
    principal.require("epidemiology:read")
    _assert_public_entity_ids_visible(session, principal, [disease_entity_id])
    effective_sort = _validated_sort(
        sort,
        EPIDEMIOLOGY_SORT_FIELDS,
        default_field="period_end",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    return _intelligence_service(session, principal).search_epidemiology_observations(
        q,
        measure,
        geography,
        unit,
        population_scope,
        age_group,
        sex,
        period_start_from,
        period_end_to,
        limit,
        offset,
        disease_entity_id=disease_entity_id,
        patient_population_id=patient_population_id,
        sort=effective_sort,
    )


@router.get(
    "/api/v1/epidemiology-trends/{disease_entity_id}",
    response_model=EpidemiologyTrendResult,
    tags=["epidemiology"],
)
def get_epidemiology_trend(
    disease_entity_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    measure: str | None = Query(default=None, max_length=40),
    geography: str | None = Query(default=None, max_length=160),
    unit: str | None = Query(default=None, max_length=120),
    population_scope: str | None = Query(default=None, max_length=500),
    patient_population_id: str | None = Query(default=None, max_length=36),
    age_group: str | None = Query(default=None, max_length=120),
    sex: str | None = Query(default=None, max_length=80),
    anchor_observation_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=200, ge=1, le=500),
) -> EpidemiologyTrendResult:
    principal.require("epidemiology:read")
    _assert_public_entity_ids_visible(session, principal, [disease_entity_id])
    result = _intelligence_service(session, principal).epidemiology_trend(
        disease_entity_id,
        measure,
        geography,
        unit,
        population_scope,
        age_group,
        sex,
        limit,
        patient_population_id=patient_population_id,
        anchor_observation_id=anchor_observation_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Disease not found")
    return result
