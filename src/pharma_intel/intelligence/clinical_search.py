from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, literal, select

from pharma_intel.intelligence.clinical_filters import _clinical_trial_filters
from pharma_intel.intelligence.clinical_landscape import (
    _clinical_trial_landscape,
    _clinical_trial_linked_drug_program_facets,
)
from pharma_intel.intelligence.clinical_read import _clinical_trial_search_items
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import _applied_filters, _json_array_facets, _scalar_facet_counts
from pharma_intel.intelligence.vocabulary import _sort_criteria_read
from pharma_intel.models import ClinicalTrialProfile, ClinicalTrialResultDisclosure
from pharma_intel.program_semantics import public_program_tags
from pharma_intel.schemas import (
    CLINICAL_TRIAL_SORT_FIELDS,
    ClinicalTrialSavedSearchQuery,
    ClinicalTrialSearchResult,
    ClinicalTrialSortField,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def clinical_trial_saved_search_matches_entity(
    context: QueryContext,
    entity_id: str,
    query: ClinicalTrialSavedSearchQuery,
) -> bool:
    def start(value: Any) -> datetime | None:
        return datetime.combine(value, time.min, tzinfo=UTC) if value else None

    def end(value: Any) -> datetime | None:
        return datetime.combine(value, time.max, tzinfo=UTC) if value else None

    filters = _clinical_trial_filters(
        context,
        entity_id,
        query.q,
        registry=query.registry,
        overall_status=query.status,
        phase=query.phase,
        study_type=query.study_type,
        acronym=query.acronym,
        initiation_type=query.initiation_type,
        therapy_line=query.therapy_line,
        has_results=query.has_results,
        results_posted_from=start(query.results_posted_from),
        results_posted_to=end(query.results_posted_to),
        result_evaluation=query.result_evaluation.value if query.result_evaluation else None,
        investigational_drug=query.investigational_drug,
        combination_drug=query.combination_drug,
        investigational_target=query.investigational_target,
        combination_target=query.combination_target,
        investigational_drug_entity_ids=query.investigational_drug_entity_ids,
        combination_drug_entity_ids=query.combination_drug_entity_ids,
        investigational_target_entity_ids=query.investigational_target_entity_ids,
        combination_target_entity_ids=query.combination_target_entity_ids,
        linked_drug_modality=query.linked_drug_modality,
        linked_drug_innovation_type=query.linked_drug_innovation_type,
        linked_drug_category=query.linked_drug_category,
        linked_drug_program_tag=query.linked_drug_program_tag,
        linked_drug_global_phase=query.linked_drug_global_phase,
        linked_drug_organization_country_region=query.linked_drug_organization_country_region,
        role_entity_id=query.role_entity_id,
        role_entity_ids=query.role_entity_ids,
        role_entity_role=query.role_entity_role.value if query.role_entity_role else None,
        has_key_result=query.has_key_result,
        publication_id=query.publication_id,
        conference=query.conference,
        disclosed_from=start(query.disclosed_from),
        disclosed_to=end(query.disclosed_to),
    )
    statement = select(ClinicalTrialProfile.id).where(*filters).limit(1)
    return context.session.scalar(statement.with_only_columns(literal(True))) is True


def search_clinical_trials(
    context: QueryContext,
    query: str | None,
    registry: str | None,
    overall_status: str | None,
    phase: str | None,
    study_type: str | None,
    has_results: bool | None,
    limit: int,
    offset: int,
    *,
    entity_id: str | None = None,
    results_posted_from: datetime | None = None,
    results_posted_to: datetime | None = None,
    result_evaluation: str | None = None,
    acronym: str | None = None,
    initiation_type: str | None = None,
    therapy_line: str | None = None,
    investigational_drug: str | None = None,
    combination_drug: str | None = None,
    investigational_target: str | None = None,
    combination_target: str | None = None,
    investigational_drug_entity_ids: list[str] | None = None,
    combination_drug_entity_ids: list[str] | None = None,
    investigational_target_entity_ids: list[str] | None = None,
    combination_target_entity_ids: list[str] | None = None,
    linked_drug_modality: list[str] | None = None,
    linked_drug_innovation_type: list[str] | None = None,
    linked_drug_category: list[str] | None = None,
    linked_drug_program_tag: list[str] | None = None,
    linked_drug_global_phase: str | None = None,
    linked_drug_organization_country_region: str | None = None,
    role_entity_id: str | None = None,
    role_entity_ids: list[str] | None = None,
    role_entity_role: str | None = None,
    has_key_result: bool | None = None,
    publication_id: str | None = None,
    conference: str | None = None,
    disclosed_from: datetime | None = None,
    disclosed_to: datetime | None = None,
    sort_by: ClinicalTrialSortField = "last_update_posted",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[ClinicalTrialSortField]] | None = None,
) -> ClinicalTrialSearchResult:
    effective_sort = validate_sort_clauses(
        sort,
        CLINICAL_TRIAL_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    filters = _clinical_trial_filters(
        context,
        entity_id,
        query,
        registry=registry,
        overall_status=overall_status,
        phase=phase,
        study_type=study_type,
        acronym=acronym,
        initiation_type=initiation_type,
        therapy_line=therapy_line,
        has_results=has_results,
        results_posted_from=results_posted_from,
        results_posted_to=results_posted_to,
        result_evaluation=result_evaluation,
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
        linked_drug_global_phase=linked_drug_global_phase,
        linked_drug_organization_country_region=linked_drug_organization_country_region,
        role_entity_id=role_entity_id,
        role_entity_ids=role_entity_ids,
        role_entity_role=role_entity_role,
        has_key_result=has_key_result,
        publication_id=publication_id,
        conference=conference,
        disclosed_from=disclosed_from,
        disclosed_to=disclosed_to,
    )
    items = _clinical_trial_search_items(
        context,
        filters,
        limit,
        offset,
        sort=effective_sort,
    )
    facet_source = (
        select(
            ClinicalTrialProfile.id.label("trial_id"),
            ClinicalTrialProfile.registry_name.label("registry"),
            ClinicalTrialProfile.overall_status.label("overall_status"),
            ClinicalTrialProfile.study_type.label("study_type"),
            ClinicalTrialProfile.initiation_type.label("initiation_type"),
            ClinicalTrialProfile.therapy_lines.label("therapy_lines"),
            ClinicalTrialProfile.phases.label("phases"),
            ClinicalTrialProfile.has_results.label("has_results"),
            ClinicalTrialProfile.result_evaluation.label("result_evaluation"),
            func.coalesce(
                select(func.max(ClinicalTrialResultDisclosure.disclosed_at))
                .where(
                    ClinicalTrialResultDisclosure.tenant_id == context.tenant_id,
                    ClinicalTrialResultDisclosure.trial_id == ClinicalTrialProfile.id,
                )
                .scalar_subquery(),
                ClinicalTrialProfile.results_first_posted,
            ).label("published_at"),
            select(ClinicalTrialResultDisclosure.id)
            .where(
                ClinicalTrialResultDisclosure.tenant_id == context.tenant_id,
                ClinicalTrialResultDisclosure.trial_id == ClinicalTrialProfile.id,
                ClinicalTrialResultDisclosure.is_key_result.is_(True),
            )
            .exists()
            .label("has_key_result"),
        )
        .where(*filters)
        .subquery()
    )
    total = context.session.scalar(select(func.count()).select_from(facet_source)) or 0
    facets = {
        name: _scalar_facet_counts(context, facet_source, name)
        for name in (
            "registry",
            "overall_status",
            "study_type",
            "initiation_type",
            "has_results",
            "result_evaluation",
            "has_key_result",
        )
    }
    facets["phase"] = _json_array_facets(context, facet_source, "phases", "trial_id")
    facets["therapy_line"] = _json_array_facets(context, facet_source, "therapy_lines", "trial_id")
    facets.update(
        {
            name: counts
            for name, counts in _clinical_trial_linked_drug_program_facets(context, facet_source).items()
            if counts
        }
    )
    landscape = _clinical_trial_landscape(context, facet_source, total)
    return ClinicalTrialSearchResult(
        query_schema_version="pharma.clinical_trial.search.v10",
        applied_filters=_applied_filters(
            ("entity_id", "eq", entity_id),
            ("q", "contains", query.strip() if query else None),
            ("registry", "eq", registry),
            ("status", "eq", overall_status),
            ("phase", "eq", phase),
            ("study_type", "eq", study_type),
            ("acronym", "contains", acronym),
            ("initiation_type", "eq", initiation_type),
            ("therapy_line", "eq", therapy_line),
            ("has_results", "eq", has_results),
            ("result_evaluation", "eq", result_evaluation),
            ("investigational_drug", "contains", investigational_drug),
            ("combination_drug", "contains", combination_drug),
            ("investigational_target", "contains", investigational_target),
            ("combination_target", "contains", combination_target),
            ("investigational_drug_entity_ids", "in", investigational_drug_entity_ids),
            ("combination_drug_entity_ids", "in", combination_drug_entity_ids),
            ("investigational_target_entity_ids", "in", investigational_target_entity_ids),
            ("combination_target_entity_ids", "in", combination_target_entity_ids),
            ("linked_drug_modality", "in", linked_drug_modality),
            ("linked_drug_innovation_type", "in", linked_drug_innovation_type),
            ("linked_drug_category", "in", linked_drug_category),
            ("linked_drug_program_tag", "in", public_program_tags(linked_drug_program_tag)),
            ("linked_drug_global_phase", "eq", linked_drug_global_phase),
            (
                "linked_drug_organization_country_region",
                "eq",
                linked_drug_organization_country_region,
            ),
            ("role_entity_id", "eq", role_entity_id),
            ("role_entity_ids", "in", role_entity_ids),
            ("role_entity_role", "eq", role_entity_role),
            ("has_key_result", "eq", has_key_result),
            ("publication_id", "eq", publication_id),
            ("conference", "contains", conference),
            ("disclosed_from", "gte", disclosed_from.isoformat() if disclosed_from else None),
            ("disclosed_to", "lte", disclosed_to.isoformat() if disclosed_to else None),
            (
                "results_posted_from",
                "gte",
                results_posted_from.isoformat() if results_posted_from else None,
            ),
            ("results_posted_to", "lte", results_posted_to.isoformat() if results_posted_to else None),
        ),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        sort_by=effective_sort[0].field,
        sort_direction=effective_sort[0].direction,
        sort=_sort_criteria_read(effective_sort),
        facets=facets,
        landscape=landscape,
        as_of=datetime.now(UTC),
        warnings=["未观察到试验不代表全球不存在；结果受数据授权、注册平台时效和治理状态限制。"],
    )
