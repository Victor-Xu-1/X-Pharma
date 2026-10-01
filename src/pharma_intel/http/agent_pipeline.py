from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.http.query_contracts import (
    PipelineModalityQueryValue,
    PipelineProgramTagQueryValue,
    _normalized_repeated_filter,
    _sort_reads,
    _validated_pipeline_signal_filters,
    _validated_sort,
    _validated_utc_datetime_range,
)
from pharma_intel.models import DevelopmentPhase, TrialResultEvaluation
from pharma_intel.schemas import (
    PIPELINE_SORT_FIELDS,
    AgentPageResult,
    CompetitiveProgramRead,
    PipelineSortField,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/targets/{target_id}/competitive-programs",
    response_model=AgentPageResult[CompetitiveProgramRead],
    tags=["internal-domain"],
)
def search_competitive_programs_for_agent(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    drug_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    disease_entity_id: str | None = Query(default=None, max_length=36),
    organization_entity_id: str | None = Query(default=None, max_length=36),
    program_status: Literal["active", "inactive", "unknown"] | None = None,
    organization_role: (
        Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"] | None
    ) = None,
    organization_type: str | None = Query(default=None, min_length=1, max_length=120),
    organization_country_region: str | None = Query(default=None, min_length=1, max_length=120),
    modality: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    innovation_type: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    therapeutic_area: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    drug_category: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    global_phase: DevelopmentPhase | None = None,
    china_phase: DevelopmentPhase | None = None,
    global_phase_started_from: Annotated[datetime | None, Query()] = None,
    global_phase_started_to: Annotated[datetime | None, Query()] = None,
    china_phase_started_from: Annotated[datetime | None, Query()] = None,
    china_phase_started_to: Annotated[datetime | None, Query()] = None,
    development_rights_region: str | None = Query(default=None, max_length=240),
    commercialization_rights_region: str | None = Query(default=None, max_length=240),
    program_tag: Annotated[list[PipelineProgramTagQueryValue] | None, Query(max_length=20)] = None,
    milestone_type: str | None = Query(default=None, max_length=120),
    milestone_from: Annotated[datetime | None, Query()] = None,
    milestone_to: Annotated[datetime | None, Query()] = None,
    has_clinical_results: bool | None = Query(default=None),
    clinical_result_evaluation: TrialResultEvaluation | None = None,
    has_deal: bool | None = Query(default=None),
    deal_currency: str | None = Query(default=None, pattern=r"^[A-Z]{3}$"),
    deal_total_potential_amount_min: float | None = Query(default=None, ge=0),
    deal_total_potential_amount_max: float | None = Query(default=None, ge=0),
    sort_by: PipelineSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[CompetitiveProgramRead]:
    principal.require("pipelines:read")
    effective_sort = _validated_sort(
        sort,
        PIPELINE_SORT_FIELDS,
        default_field="status_date",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    modality = _normalized_repeated_filter(modality)
    innovation_type = _normalized_repeated_filter(innovation_type)
    therapeutic_area = _normalized_repeated_filter(therapeutic_area)
    drug_category = _normalized_repeated_filter(drug_category)
    program_tag = _normalized_repeated_filter(program_tag)
    arguments: dict[str, object] = {"target_entity_id": target_id, "limit": limit}
    global_phase_started_from, global_phase_started_to = _validated_utc_datetime_range(
        global_phase_started_from,
        global_phase_started_to,
        start_field="global_phase_started_from",
        end_field="global_phase_started_to",
    )
    china_phase_started_from, china_phase_started_to = _validated_utc_datetime_range(
        china_phase_started_from,
        china_phase_started_to,
        start_field="china_phase_started_from",
        end_field="china_phase_started_to",
    )
    milestone_from, milestone_to = _validated_utc_datetime_range(
        milestone_from,
        milestone_to,
        start_field="milestone_from",
        end_field="milestone_to",
    )
    deal_total_potential_amount_min, deal_total_potential_amount_max = _validated_pipeline_signal_filters(
        has_clinical_results,
        clinical_result_evaluation,
        has_deal,
        deal_currency,
        deal_total_potential_amount_min,
        deal_total_potential_amount_max,
    )
    filters: dict[str, object | None] = {
        "drug_entity_id": drug_entity_id,
        "disease_entity_id": disease_entity_id,
        "organization_entity_id": organization_entity_id,
        "program_status": program_status,
        "organization_role": organization_role,
        "organization_type": organization_type,
        "organization_country_region": organization_country_region,
        "modality": modality,
        "innovation_type": innovation_type,
        "therapeutic_area": therapeutic_area,
        "drug_category": drug_category,
        "global_phase": global_phase.value if global_phase else None,
        "china_phase": china_phase.value if china_phase else None,
        "global_phase_started_from": global_phase_started_from,
        "global_phase_started_to": global_phase_started_to,
        "china_phase_started_from": china_phase_started_from,
        "china_phase_started_to": china_phase_started_to,
        "development_rights_region": development_rights_region,
        "commercialization_rights_region": commercialization_rights_region,
        "program_tag": program_tag,
        "milestone_type": milestone_type,
        "milestone_from": milestone_from,
        "milestone_to": milestone_to,
        "has_clinical_results": has_clinical_results,
        "clinical_result_evaluation": clinical_result_evaluation.value if clinical_result_evaluation else None,
        "has_deal": has_deal,
        "deal_currency": deal_currency,
        "deal_total_potential_amount_min": deal_total_potential_amount_min,
        "deal_total_potential_amount_max": deal_total_potential_amount_max,
        "sort": [clause.token for clause in effective_sort],
    }
    arguments.update(
        {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in filters.items()
            if value is not None
        }
    )
    if cursor is not None:
        arguments["cursor"] = cursor
    intelligence = _intelligence_service(session, principal)
    return _agent_page(
        principal,
        session,
        reservation_id,
        billing_class="pipeline.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[target_id, drug_entity_id, disease_entity_id, organization_entity_id],
        fetch=lambda offset, fetch_limit: intelligence.search_programs(
            None,
            modality,
            None,
            None,
            fetch_limit,
            offset,
            innovation_type=innovation_type,
            therapeutic_area=therapeutic_area,
            drug_category=drug_category,
            program_status=program_status,
            organization_role=organization_role,
            organization_type=organization_type,
            organization_country_region=organization_country_region,
            drug_entity_id=drug_entity_id,
            target_entity_id=target_id,
            disease_entity_id=disease_entity_id,
            organization_entity_id=organization_entity_id,
            global_phase=global_phase.value if global_phase else None,
            china_phase=china_phase.value if china_phase else None,
            global_phase_started_from=global_phase_started_from,
            global_phase_started_to=global_phase_started_to,
            china_phase_started_from=china_phase_started_from,
            china_phase_started_to=china_phase_started_to,
            development_rights_region=development_rights_region,
            commercialization_rights_region=commercialization_rights_region,
            program_tag=program_tag,
            milestone_type=milestone_type,
            milestone_from=milestone_from,
            milestone_to=milestone_to,
            has_clinical_results=has_clinical_results,
            clinical_result_evaluation=(clinical_result_evaluation.value if clinical_result_evaluation else None),
            has_deal=has_deal,
            deal_currency=deal_currency,
            deal_total_potential_amount_min=deal_total_potential_amount_min,
            deal_total_potential_amount_max=deal_total_potential_amount_max,
            sort=effective_sort,
        ).items,
        sort=_sort_reads(effective_sort),
    )
