from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import func, literal, or_, select
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import _json_array_value_exists, _json_object_array_exists
from pharma_intel.intelligence.pipeline_predicates import (
    _pipeline_deal_exists,
    _pipeline_related_signal_exists,
    _pipeline_trial_exists,
    _program_organization_exists,
    _program_organization_name_exists,
    _program_target_combination_matches,
    _program_target_exists,
    _program_target_name_exists,
    _unique_program_record,
)
from pharma_intel.intelligence.scope import (
    _entity_identity_ids,
    _published_identity_exists,
    _published_optional_identity_entity,
)
from pharma_intel.intelligence.vocabulary import _public_program_drug_category_sql, _public_program_modality_sql
from pharma_intel.models import DevelopmentProgram, DevelopmentProgramOrganization, Entity, EntityType
from pharma_intel.program_semantics import public_program_tags
from pharma_intel.schemas import PipelineSavedSearchQuery


def _program_query(
    context: QueryContext,
    query: str | None,
    modality: list[str] | None,
    phase: str | None,
    geography: str | None,
    *,
    innovation_type: list[str] | None = None,
    therapeutic_area: list[str] | None = None,
    drug_category: list[str] | None = None,
    program_status: str | None = None,
    organization_role: str | None = None,
    organization_type: str | None = None,
    organization_country_region: str | None = None,
    status_date_from: datetime | None = None,
    status_date_to: datetime | None = None,
    drug_entity_id: str | None = None,
    target_entity_id: str | None = None,
    target_combination_key: str | None = None,
    disease_entity_id: str | None = None,
    organization_entity_id: str | None = None,
    global_phase: str | None = None,
    china_phase: str | None = None,
    global_phase_started_from: datetime | None = None,
    global_phase_started_to: datetime | None = None,
    china_phase_started_from: datetime | None = None,
    china_phase_started_to: datetime | None = None,
    development_rights_region: str | None = None,
    commercialization_rights_region: str | None = None,
    program_tag: list[str] | None = None,
    milestone_type: str | None = None,
    milestone_from: datetime | None = None,
    milestone_to: datetime | None = None,
    has_clinical_results: bool | None = None,
    clinical_result_evaluation: str | None = None,
    has_deal: bool | None = None,
    deal_currency: str | None = None,
    deal_total_potential_amount_min: float | None = None,
    deal_total_potential_amount_max: float | None = None,
    related_entity_id: str | None = None,
) -> tuple[Any, Any, Any, Any, Select[Any]]:
    drug = Entity.__table__.alias("pipeline_drug")
    target = Entity.__table__.alias("pipeline_target")
    disease = Entity.__table__.alias("pipeline_disease")
    organization = Entity.__table__.alias("pipeline_organization")
    public_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    public_drug_category = _public_program_drug_category_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    filters: list[ColumnElement[bool]] = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        _unique_program_record(context),
    ]
    if not context.include_unpublished:
        filters.extend(
            [
                _published_identity_exists(
                    context,
                    DevelopmentProgram.drug_entity_id,
                    EntityType.DRUG,
                    correlate_from=DevelopmentProgram.__table__,
                ),
                _published_optional_identity_entity(
                    context,
                    DevelopmentProgram.target_entity_id,
                    EntityType.TARGET,
                    correlate_from=DevelopmentProgram.__table__,
                ),
                _published_optional_identity_entity(
                    context,
                    DevelopmentProgram.disease_entity_id,
                    EntityType.DISEASE,
                    correlate_from=DevelopmentProgram.__table__,
                ),
                _published_optional_identity_entity(
                    context,
                    DevelopmentProgram.organization_entity_id,
                    EntityType.ORGANIZATION,
                    correlate_from=DevelopmentProgram.__table__,
                ),
            ]
        )
    normalized_query = query.strip().casefold() if query else None
    if normalized_query:
        searchable = (
            drug.c.name,
            target.c.name,
            disease.c.name,
            organization.c.name,
            DevelopmentProgram.mechanism_of_action,
        )
        filters.append(
            or_(
                *(func.lower(column).contains(normalized_query, autoescape=True) for column in searchable),
                _program_target_name_exists(context, normalized_query),
                _program_organization_name_exists(context, normalized_query),
            )
        )
    if modality:
        # Same-dimension OR, matching the deal asset multi-select contract.
        filters.append(public_modality.in_(modality))
    if innovation_type:
        filters.append(DevelopmentProgram.innovation_type.in_(innovation_type))
    if therapeutic_area:
        filters.append(DevelopmentProgram.therapeutic_area.in_(therapeutic_area))
    if drug_category:
        filters.append(public_drug_category.in_(drug_category))
    if program_status == "unknown":
        filters.append(
            or_(
                DevelopmentProgram.program_status == "unknown",
                DevelopmentProgram.program_status.is_(None),
            )
        )
    elif program_status:
        filters.append(DevelopmentProgram.program_status == program_status)
    if organization_entity_id or organization_role or organization_type or organization_country_region:
        # Conditions apply to the program's current organization set version only, so
        # superseded historical rows never widen a query. When an entity and role
        # attributes are combined they must describe the same governed relationship.
        org_conditions = [
            DevelopmentProgramOrganization.tenant_id == context.tenant_id,
            DevelopmentProgramOrganization.program_id == DevelopmentProgram.id,
            DevelopmentProgramOrganization.organization_set_version == DevelopmentProgram.organization_set_version,
        ]
        if organization_entity_id:
            org_conditions.append(DevelopmentProgramOrganization.organization_entity_id == organization_entity_id)
        if organization_role:
            org_conditions.append(DevelopmentProgramOrganization.role == organization_role)
        if organization_type:
            org_conditions.append(DevelopmentProgramOrganization.organization_type == organization_type)
        if organization_country_region:
            org_conditions.append(DevelopmentProgramOrganization.country_region == organization_country_region)
        organization_match = select(literal(True)).where(*org_conditions).exists()
        if organization_entity_id and not (organization_role or organization_type or organization_country_region):
            filters.append(
                or_(
                    DevelopmentProgram.organization_entity_id == organization_entity_id,
                    organization_match,
                )
            )
        else:
            filters.append(organization_match)
    if phase:
        filters.append(DevelopmentProgram.phase == phase)
    if geography:
        filters.append(DevelopmentProgram.geography == geography)
    if status_date_from:
        filters.append(DevelopmentProgram.status_date >= status_date_from)
    if status_date_to:
        filters.append(DevelopmentProgram.status_date <= status_date_to)
    if drug_entity_id:
        filters.append(DevelopmentProgram.drug_entity_id == drug_entity_id)
    if target_entity_id:
        filters.append(
            or_(
                DevelopmentProgram.target_entity_id.in_(
                    _entity_identity_ids(context, target_entity_id, EntityType.TARGET)
                ),
                _program_target_exists(context, target_entity_id),
            )
        )
    if target_combination_key:
        filters.append(_program_target_combination_matches(context, target_combination_key))
    if disease_entity_id:
        filters.append(DevelopmentProgram.disease_entity_id == disease_entity_id)
    if global_phase:
        filters.append(DevelopmentProgram.global_phase == global_phase)
    if china_phase:
        filters.append(DevelopmentProgram.china_phase == china_phase)
    if global_phase_started_from:
        filters.append(DevelopmentProgram.global_phase_started_at >= global_phase_started_from)
    if global_phase_started_to:
        filters.append(DevelopmentProgram.global_phase_started_at <= global_phase_started_to)
    if china_phase_started_from:
        filters.append(DevelopmentProgram.china_phase_started_at >= china_phase_started_from)
    if china_phase_started_to:
        filters.append(DevelopmentProgram.china_phase_started_at <= china_phase_started_to)
    if development_rights_region:
        filters.append(
            _json_array_value_exists(
                context,
                DevelopmentProgram.development_rights_regions,
                development_rights_region,
            )
        )
    if commercialization_rights_region:
        filters.append(
            _json_array_value_exists(
                context,
                DevelopmentProgram.commercialization_rights_regions,
                commercialization_rights_region,
            )
        )
    if program_tag:
        # Same-dimension OR: a program matches when any selected tag is present.
        visible_program_tags = public_program_tags(program_tag)
        filters.append(
            or_(
                *(
                    _json_array_value_exists(context, DevelopmentProgram.program_tags, tag)
                    for tag in visible_program_tags
                )
            )
            if visible_program_tags
            else literal(False)
        )
    if milestone_type or milestone_from or milestone_to:
        filters.append(
            _json_object_array_exists(
                context,
                DevelopmentProgram.milestones,
                text_field="milestone_type",
                text_value=milestone_type,
                datetime_field="occurred_at",
                datetime_from=milestone_from,
                datetime_to=milestone_to,
            )
        )
    clinical_result_match = _pipeline_trial_exists(
        context,
        DevelopmentProgram.drug_entity_id,
        require_results=True,
        result_evaluation=clinical_result_evaluation,
    )
    if has_clinical_results is True or clinical_result_evaluation:
        filters.append(clinical_result_match)
    elif has_clinical_results is False:
        filters.append(~clinical_result_match)
    deal_match = _pipeline_deal_exists(
        context,
        DevelopmentProgram.drug_entity_id,
        currency=deal_currency,
        total_potential_amount_min=deal_total_potential_amount_min,
        total_potential_amount_max=deal_total_potential_amount_max,
    )
    if has_deal is True or any(
        value is not None for value in (deal_currency, deal_total_potential_amount_min, deal_total_potential_amount_max)
    ):
        filters.append(deal_match)
    elif has_deal is False:
        filters.append(~deal_match)
    if related_entity_id:
        filters.append(
            or_(
                DevelopmentProgram.drug_entity_id == related_entity_id,
                DevelopmentProgram.target_entity_id == related_entity_id,
                _program_target_exists(context, related_entity_id),
                DevelopmentProgram.disease_entity_id == related_entity_id,
                DevelopmentProgram.organization_entity_id == related_entity_id,
                _program_organization_exists(context, related_entity_id),
                _pipeline_related_signal_exists(
                    context,
                    DevelopmentProgram.drug_entity_id,
                    related_entity_id,
                ),
            )
        )
    joined = (
        select(
            DevelopmentProgram,
            drug.c.name.label("drug_name"),
            target.c.name.label("target_name"),
            disease.c.name.label("disease_name"),
            organization.c.name.label("organization_name"),
        )
        .join(drug, drug.c.id == DevelopmentProgram.drug_entity_id)
        .outerjoin(target, target.c.id == DevelopmentProgram.target_entity_id)
        .outerjoin(disease, disease.c.id == DevelopmentProgram.disease_entity_id)
        .outerjoin(organization, organization.c.id == DevelopmentProgram.organization_entity_id)
        .where(*filters)
    )
    return drug, target, disease, organization, joined


def program_saved_search_matches_entity(context: QueryContext, entity_id: str, query: PipelineSavedSearchQuery) -> bool:
    def start(value: Any) -> datetime | None:
        return datetime.combine(value, time.min, tzinfo=UTC) if value else None

    def end(value: Any) -> datetime | None:
        return datetime.combine(value, time.max, tzinfo=UTC) if value else None

    *_, joined = _program_query(
        context,
        query.q,
        query.modality,
        query.phase.value if query.phase else None,
        query.geography,
        innovation_type=query.innovation_type,
        therapeutic_area=query.therapeutic_area,
        drug_category=query.drug_category,
        program_status=query.program_status,
        organization_role=query.organization_role,
        organization_type=query.organization_type,
        organization_country_region=query.organization_country_region,
        status_date_from=start(query.status_date_from),
        status_date_to=end(query.status_date_to),
        drug_entity_id=query.drug_entity_id,
        target_entity_id=query.target_entity_id,
        target_combination_key=query.target_combination_key,
        disease_entity_id=query.disease_entity_id,
        organization_entity_id=query.organization_entity_id,
        global_phase=query.global_phase.value if query.global_phase else None,
        china_phase=query.china_phase.value if query.china_phase else None,
        global_phase_started_from=start(query.global_phase_started_from),
        global_phase_started_to=end(query.global_phase_started_to),
        china_phase_started_from=start(query.china_phase_started_from),
        china_phase_started_to=end(query.china_phase_started_to),
        development_rights_region=query.development_rights_region,
        commercialization_rights_region=query.commercialization_rights_region,
        program_tag=query.program_tag,
        milestone_type=query.milestone_type,
        milestone_from=start(query.milestone_from),
        milestone_to=end(query.milestone_to),
        has_clinical_results=query.has_clinical_results,
        clinical_result_evaluation=(
            query.clinical_result_evaluation.value if query.clinical_result_evaluation else None
        ),
        has_deal=query.has_deal,
        deal_currency=query.deal_currency,
        deal_total_potential_amount_min=query.deal_total_potential_amount_min,
        deal_total_potential_amount_max=query.deal_total_potential_amount_max,
        related_entity_id=entity_id,
    )
    return context.session.scalar(joined.with_only_columns(literal(True)).limit(1)) is True


def _program_filters(context: QueryContext, entity_id: str) -> list[ColumnElement[bool]]:
    filters = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        _unique_program_record(context),
        or_(
            DevelopmentProgram.drug_entity_id.in_(_entity_identity_ids(context, entity_id, EntityType.DRUG)),
            DevelopmentProgram.target_entity_id.in_(_entity_identity_ids(context, entity_id, EntityType.TARGET)),
            _program_target_exists(context, entity_id),
            DevelopmentProgram.disease_entity_id.in_(_entity_identity_ids(context, entity_id, EntityType.DISEASE)),
            DevelopmentProgram.organization_entity_id.in_(
                _entity_identity_ids(context, entity_id, EntityType.ORGANIZATION)
            ),
            _program_organization_exists(context, entity_id),
        ),
    ]
    if not context.include_unpublished:
        filters.extend(
            [
                _published_identity_exists(
                    context,
                    DevelopmentProgram.drug_entity_id,
                    EntityType.DRUG,
                    correlate_from=DevelopmentProgram.__table__,
                ),
                _published_optional_identity_entity(
                    context,
                    DevelopmentProgram.target_entity_id,
                    EntityType.TARGET,
                    correlate_from=DevelopmentProgram.__table__,
                ),
                _published_optional_identity_entity(
                    context,
                    DevelopmentProgram.disease_entity_id,
                    EntityType.DISEASE,
                    correlate_from=DevelopmentProgram.__table__,
                ),
                _published_optional_identity_entity(
                    context,
                    DevelopmentProgram.organization_entity_id,
                    EntityType.ORGANIZATION,
                    correlate_from=DevelopmentProgram.__table__,
                ),
            ]
        )
    return filters
