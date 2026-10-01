from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible, _intelligence_service
from pharma_intel.http.query_contracts import (
    DealAssetModalityQueryValue,
    DealAssetProgramTagQueryValue,
    _normalized_repeated_filter,
    _validate_deal_amount_sort,
    _validated_number_range,
    _validated_sort,
    _validated_utc_datetime_range,
)
from pharma_intel.models import DealDirection, DealPartyRole, DealRightType, DealStatus, DevelopmentPhase
from pharma_intel.schemas import (
    DEAL_SORT_FIELDS,
    DealAnalysisLimit,
    DealRead,
    DealSearchItemRead,
    DealSearchResult,
    DealSortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get("/api/v1/deals", response_model=list[DealRead], tags=["deals"])
def search_deals(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[DealRead]:
    principal.require("deals:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).deals(entity_id, limit)


@router.get("/api/v1/deal-transactions", response_model=DealSearchResult, tags=["deals"])
def search_deal_transactions(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    deal_type: str | None = Query(default=None, max_length=100),
    deal_status: Annotated[DealStatus | None, Query(alias="status")] = None,
    direction: DealDirection | None = None,
    direction_reference_jurisdiction: str | None = Query(default=None, max_length=120),
    territory: str | None = Query(default=None, max_length=240),
    asset_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    target_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    disease_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    asset_modality: Annotated[list[DealAssetModalityQueryValue] | None, Query(max_length=20)] = None,
    asset_program_tag: Annotated[list[DealAssetProgramTagQueryValue] | None, Query(max_length=20)] = None,
    party: str | None = Query(default=None, max_length=500),
    party_entity_id: str | None = Query(default=None, max_length=36),
    party_role: DealPartyRole | None = None,
    party_country_region: str | None = Query(default=None, max_length=120),
    party_organization_type: str | None = Query(default=None, max_length=120),
    development_phase_at_transaction: DevelopmentPhase | None = None,
    current_development_phase: DevelopmentPhase | None = None,
    right_type: DealRightType | None = None,
    rights_territory: str | None = Query(default=None, max_length=240),
    currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    announced_from: Annotated[datetime | None, Query()] = None,
    announced_to: Annotated[datetime | None, Query()] = None,
    terminated_from: Annotated[datetime | None, Query()] = None,
    terminated_to: Annotated[datetime | None, Query()] = None,
    source_updated_from: Annotated[datetime | None, Query()] = None,
    source_updated_to: Annotated[datetime | None, Query()] = None,
    upfront_amount_min: float | None = Query(default=None, ge=0),
    upfront_amount_max: float | None = Query(default=None, ge=0),
    total_potential_amount_min: float | None = Query(default=None, ge=0),
    total_potential_amount_max: float | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: DealSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
    analysis_top: int = Query(default=8, ge=5, le=50),
) -> DealSearchResult:
    principal.require("deals:read")
    if analysis_top not in {5, 8, 20, 50}:
        raise HTTPException(status_code=422, detail="analysis_top must be one of 5, 8, 20 or 50")
    effective_sort = _validated_sort(
        sort,
        DEAL_SORT_FIELDS,
        default_field="announced_at",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    _validate_deal_amount_sort(effective_sort, currency)
    announced_from, announced_to = _validated_utc_datetime_range(
        announced_from,
        announced_to,
        start_field="announced_from",
        end_field="announced_to",
    )
    terminated_from, terminated_to = _validated_utc_datetime_range(
        terminated_from,
        terminated_to,
        start_field="terminated_from",
        end_field="terminated_to",
    )
    source_updated_from, source_updated_to = _validated_utc_datetime_range(
        source_updated_from,
        source_updated_to,
        start_field="source_updated_from",
        end_field="source_updated_to",
    )
    upfront_amount_min, upfront_amount_max = _validated_number_range(
        upfront_amount_min,
        upfront_amount_max,
        minimum_field="upfront_amount_min",
        maximum_field="upfront_amount_max",
    )
    total_potential_amount_min, total_potential_amount_max = _validated_number_range(
        total_potential_amount_min,
        total_potential_amount_max,
        minimum_field="total_potential_amount_min",
        maximum_field="total_potential_amount_max",
    )
    asset_modality = _normalized_repeated_filter(asset_modality)
    asset_program_tag = _normalized_repeated_filter(asset_program_tag)
    _assert_public_entity_ids_visible(
        session,
        principal,
        [asset_entity_id, target_entity_id, disease_entity_id, party_entity_id],
    )
    return _intelligence_service(session, principal).search_deals(
        q,
        deal_type,
        territory,
        party,
        limit,
        offset,
        status=deal_status.value if deal_status else None,
        direction=direction.value if direction else None,
        direction_reference_jurisdiction=direction_reference_jurisdiction,
        asset_entity_id=asset_entity_id,
        target_entity_id=target_entity_id,
        disease_entity_id=disease_entity_id,
        asset_modality=asset_modality,
        asset_program_tag=asset_program_tag,
        party_entity_id=party_entity_id,
        party_role=party_role.value if party_role else None,
        party_country_region=party_country_region,
        party_organization_type=party_organization_type,
        development_phase_at_transaction=(
            development_phase_at_transaction.value if development_phase_at_transaction else None
        ),
        current_development_phase=current_development_phase.value if current_development_phase else None,
        right_type=right_type.value if right_type else None,
        rights_territory=rights_territory,
        currency=currency,
        announced_from=announced_from,
        announced_to=announced_to,
        terminated_from=terminated_from,
        terminated_to=terminated_to,
        source_updated_from=source_updated_from,
        source_updated_to=source_updated_to,
        upfront_amount_min=upfront_amount_min,
        upfront_amount_max=upfront_amount_max,
        total_potential_amount_min=total_potential_amount_min,
        total_potential_amount_max=total_potential_amount_max,
        sort=effective_sort,
        landscape_limit=cast(DealAnalysisLimit, analysis_top),
    )


@router.get("/api/v1/deal-transactions/{deal_id}", response_model=DealSearchItemRead, tags=["deals"])
def get_deal_transaction(
    deal_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> DealSearchItemRead:
    principal.require("deals:read")
    deal = _intelligence_service(session, principal).deal_detail(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal transaction not found")
    return deal
