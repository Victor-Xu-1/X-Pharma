from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Header, Query

from pharma_intel.http.agent_page import _agent_page
from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.http.public_read_policy import _intelligence_service
from pharma_intel.http.query_contracts import (
    PipelineModalityQueryValue,
    PipelineProgramTagQueryValue,
    _normalized_repeated_filter,
    _sort_reads,
    _validated_sort,
    _validated_trial_role_entity_filter,
    _validated_trial_role_entity_ids,
    _validated_utc_datetime_range,
)
from pharma_intel.models import DevelopmentPhase, TrialEntityRole, TrialResultEvaluation
from pharma_intel.schemas import (
    CLINICAL_TRIAL_SORT_FIELDS,
    AgentPageResult,
    ClinicalTrialSearchItemRead,
    ClinicalTrialSortField,
    SortDirection,
    SortToken,
    TrialInitiationType,
    TrialTherapyLine,
)

router = APIRouter()


@router.get(
    "/internal/v1/domain/clinical-trials",
    response_model=AgentPageResult[ClinicalTrialSearchItemRead],
    tags=["internal-domain"],
)
def search_clinical_trials_for_agent(
    principal: PrincipalDep,
    session: SessionDep,
    reservation_id: Annotated[
        str,
        Header(alias="X-Commercial-Reservation-ID", min_length=36, max_length=36),
    ],
    entity_id: str | None = Query(default=None, max_length=500),
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
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None, max_length=4096),
    sort_by: ClinicalTrialSortField | None = None,
    sort_direction: SortDirection | None = None,
    sort: Annotated[list[SortToken] | None, Query(max_length=5)] = None,
) -> AgentPageResult[ClinicalTrialSearchItemRead]:
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
    arguments: dict[str, object] = {
        "limit": limit,
        "sort": [clause.token for clause in effective_sort],
    }
    if entity_id is not None:
        arguments["entity_id"] = entity_id
    if q is not None:
        arguments["q"] = q
    if registry is not None:
        arguments["registry"] = registry
    if overall_status is not None:
        arguments["status"] = overall_status
    if phase is not None:
        arguments["phase"] = phase
    if study_type is not None:
        arguments["study_type"] = study_type
    if acronym is not None:
        arguments["acronym"] = acronym
    if initiation_type is not None:
        arguments["initiation_type"] = initiation_type
    if therapy_line is not None:
        arguments["therapy_line"] = therapy_line
    if has_results is not None:
        arguments["has_results"] = has_results
    if result_evaluation is not None:
        arguments["result_evaluation"] = result_evaluation.value
    if results_posted_from is not None:
        arguments["results_posted_from"] = results_posted_from.isoformat()
    if results_posted_to is not None:
        arguments["results_posted_to"] = results_posted_to.isoformat()
    for key, value in {
        "investigational_drug": investigational_drug,
        "combination_drug": combination_drug,
        "investigational_target": investigational_target,
        "combination_target": combination_target,
        "investigational_drug_entity_ids": investigational_drug_entity_ids,
        "combination_drug_entity_ids": combination_drug_entity_ids,
        "investigational_target_entity_ids": investigational_target_entity_ids,
        "combination_target_entity_ids": combination_target_entity_ids,
        "linked_drug_modality": linked_drug_modality,
        "linked_drug_innovation_type": linked_drug_innovation_type,
        "linked_drug_category": linked_drug_category,
        "linked_drug_program_tag": linked_drug_program_tag,
        "linked_drug_global_phase": linked_drug_global_phase.value if linked_drug_global_phase else None,
        "linked_drug_organization_country_region": linked_drug_organization_country_region,
        "role_entity_id": role_entity_id,
        "role_entity_ids": role_entity_ids,
        "role_entity_role": role_entity_role.value if role_entity_role else None,
        "has_key_result": has_key_result,
        "publication_id": publication_id,
        "conference": conference,
        "disclosed_from": disclosed_from.isoformat() if disclosed_from else None,
        "disclosed_to": disclosed_to.isoformat() if disclosed_to else None,
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
        billing_class="trial.search",
        arguments=arguments,
        page_size=limit,
        visible_entity_ids=[
            entity_id,
            role_entity_id,
        ],
        visible_filter_entity_ids=[
            *(role_entity_ids or []),
            *(investigational_drug_entity_ids or []),
            *(combination_drug_entity_ids or []),
            *(investigational_target_entity_ids or []),
            *(combination_target_entity_ids or []),
        ],
        fetch=lambda offset, fetch_limit: intelligence.clinical_trial_search_items(
            entity_id,
            q,
            registry,
            overall_status,
            phase,
            study_type,
            has_results,
            fetch_limit,
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
        ),
        sort=_sort_reads(effective_sort),
    )
