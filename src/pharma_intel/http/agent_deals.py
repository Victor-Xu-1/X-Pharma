from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.http.query_contracts import (
    DealAssetModalityQueryValue,
    DealAssetProgramTagQueryValue,
    _normalized_repeated_filter,
    _sort_reads,
    _validate_deal_amount_sort,
    _validated_number_range,
    _validated_sort,
    _validated_utc_datetime_range,
)
from pharma_intel.models import DealDirection, DealPartyRole, DealRightType, DealStatus, DevelopmentPhase
from pharma_intel.schemas import (
    DEAL_SORT_FIELDS,
    AgentPageResult,
    CompanyTimelineEventRead,
    DealSearchItemRead,
    DealSortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/deals",
    response_model=AgentPageResult[DealSearchItemRead],
    tags=["internal-domain"],
)
def search_deals_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
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
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: DealSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[DealSearchItemRead]:
    principal.require("deals:read")
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
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if q is not None:
        arguments["q"] = q
    if deal_type is not None:
        arguments["deal_type"] = deal_type
    for key, value in {
        "status": deal_status.value if deal_status else None,
        "direction": direction.value if direction else None,
        "direction_reference_jurisdiction": direction_reference_jurisdiction,
        "territory": territory,
        "asset_entity_id": asset_entity_id,
        "target_entity_id": target_entity_id,
        "disease_entity_id": disease_entity_id,
        "asset_modality": asset_modality,
        "asset_program_tag": asset_program_tag,
        "party": party,
        "party_entity_id": party_entity_id,
        "party_role": party_role.value if party_role else None,
        "party_country_region": party_country_region,
        "party_organization_type": party_organization_type,
        "development_phase_at_transaction": (
            development_phase_at_transaction.value if development_phase_at_transaction else None
        ),
        "current_development_phase": current_development_phase.value if current_development_phase else None,
        "right_type": right_type.value if right_type else None,
        "rights_territory": rights_territory,
        "currency": currency,
        "announced_from": announced_from.isoformat() if announced_from else None,
        "announced_to": announced_to.isoformat() if announced_to else None,
        "terminated_from": terminated_from.isoformat() if terminated_from else None,
        "terminated_to": terminated_to.isoformat() if terminated_to else None,
        "source_updated_from": source_updated_from.isoformat() if source_updated_from else None,
        "source_updated_to": source_updated_to.isoformat() if source_updated_to else None,
        "upfront_amount_min": upfront_amount_min,
        "upfront_amount_max": upfront_amount_max,
        "total_potential_amount_min": total_potential_amount_min,
        "total_potential_amount_max": total_potential_amount_max,
    }.items():
        if value is not None:
            arguments[key] = value
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="deal.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[
            entity_id,
            asset_entity_id,
            target_entity_id,
            disease_entity_id,
            party_entity_id,
        ],
        fetch=lambda offset, fetch_limit: intelligence.deal_search_items(
            entity_id,
            q,
            deal_type,
            territory,
            party,
            fetch_limit,
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
        ),
        sort=_sort_reads(effective_sort),
    )


@router.get(
    "/internal/v1/domain/companies/{company_id}/timeline",
    response_model=AgentPageResult[CompanyTimelineEventRead],
    tags=["internal-domain"],
)
def get_company_timeline_for_agent(
    company_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
) -> AgentPageResult[CompanyTimelineEventRead]:
    principal.require("pipelines:read")
    principal.require("deals:read")
    arguments: dict[str, object] = {"company_entity_id": company_id, "limit": limit}
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)

    def fetch(offset: int, fetch_limit: int) -> list[CompanyTimelineEventRead]:
        result = intelligence.company_timeline(company_id, fetch_limit, offset)
        if result is None:
            raise HTTPException(status_code=404, detail="Company not found")
        return result.items

    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="company.timeline",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[company_id],
        fetch=fetch,
    )
