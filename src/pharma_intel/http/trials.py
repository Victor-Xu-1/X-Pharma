from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _assert_public_entity_ids_visible, _intelligence_service
from pharma_intel.http.query_contracts import (
    PipelineModalityQueryValue,
    PipelineProgramTagQueryValue,
    _normalized_repeated_filter,
    _validated_sort,
    _validated_trial_role_entity_filter,
    _validated_trial_role_entity_ids,
    _validated_utc_datetime_range,
)
from pharma_intel.models import DevelopmentPhase, TrialEntityRole, TrialResultEvaluation
from pharma_intel.schemas import (
    CLINICAL_TRIAL_SORT_FIELDS,
    ClinicalTrialDetailRead,
    ClinicalTrialRead,
    ClinicalTrialSearchResult,
    ClinicalTrialSortField,
    SortDirection,
    SortToken,
    TrialInitiationType,
    TrialTherapyLine,
)

router = APIRouter()


@router.get("/api/v1/clinical-trials", response_model=list[ClinicalTrialRead], tags=["clinical-trials"])
def search_clinical_trials(
    principal: PrincipalDep,
    session: SessionDep,
    entity_id: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    has_results: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[ClinicalTrialRead]:
    principal.require("trials:read")
    _assert_public_entity_ids_visible(session, principal, [entity_id])
    return _intelligence_service(session, principal).clinical_trials(
        entity_id,
        q,
        limit,
        has_results=has_results,
    )


@router.get("/api/v1/trials", response_model=ClinicalTrialSearchResult, tags=["trials"])
def search_trials(
    principal: PrincipalDep,
    session: SessionDep,
    q: str | None = Query(default=None, max_length=500),
    registry: str | None = Query(default=None, max_length=80),
    overall_status: str | None = Query(default=None, alias="status", max_length=100),
    phase: str | None = Query(default=None, max_length=80),
    study_type: str | None = Query(default=None, max_length=80),
    acronym: str | None = Query(default=None, max_length=240),
    initiation_type: TrialInitiationType | None = None,
    therapy_line: TrialTherapyLine | None = None,
    has_results: bool | None = Query(default=None),
    result_evaluation: TrialResultEvaluation | None = None,
    results_posted_from: Annotated[datetime | None, Query()] = None,
    results_posted_to: Annotated[datetime | None, Query()] = None,
    investigational_drug: str | None = Query(default=None, max_length=500),
    combination_drug: str | None = Query(default=None, max_length=500),
    investigational_target: str | None = Query(default=None, max_length=500),
    combination_target: str | None = Query(default=None, max_length=500),
    investigational_drug_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    combination_drug_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    investigational_target_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    combination_target_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    linked_drug_modality: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_innovation_type: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_category: Annotated[list[PipelineModalityQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_program_tag: Annotated[list[PipelineProgramTagQueryValue] | None, Query(max_length=20)] = None,
    linked_drug_global_phase: DevelopmentPhase | None = None,
    linked_drug_organization_country_region: str | None = Query(default=None, min_length=1, max_length=120),
    role_entity_id: str | None = Query(default=None, max_length=36),
    role_entity_ids: Annotated[list[str] | None, Query(max_length=20)] = None,
    role_entity_role: TrialEntityRole | None = None,
    has_key_result: bool | None = Query(default=None),
    publication_id: str | None = Query(default=None, max_length=240),
    conference: str | None = Query(default=None, max_length=500),
    disclosed_from: Annotated[datetime | None, Query()] = None,
    disclosed_to: Annotated[datetime | None, Query()] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    sort_by: ClinicalTrialSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> ClinicalTrialSearchResult:
    principal.require("trials:read")
    effective_sort = _validated_sort(
        sort,
        CLINICAL_TRIAL_SORT_FIELDS,
        default_field="last_update_posted",
        default_direction="desc",
        legacy_field=sort_by,
        legacy_direction=sort_direction,
    )
    results_posted_from, results_posted_to = _validated_utc_datetime_range(
        results_posted_from,
        results_posted_to,
        start_field="results_posted_from",
        end_field="results_posted_to",
    )
    disclosed_from, disclosed_to = _validated_utc_datetime_range(
        disclosed_from,
        disclosed_to,
        start_field="disclosed_from",
        end_field="disclosed_to",
    )
    role_entity_id, role_entity_ids, role_entity_role = _validated_trial_role_entity_filter(
        role_entity_id,
        role_entity_ids,
        role_entity_role,
    )
    investigational_drug_entity_ids = _validated_trial_role_entity_ids(
        "investigational_drug_entity_ids", investigational_drug_entity_ids
    )
    combination_drug_entity_ids = _validated_trial_role_entity_ids(
        "combination_drug_entity_ids", combination_drug_entity_ids
    )
    investigational_target_entity_ids = _validated_trial_role_entity_ids(
        "investigational_target_entity_ids", investigational_target_entity_ids
    )
    combination_target_entity_ids = _validated_trial_role_entity_ids(
        "combination_target_entity_ids", combination_target_entity_ids
    )
    linked_drug_modality = _normalized_repeated_filter(linked_drug_modality)
    linked_drug_innovation_type = _normalized_repeated_filter(linked_drug_innovation_type)
    linked_drug_category = _normalized_repeated_filter(linked_drug_category)
    linked_drug_program_tag = _normalized_repeated_filter(linked_drug_program_tag)
    _assert_public_entity_ids_visible(
        session,
        principal,
        [role_entity_id],
    )
    _assert_public_entity_ids_visible(
        session,
        principal,
        [
            *(role_entity_ids or []),
            *(investigational_drug_entity_ids or []),
            *(combination_drug_entity_ids or []),
            *(investigational_target_entity_ids or []),
            *(combination_target_entity_ids or []),
        ],
        reject_missing=False,
    )
    return _intelligence_service(session, principal).search_clinical_trials(
        q,
        registry,
        overall_status,
        phase,
        study_type,
        has_results,
        limit,
        offset,
        results_posted_from=results_posted_from,
        results_posted_to=results_posted_to,
        result_evaluation=result_evaluation.value if result_evaluation else None,
        acronym=acronym,
        initiation_type=initiation_type,
        therapy_line=therapy_line,
        investigational_drug=investigational_drug,
        combination_drug=combination_drug,
        investigational_target=investigational_target,
        combination_target=combination_target,
        investigational_drug_entity_ids=investigational_drug_entity_ids,
        combination_drug_entity_ids=combination_drug_entity_ids,
        investigational_target_entity_ids=investigational_target_entity_ids,
        combination_target_entity_ids=combination_target_entity_ids,
        linked_drug_modality=linked_drug_modality,
        linked_drug_innovation_type=linked_drug_innovation_type,
        linked_drug_category=linked_drug_category,
        linked_drug_program_tag=linked_drug_program_tag,
        linked_drug_global_phase=linked_drug_global_phase.value if linked_drug_global_phase else None,
        linked_drug_organization_country_region=linked_drug_organization_country_region,
        role_entity_id=role_entity_id,
        role_entity_ids=role_entity_ids,
        role_entity_role=role_entity_role.value if role_entity_role else None,
        has_key_result=has_key_result,
        publication_id=publication_id,
        conference=conference,
        disclosed_from=disclosed_from,
        disclosed_to=disclosed_to,
        sort=effective_sort,
    )


@router.get("/api/v1/trials/{trial_id}", response_model=ClinicalTrialDetailRead, tags=["trials"])
def get_trial_detail(
    trial_id: str,
    principal: PrincipalDep,
    session: SessionDep,
) -> ClinicalTrialDetailRead:
    principal.require("trials:read")
    result = _intelligence_service(session, principal).clinical_trial_detail(trial_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Clinical trial not found")
    return result
