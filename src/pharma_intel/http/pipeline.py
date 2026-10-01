from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import (
    _assert_public_entity_ids_visible,
    _intelligence_service,
    _public_dossier_projection,
)
from pharma_intel.http.query_contracts import (
    PipelineModalityQueryValue,
    PipelineProgramTagQueryValue,
    _normalized_repeated_filter,
    _validated_pipeline_signal_filters,
    _validated_sort,
    _validated_utc_datetime_range,
)
from pharma_intel.models import DevelopmentPhase, EntityType, TrialResultEvaluation
from pharma_intel.research_activity import RESEARCH_ENTITY_RESOURCE_TYPE, RequestAuditResource
from pharma_intel.schemas import (
    PIPELINE_SORT_FIELDS,
    CompetitiveProgramRead,
    DrugProgramSearchResult,
    PipelineLandscapeStageScope,
    PipelineResultGrain,
    PipelineSearchResult,
    PipelineSortField,
    PipelineTargetAggregation,
    SortDirection,
    SortToken,
)

router = APIRouter()


@router.get(
    "/api/v1/drugs/{drug_id}/programs",
    response_model=DrugProgramSearchResult,
    response_model_exclude_none=True,
    tags=["drugs"],
)
def list_drug_programs(
    drug_id: str,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DrugProgramSearchResult:
    principal.require("pipelines:read")
    _assert_public_entity_ids_visible(session, principal, [drug_id])
    result = _intelligence_service(session, principal).drug_programs(drug_id, limit, offset)
    if result is None:
        raise HTTPException(status_code=404, detail="Drug not found")
    request.state.audit_resource = RequestAuditResource(
        resource_type=RESEARCH_ENTITY_RESOURCE_TYPE,
        resource_id=drug_id,
        details={"entity_type": EntityType.DRUG.value, "profile": "drug_programs", "offset": offset},
    )
    return _public_dossier_projection(result)


@router.get(
    "/api/v1/targets/{target_id}/competitive-programs",
    response_model=list[CompetitiveProgramRead],
    tags=["pipelines"],
)
def get_competitive_programs(
    target_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    limit: int = Query(default=500, ge=1, le=5000),
) -> list[CompetitiveProgramRead]:
    principal.require("pipelines:read")
    _assert_public_entity_ids_visible(session, principal, [target_id])
    return _intelligence_service(session, principal).competitive_programs(target_id, limit)


@router.get("/api/v1/pipelines", response_model=PipelineSearchResult, tags=["pipelines"])
def search_pipelines(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    modality: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    innovation_type: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    therapeutic_area: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    drug_category: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    program_status: Literal["active", "inactive", "unknown"] | None = None,
    organization_role: (
        Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"] | None
    ) = None,
    organization_type: str | None = Query(default=None, min_length=1, max_length=120),
    organization_country_region: str | None = Query(default=None, min_length=1, max_length=120),
    phase: DevelopmentPhase | None = None,
    geography: str | None = Query(default=None, min_length=1, max_length=120),
    status_date_from: Annotated[datetime | None, Query()] = None,
    status_date_to: Annotated[datetime | None, Query()] = None,
    drug_entity_id: str | None = Query(default=None, min_length=36, max_length=36),
    target_entity_id: str | None = Query(default=None, max_length=36),
    target_combination_key: str | None = Query(
        default=None,
        max_length=760,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?:\|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}){0,19}$",
    ),
    disease_entity_id: str | None = Query(default=None, max_length=36),
    organization_entity_id: str | None = Query(default=None, max_length=36),
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
    landscape_limit: int = Query(default=20, ge=5, le=200),
    landscape_stage_scope: PipelineLandscapeStageScope = "overall",
    landscape_target_aggregation: PipelineTargetAggregation = "all",
    result_grain: PipelineResultGrain = "program",
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> PipelineSearchResult:
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
    status_date_from, status_date_to = _validated_utc_datetime_range(
        status_date_from,
        status_date_to,
        start_field="status_date_from",
        end_field="status_date_to",
    )
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
    _assert_public_entity_ids_visible(
        session,
        principal,
        [
            drug_entity_id,
            target_entity_id,
            disease_entity_id,
            organization_entity_id,
            *(target_combination_key.split("|") if target_combination_key else []),
        ],
    )
    return _intelligence_service(session, principal).search_programs(
        q,
        modality,
        phase.value if phase else None,
        geography,
        limit,
        offset,
        innovation_type=innovation_type,
        therapeutic_area=therapeutic_area,
        drug_category=drug_category,
        program_status=program_status,
        organization_role=organization_role,
        organization_type=organization_type,
        organization_country_region=organization_country_region,
        status_date_from=status_date_from,
        status_date_to=status_date_to,
        drug_entity_id=drug_entity_id,
        target_entity_id=target_entity_id,
        target_combination_key=target_combination_key.lower() if target_combination_key else None,
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
        landscape_limit=landscape_limit,
        landscape_stage_scope=landscape_stage_scope,
        landscape_target_aggregation=landscape_target_aggregation,
        result_grain=result_grain,
    )
