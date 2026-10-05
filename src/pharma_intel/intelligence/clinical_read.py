from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select, true
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.clinical_semantics import TRIAL_ENTITY_LINK_PREDICATES
from pharma_intel.intelligence.clinical_filters import _clinical_trial_filters
from pharma_intel.intelligence.clinical_role_policy import asserted_trial_role
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.scope import _published_entity_exists
from pharma_intel.intelligence.vocabulary import _ordered_sort_expressions
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    Entity,
    Relationship,
    ReviewStatus,
    TrialResultDisclosureType,
    TrialResultEvaluation,
)
from pharma_intel.schemas import (
    CLINICAL_TRIAL_SORT_FIELDS,
    ClinicalTrialDetailRead,
    ClinicalTrialEntityRoleRead,
    ClinicalTrialLinkedEntityRead,
    ClinicalTrialRead,
    ClinicalTrialResultDisclosureRead,
    ClinicalTrialSearchItemRead,
    ClinicalTrialSortField,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def clinical_trials(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    limit: int,
    offset: int = 0,
    registry: str | None = None,
    overall_status: str | None = None,
    phase: str | None = None,
    study_type: str | None = None,
    has_results: bool | None = None,
) -> list[ClinicalTrialRead]:
    filters = _clinical_trial_filters(
        context,
        entity_id,
        query,
        registry=registry,
        overall_status=overall_status,
        phase=phase,
        study_type=study_type,
        has_results=has_results,
    )
    rows = context.session.scalars(
        select(ClinicalTrialProfile)
        .where(*filters)
        .order_by(
            ClinicalTrialProfile.last_update_posted.desc().nullslast(),
            ClinicalTrialProfile.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return [ClinicalTrialRead.model_validate(row) for row in rows]


def clinical_trial_search_items(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    registry: str | None,
    overall_status: str | None,
    phase: str | None,
    study_type: str | None,
    has_results: bool | None,
    limit: int,
    offset: int = 0,
    *,
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
) -> list[ClinicalTrialSearchItemRead]:
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
    return _clinical_trial_search_items(
        context,
        filters,
        limit,
        offset,
        sort=validate_sort_clauses(
            sort,
            CLINICAL_TRIAL_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        ),
    )


def clinical_trial_detail(context: QueryContext, trial_id: str) -> ClinicalTrialDetailRead | None:
    row = context.session.scalar(
        select(ClinicalTrialProfile).where(
            ClinicalTrialProfile.tenant_id == context.tenant_id,
            ClinicalTrialProfile.id == trial_id,
            _published_entity_exists(context, ClinicalTrialProfile.entity_id),
        )
    )
    if row is None:
        return None
    linked_entities = _clinical_trial_linked_entities(context, [row.entity_id]).get(row.entity_id, [])
    entity_roles = _clinical_trial_entity_roles(context, [row.id])[row.id]
    disclosures = _clinical_trial_result_disclosures(context, [row.id])[row.id]
    return ClinicalTrialDetailRead(
        **ClinicalTrialRead.model_validate(row).model_dump(),
        linked_entities=linked_entities,
        entity_roles=entity_roles,
        key_result_count=sum(1 for disclosure in disclosures if disclosure.is_key_result),
        latest_result_disclosure=disclosures[0] if disclosures else None,
        result_disclosures=disclosures,
    )


def _clinical_trial_search_items(
    context: QueryContext,
    filters: list[ColumnElement[bool]],
    limit: int,
    offset: int,
    *,
    sort_by: ClinicalTrialSortField = "last_update_posted",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[ClinicalTrialSortField]] | None = None,
) -> list[ClinicalTrialSearchItemRead]:
    effective_sort = validate_sort_clauses(
        sort,
        CLINICAL_TRIAL_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    sort_expressions: dict[ClinicalTrialSortField, Any] = {
        "last_update_posted": ClinicalTrialProfile.last_update_posted,
        "registry_id": func.lower(ClinicalTrialProfile.registry_id),
        "has_results": ClinicalTrialProfile.has_results,
        "result_evaluation": func.lower(ClinicalTrialProfile.result_evaluation),
        "overall_status": func.lower(ClinicalTrialProfile.overall_status),
        "enrollment": ClinicalTrialProfile.enrollment,
        "study_type": func.lower(ClinicalTrialProfile.study_type),
        "acronym": func.lower(ClinicalTrialProfile.acronym),
        "initiation_type": func.lower(ClinicalTrialProfile.initiation_type),
    }
    ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
    rows = context.session.scalars(
        select(ClinicalTrialProfile)
        .where(*filters)
        .order_by(
            *ordered_sort,
            ClinicalTrialProfile.registry_id,
            ClinicalTrialProfile.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    trial_ids = [row.id for row in rows]
    linked_by_trial = _clinical_trial_linked_entities(context, [row.entity_id for row in rows])
    entity_roles = _clinical_trial_entity_roles(context, trial_ids)
    disclosure_summaries = _clinical_trial_disclosure_summaries(context, trial_ids)
    return [
        ClinicalTrialSearchItemRead(
            **ClinicalTrialRead.model_validate(row).model_dump(),
            linked_entities=linked_by_trial[row.entity_id],
            entity_roles=entity_roles[row.id],
            key_result_count=disclosure_summaries[row.id]["key_result_count"],
            latest_result_disclosure=disclosure_summaries[row.id]["latest"],
        )
        for row in rows
    ]


def _clinical_trial_linked_entities(
    context: QueryContext,
    trial_entity_ids: list[str],
) -> dict[str, list[ClinicalTrialLinkedEntityRead]]:
    linked_by_trial: dict[str, list[ClinicalTrialLinkedEntityRead]] = {
        entity_id: [] for entity_id in dict.fromkeys(trial_entity_ids)
    }
    if trial_entity_ids:
        linked_rows = context.session.execute(
            select(Relationship.subject_id, Entity)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == context.tenant_id,
                    Entity.id == Relationship.object_id,
                ),
            )
            .where(
                Relationship.tenant_id == context.tenant_id,
                Relationship.predicate.in_(TRIAL_ENTITY_LINK_PREDICATES),
                Relationship.valid_to.is_(None),
                Relationship.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                _published_entity_exists(context, Entity.id),
                Relationship.subject_id.in_(trial_entity_ids),
            )
            .order_by(Relationship.subject_id, Entity.entity_type, Entity.name, Entity.id)
        ).all()
        for trial_entity_id, entity in linked_rows:
            linked_by_trial[trial_entity_id].append(
                ClinicalTrialLinkedEntityRead(
                    id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                )
            )
    return linked_by_trial


def _clinical_trial_entity_roles(
    context: QueryContext,
    trial_ids: list[str],
) -> dict[str, list[ClinicalTrialEntityRoleRead]]:
    roles_by_trial: dict[str, list[ClinicalTrialEntityRoleRead]] = {
        trial_id: [] for trial_id in dict.fromkeys(trial_ids)
    }
    if not trial_ids:
        return roles_by_trial
    rows = context.session.execute(
        select(ClinicalTrialEntityRole, Entity)
        .join(
            Entity,
            and_(
                Entity.tenant_id == context.tenant_id,
                Entity.id == ClinicalTrialEntityRole.entity_id,
            ),
        )
        .where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialEntityRole.trial_id.in_(roles_by_trial),
            asserted_trial_role(context),
            _published_entity_exists(context, Entity.id),
        )
        .order_by(ClinicalTrialEntityRole.trial_id, ClinicalTrialEntityRole.role, Entity.name, Entity.id)
    ).all()
    for association, entity in rows:
        roles_by_trial[association.trial_id].append(
            ClinicalTrialEntityRoleRead(
                entity_id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                role=association.role,
            )
        )
    return roles_by_trial


def _clinical_trial_result_disclosures(
    context: QueryContext,
    trial_ids: list[str],
) -> dict[str, list[ClinicalTrialResultDisclosureRead]]:
    disclosures_by_trial: dict[str, list[ClinicalTrialResultDisclosureRead]] = {
        trial_id: [] for trial_id in dict.fromkeys(trial_ids)
    }
    if not trial_ids:
        return disclosures_by_trial
    rows = context.session.scalars(
        select(ClinicalTrialResultDisclosure)
        .where(
            ClinicalTrialResultDisclosure.tenant_id == context.tenant_id,
            ClinicalTrialResultDisclosure.trial_id.in_(disclosures_by_trial),
        )
        .order_by(
            ClinicalTrialResultDisclosure.trial_id,
            ClinicalTrialResultDisclosure.disclosed_at.desc(),
            ClinicalTrialResultDisclosure.version.desc(),
            ClinicalTrialResultDisclosure.id,
        )
    ).all()
    for disclosure in rows:
        disclosures_by_trial[disclosure.trial_id].append(
            ClinicalTrialResultDisclosureRead(
                id=disclosure.id,
                disclosure_key=disclosure.disclosure_key,
                version=disclosure.version,
                disclosure_type=TrialResultDisclosureType(disclosure.disclosure_type),
                external_id=disclosure.external_id,
                title=disclosure.title,
                disclosed_at=disclosure.disclosed_at,
                conference_name=disclosure.conference_name,
                is_key_result=disclosure.is_key_result,
                result_evaluation=(
                    TrialResultEvaluation(disclosure.result_evaluation) if disclosure.result_evaluation else None
                ),
                source_locator=disclosure.source_locator,
                source_quote=disclosure.source_quote,
                source_document_id=disclosure.source_document_id,
            )
        )
    return disclosures_by_trial


def _clinical_trial_disclosure_summaries(context: QueryContext, trial_ids: list[str]) -> dict[str, dict[str, Any]]:
    disclosures_by_trial = _clinical_trial_result_disclosures(context, trial_ids)
    return {
        trial_id: {
            "key_result_count": sum(1 for disclosure in disclosures if disclosure.is_key_result),
            "latest": disclosures[0] if disclosures else None,
        }
        for trial_id, disclosures in disclosures_by_trial.items()
    }
