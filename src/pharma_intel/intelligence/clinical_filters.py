from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, and_, cast, func, literal, or_, select, true
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import _json_array_value_exists
from pharma_intel.intelligence.scope import _entity_identity_ids, _published_entity_exists, _published_identity_exists
from pharma_intel.intelligence.vocabulary import (
    _TRIAL_DRUG_ROLES,
    _public_program_drug_category_sql,
    _public_program_modality_sql,
)
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityType,
    Relationship,
    ReviewStatus,
)
from pharma_intel.program_semantics import public_program_tags


def _clinical_trial_target_program_exists(context: QueryContext, target_entity_id: str) -> ColumnElement[bool]:
    role_drug = Entity.__table__.alias("target_trial_role_drug")
    program_drug = Entity.__table__.alias("target_trial_program_drug")
    target_identity_ids = _entity_identity_ids(context, target_entity_id, EntityType.TARGET)
    current_target = (
        select(DevelopmentProgramTarget.id)
        .where(
            DevelopmentProgramTarget.tenant_id == context.tenant_id,
            DevelopmentProgramTarget.program_id == DevelopmentProgram.id,
            DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
            DevelopmentProgramTarget.target_entity_id.in_(target_identity_ids),
        )
        .exists()
    )
    conditions: list[ColumnElement[bool]] = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        or_(DevelopmentProgram.target_entity_id.in_(target_identity_ids), current_target),
        ClinicalTrialEntityRole.tenant_id == context.tenant_id,
        ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
        ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
        role_drug.c.normalized_name == program_drug.c.normalized_name,
    ]
    if not context.include_unpublished:
        conditions.extend(
            [
                role_drug.c.review_status == ReviewStatus.VERIFIED,
                _published_identity_exists(
                    context,
                    DevelopmentProgram.drug_entity_id,
                    EntityType.DRUG,
                    correlate_from=DevelopmentProgram.__table__,
                ),
            ]
        )
    return (
        select(DevelopmentProgram.id)
        .join(
            program_drug,
            and_(
                program_drug.c.tenant_id == context.tenant_id,
                program_drug.c.id == DevelopmentProgram.drug_entity_id,
                program_drug.c.entity_type == EntityType.DRUG,
            ),
        )
        .join(
            role_drug,
            and_(
                role_drug.c.tenant_id == context.tenant_id,
                role_drug.c.entity_type == EntityType.DRUG,
            ),
        )
        .join(
            ClinicalTrialEntityRole,
            ClinicalTrialEntityRole.entity_id == role_drug.c.id,
        )
        .where(*conditions)
        .exists()
    )


def _clinical_trial_filters(
    context: QueryContext,
    entity_id: str | None,
    query: str | None,
    *,
    registry: str | None = None,
    overall_status: str | None = None,
    phase: str | None = None,
    study_type: str | None = None,
    acronym: str | None = None,
    initiation_type: str | None = None,
    therapy_line: str | None = None,
    has_results: bool | None = None,
    results_posted_from: datetime | None = None,
    results_posted_to: datetime | None = None,
    result_evaluation: str | None = None,
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
) -> list[ColumnElement[bool]]:
    filters = [
        ClinicalTrialProfile.tenant_id == context.tenant_id,
        _published_entity_exists(context, ClinicalTrialProfile.entity_id),
    ]
    if entity_id:
        linked_trial_ids = select(Relationship.subject_id).where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.predicate == "trial_links_entity",
            Relationship.object_id == entity_id,
        )
        role_linked_trial_ids = select(ClinicalTrialEntityRole.trial_id).where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialEntityRole.entity_id == entity_id,
        )
        entity_type = context.session.scalar(
            select(Entity.entity_type).where(
                Entity.tenant_id == context.tenant_id,
                Entity.id == entity_id,
            )
        )
        entity_matches: list[ColumnElement[bool]] = [
            ClinicalTrialProfile.entity_id == entity_id,
            ClinicalTrialProfile.entity_id.in_(linked_trial_ids),
            ClinicalTrialProfile.id.in_(role_linked_trial_ids),
        ]
        if entity_type == EntityType.TARGET:
            entity_matches.append(_clinical_trial_target_program_exists(context, entity_id))
        filters.append(or_(*entity_matches))
    if query and (normalized_query := query.strip().casefold()):
        linked_entity_match = (
            select(Relationship.id)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == context.tenant_id,
                    Entity.id == Relationship.object_id,
                ),
            )
            .where(
                Relationship.tenant_id == context.tenant_id,
                Relationship.predicate == "trial_links_entity",
                Relationship.subject_id == ClinicalTrialProfile.entity_id,
                Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
                func.lower(Entity.name).contains(normalized_query, autoescape=True),
            )
            .exists()
        )
        filters.append(
            or_(
                func.lower(ClinicalTrialProfile.official_title).contains(normalized_query, autoescape=True),
                func.lower(ClinicalTrialProfile.acronym).contains(normalized_query, autoescape=True),
                func.lower(ClinicalTrialProfile.registry_id).contains(normalized_query, autoescape=True),
                func.lower(cast(ClinicalTrialProfile.conditions, String)).contains(normalized_query, autoescape=True),
                func.lower(cast(ClinicalTrialProfile.interventions, String)).contains(
                    normalized_query, autoescape=True
                ),
                func.lower(cast(ClinicalTrialProfile.sponsors, String)).contains(normalized_query, autoescape=True),
                linked_entity_match,
            )
        )
    if registry:
        filters.append(ClinicalTrialProfile.registry_name == registry)
    if overall_status:
        filters.append(ClinicalTrialProfile.overall_status == overall_status)
    if phase:
        filters.append(cast(ClinicalTrialProfile.phases, String).contains(f'"{phase}"', autoescape=True))
    if study_type:
        filters.append(ClinicalTrialProfile.study_type == study_type)
    if acronym and (normalized_acronym := acronym.strip().casefold()):
        filters.append(func.lower(ClinicalTrialProfile.acronym).contains(normalized_acronym, autoescape=True))
    if initiation_type:
        filters.append(ClinicalTrialProfile.initiation_type == initiation_type)
    if therapy_line:
        filters.append(_json_array_value_exists(context, ClinicalTrialProfile.therapy_lines, therapy_line))
    if has_results is not None:
        filters.append(ClinicalTrialProfile.has_results.is_(has_results))
    if result_evaluation:
        filters.append(ClinicalTrialProfile.result_evaluation == result_evaluation)
    if results_posted_from:
        filters.append(ClinicalTrialProfile.results_first_posted >= results_posted_from)
    if results_posted_to:
        filters.append(ClinicalTrialProfile.results_first_posted <= results_posted_to)
    for role, name in (
        ("investigational_drug", investigational_drug),
        ("combination_drug", combination_drug),
        ("investigational_target", investigational_target),
        ("combination_target", combination_target),
    ):
        if name and (normalized_name := name.strip().casefold()):
            filters.append(_clinical_trial_role_name_exists(context, role, normalized_name))
    for role, entity_ids in (
        ("investigational_drug", investigational_drug_entity_ids),
        ("combination_drug", combination_drug_entity_ids),
        ("investigational_target", investigational_target_entity_ids),
        ("combination_target", combination_target_entity_ids),
    ):
        if entity_ids:
            filters.append(_clinical_trial_role_entities_exist(context, entity_ids, role))
    if any(
        (
            linked_drug_modality,
            linked_drug_innovation_type,
            linked_drug_category,
            linked_drug_program_tag,
            linked_drug_global_phase,
            linked_drug_organization_country_region,
        )
    ):
        filters.append(
            _clinical_trial_linked_drug_program_exists(
                context,
                modalities=linked_drug_modality,
                innovation_types=linked_drug_innovation_type,
                drug_categories=linked_drug_category,
                program_tags=linked_drug_program_tag,
                global_phase=linked_drug_global_phase,
                organization_country_region=linked_drug_organization_country_region,
            )
        )
    if role_entity_id and role_entity_ids:
        raise ValueError("role_entity_id cannot be combined with role_entity_ids")
    if role_entity_role and not role_entity_id and not role_entity_ids:
        raise ValueError("role_entity_role requires role_entity_id or role_entity_ids")
    if role_entity_id:
        filters.append(_clinical_trial_role_entity_exists(context, role_entity_id, role_entity_role))
    if role_entity_ids:
        filters.append(_clinical_trial_role_entities_exist(context, role_entity_ids, role_entity_role))
    disclosure_conditions: list[ColumnElement[bool]] = []
    if publication_id and (normalized_publication_id := publication_id.strip().casefold()):
        disclosure_conditions.append(func.lower(ClinicalTrialResultDisclosure.external_id) == normalized_publication_id)
    if conference and (normalized_conference := conference.strip().casefold()):
        disclosure_conditions.append(
            func.lower(ClinicalTrialResultDisclosure.conference_name).contains(
                normalized_conference,
                autoescape=True,
            )
        )
    if disclosed_from:
        disclosure_conditions.append(ClinicalTrialResultDisclosure.disclosed_at >= disclosed_from)
    if disclosed_to:
        disclosure_conditions.append(ClinicalTrialResultDisclosure.disclosed_at <= disclosed_to)
    if disclosure_conditions:
        filters.append(_clinical_trial_disclosure_exists(context, *disclosure_conditions))
    if has_key_result is not None:
        key_result_exists = _clinical_trial_disclosure_exists(
            context, ClinicalTrialResultDisclosure.is_key_result.is_(True)
        )
        filters.append(key_result_exists if has_key_result else ~key_result_exists)
    return filters


def _clinical_trial_role_name_exists(context: QueryContext, role: str, normalized_name: str) -> ColumnElement[bool]:
    return (
        select(ClinicalTrialEntityRole.id)
        .join(
            Entity,
            and_(
                Entity.tenant_id == context.tenant_id,
                Entity.id == ClinicalTrialEntityRole.entity_id,
            ),
        )
        .where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
            ClinicalTrialEntityRole.role == role,
            Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
            func.lower(Entity.name).contains(normalized_name, autoescape=True),
        )
        .exists()
    )


def _clinical_trial_linked_drug_program_exists(
    context: QueryContext,
    *,
    modalities: list[str] | None,
    innovation_types: list[str] | None,
    drug_categories: list[str] | None,
    program_tags: list[str] | None,
    global_phase: str | None,
    organization_country_region: str | None,
) -> ColumnElement[bool]:
    program_conditions: list[ColumnElement[bool]] = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        ClinicalTrialEntityRole.tenant_id == context.tenant_id,
        ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
        ClinicalTrialEntityRole.role.in_(("investigational_drug", "combination_drug")),
        ClinicalTrialEntityRole.entity_id == DevelopmentProgram.drug_entity_id,
    ]
    if not context.include_unpublished:
        program_conditions.append(_published_entity_exists(context, DevelopmentProgram.drug_entity_id))
    public_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    public_drug_category = _public_program_drug_category_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    if modalities:
        program_conditions.append(public_modality.in_(modalities))
    if innovation_types:
        program_conditions.append(DevelopmentProgram.innovation_type.in_(innovation_types))
    if drug_categories:
        program_conditions.append(public_drug_category.in_(drug_categories))
    if program_tags:
        visible_program_tags = public_program_tags(program_tags)
        program_conditions.append(
            or_(
                *(
                    _json_array_value_exists(context, DevelopmentProgram.program_tags, tag)
                    for tag in visible_program_tags
                )
            )
            if visible_program_tags
            else literal(False)
        )
    if global_phase:
        program_conditions.append(DevelopmentProgram.global_phase == global_phase)
    if organization_country_region:
        program_conditions.append(
            select(DevelopmentProgramOrganization.id)
            .where(
                DevelopmentProgramOrganization.tenant_id == context.tenant_id,
                DevelopmentProgramOrganization.program_id == DevelopmentProgram.id,
                DevelopmentProgramOrganization.organization_set_version == DevelopmentProgram.organization_set_version,
                DevelopmentProgramOrganization.country_region == organization_country_region,
                _published_entity_exists(context, DevelopmentProgramOrganization.organization_entity_id),
            )
            .exists()
        )
    return (
        select(DevelopmentProgram.id)
        .join(
            ClinicalTrialEntityRole,
            ClinicalTrialEntityRole.entity_id == DevelopmentProgram.drug_entity_id,
        )
        .where(*program_conditions)
        .exists()
    )


def _clinical_trial_role_entity_exists(context: QueryContext, entity_id: str, role: str | None) -> ColumnElement[bool]:
    conditions: list[ColumnElement[bool]] = [
        ClinicalTrialEntityRole.tenant_id == context.tenant_id,
        ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
        ClinicalTrialEntityRole.entity_id == entity_id,
    ]
    if not context.include_unpublished:
        conditions.append(_published_entity_exists(context, ClinicalTrialEntityRole.entity_id))
    if role:
        conditions.append(ClinicalTrialEntityRole.role == role)
    return select(ClinicalTrialEntityRole.id).where(*conditions).exists()


def _clinical_trial_role_entities_exist(
    context: QueryContext, entity_ids: list[str], role: str | None
) -> ColumnElement[bool]:
    conditions: list[ColumnElement[bool]] = [
        ClinicalTrialEntityRole.tenant_id == context.tenant_id,
        ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
        ClinicalTrialEntityRole.entity_id.in_(entity_ids),
    ]
    if not context.include_unpublished:
        conditions.append(_published_entity_exists(context, ClinicalTrialEntityRole.entity_id))
    if role:
        conditions.append(ClinicalTrialEntityRole.role == role)
    return select(ClinicalTrialEntityRole.id).where(*conditions).exists()


def _clinical_trial_disclosure_exists(
    context: QueryContext,
    *conditions: ColumnElement[bool],
) -> ColumnElement[bool]:
    return (
        select(ClinicalTrialResultDisclosure.id)
        .where(
            ClinicalTrialResultDisclosure.tenant_id == context.tenant_id,
            ClinicalTrialResultDisclosure.trial_id == ClinicalTrialProfile.id,
            *conditions,
        )
        .exists()
    )
