from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.scope import (
    _clean_target_combination_expression,
    _entity_identity_ids,
    _entity_identity_member_ids,
    _placeholder_target_ids,
    _published_entity_exists,
    _published_identity_exists,
)
from pharma_intel.intelligence.vocabulary import _TRIAL_DRUG_ROLES, _meaningful_entity_name_sql
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    DealAssetAssociation,
    DealProfile,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityType,
    Relationship,
)


def _pipeline_trial_exists(
    context: QueryContext,
    drug_entity_id: Any,
    *,
    require_results: bool = False,
    result_evaluation: str | None = None,
) -> ColumnElement[bool]:
    role_drug = Entity.__table__.alias("pipeline_trial_role_drug")
    program_drug = Entity.__table__.alias("pipeline_trial_program_drug")
    statement = (
        select(ClinicalTrialEntityRole.id)
        .join(
            ClinicalTrialProfile,
            and_(
                ClinicalTrialProfile.tenant_id == context.tenant_id,
                ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
            ),
        )
        .join(
            role_drug,
            and_(
                role_drug.c.tenant_id == context.tenant_id,
                role_drug.c.id == ClinicalTrialEntityRole.entity_id,
                role_drug.c.entity_type == EntityType.DRUG,
            ),
        )
        .join(
            program_drug,
            and_(
                program_drug.c.tenant_id == context.tenant_id,
                program_drug.c.id == drug_entity_id,
                program_drug.c.entity_type == EntityType.DRUG,
            ),
        )
        .where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
            role_drug.c.normalized_name == program_drug.c.normalized_name,
        )
    )
    if require_results or result_evaluation:
        statement = statement.where(ClinicalTrialProfile.has_results.is_(True))
    if result_evaluation:
        statement = statement.where(ClinicalTrialProfile.result_evaluation == result_evaluation)
    return statement.exists()


def _pipeline_deal_exists(
    context: QueryContext,
    drug_entity_id: Any,
    *,
    currency: str | None = None,
    total_potential_amount_min: float | None = None,
    total_potential_amount_max: float | None = None,
) -> ColumnElement[bool]:
    deal_filters: list[ColumnElement[bool]] = []
    if currency:
        deal_filters.append(DealProfile.currency == currency)
    if total_potential_amount_min is not None:
        deal_filters.append(DealProfile.total_potential_amount >= total_potential_amount_min)
    if total_potential_amount_max is not None:
        deal_filters.append(DealProfile.total_potential_amount <= total_potential_amount_max)
    normalized = (
        select(DealAssetAssociation.id)
        .join(
            DealProfile,
            and_(
                DealProfile.tenant_id == context.tenant_id,
                DealProfile.id == DealAssetAssociation.deal_id,
            ),
        )
        .where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.asset_entity_id == drug_entity_id,
            *deal_filters,
        )
    )
    relationship = (
        select(Relationship.id)
        .join(
            DealProfile,
            and_(
                DealProfile.tenant_id == context.tenant_id,
                DealProfile.entity_id == Relationship.subject_id,
            ),
        )
        .where(
            Relationship.tenant_id == context.tenant_id,
            Relationship.predicate == "deal_asset",
            Relationship.object_id == drug_entity_id,
            *deal_filters,
        )
    )
    return or_(normalized.exists(), relationship.exists())


def _pipeline_related_signal_exists(
    context: QueryContext,
    drug_entity_id: Any,
    related_entity_id: str,
) -> ColumnElement[bool]:
    linked_trial = (
        select(ClinicalTrialEntityRole.id)
        .join(
            ClinicalTrialProfile,
            and_(
                ClinicalTrialProfile.tenant_id == context.tenant_id,
                ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
            ),
        )
        .where(
            ClinicalTrialEntityRole.tenant_id == context.tenant_id,
            ClinicalTrialEntityRole.entity_id == drug_entity_id,
            ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
            ClinicalTrialProfile.entity_id == related_entity_id,
        )
    )
    linked_deal = (
        select(DealAssetAssociation.id)
        .join(
            DealProfile,
            and_(
                DealProfile.tenant_id == context.tenant_id,
                DealProfile.id == DealAssetAssociation.deal_id,
            ),
        )
        .where(
            DealAssetAssociation.tenant_id == context.tenant_id,
            DealAssetAssociation.asset_entity_id == drug_entity_id,
            DealProfile.entity_id == related_entity_id,
        )
    )
    legacy_deal = select(Relationship.id).where(
        Relationship.tenant_id == context.tenant_id,
        Relationship.predicate == "deal_asset",
        Relationship.subject_id == related_entity_id,
        Relationship.object_id == drug_entity_id,
    )
    return or_(linked_trial.exists(), linked_deal.exists(), legacy_deal.exists())


def _program_target_exists(context: QueryContext, target_entity_id: str) -> ColumnElement[bool]:
    link = DevelopmentProgramTarget.__table__.alias("program_target_filter")
    return (
        select(literal(1))
        .select_from(link)
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == DevelopmentProgram.id,
            link.c.target_set_version == DevelopmentProgram.target_set_version,
            link.c.target_entity_id.in_(_entity_identity_ids(context, target_entity_id, EntityType.TARGET)),
            _published_identity_exists(
                context,
                link.c.target_entity_id,
                EntityType.TARGET,
                correlate_from=link,
            ),
        )
        .correlate(DevelopmentProgram)
        .exists()
    )


def _program_target_combination_matches(context: QueryContext, target_combination_key: str) -> ColumnElement[bool]:
    """Match the current governed target set by canonical identity, not stale raw IDs."""

    requested_ids = tuple(sorted(set(target_combination_key.split("|"))))
    if not requested_ids:
        return literal(False)

    identity_families = [
        _entity_identity_member_ids(context, target_id, EntityType.TARGET) for target_id in requested_ids
    ]
    allowed_target_ids = set().union(*identity_families)
    allowed_target_ids.difference_update(_placeholder_target_ids(context))
    if not allowed_target_ids:
        return literal(False)

    link = DevelopmentProgramTarget.__table__.alias("program_target_combination_filter")
    target = Entity.__table__.alias("program_target_combination_entity")
    current_link = (
        select(literal(1))
        .select_from(link)
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == DevelopmentProgram.id,
            link.c.target_set_version == DevelopmentProgram.target_set_version,
        )
        .correlate(DevelopmentProgram)
        .exists()
    )
    required_identity_matches = [
        select(literal(1))
        .select_from(link.join(target, target.c.id == link.c.target_entity_id))
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == DevelopmentProgram.id,
            link.c.target_set_version == DevelopmentProgram.target_set_version,
            link.c.target_entity_id.in_(identity_family),
            _meaningful_entity_name_sql(target.c.name),
            _published_identity_exists(
                context,
                link.c.target_entity_id,
                EntityType.TARGET,
                correlate_from=link,
            ),
        )
        .correlate(DevelopmentProgram)
        .exists()
        for identity_family in identity_families
    ]
    unexpected_identity = (
        select(literal(1))
        .select_from(link.join(target, target.c.id == link.c.target_entity_id))
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == DevelopmentProgram.id,
            link.c.target_set_version == DevelopmentProgram.target_set_version,
            ~link.c.target_entity_id.in_(allowed_target_ids),
            _meaningful_entity_name_sql(target.c.name),
            _published_identity_exists(
                context,
                link.c.target_entity_id,
                EntityType.TARGET,
                correlate_from=link,
            ),
        )
        .correlate(DevelopmentProgram)
        .exists()
    )
    linked_match = and_(current_link, *required_identity_matches, ~unexpected_identity)
    legacy_raw_match = and_(
        ~current_link,
        _clean_target_combination_expression(context, DevelopmentProgram.target_combination_key)
        == target_combination_key,
    )

    if len(identity_families) != 1:
        return or_(linked_match, legacy_raw_match)
    legacy_match = and_(
        ~current_link,
        DevelopmentProgram.target_entity_id.in_(identity_families[0]),
        _published_identity_exists(
            context,
            DevelopmentProgram.target_entity_id,
            EntityType.TARGET,
            correlate_from=DevelopmentProgram.__table__,
        ),
    )
    return or_(linked_match, legacy_match, legacy_raw_match)


def _unique_program_record(context: QueryContext) -> ColumnElement[bool]:
    """Keep one row for an exact duplicate emitted by one source document.

    Source workbooks can repeat a drug/indication row while the ingestion layer
    is still resolving duplicate entity IDs. Keep records from different source
    documents, or rows with different core development fields, because those can
    represent independent observations. Rows without a source document are not
    deduplicated here and remain visible for governance review.
    """

    ranked_program = DevelopmentProgram.__table__.alias("ranked_program")
    ranked_drug = Entity.__table__.alias("ranked_program_drug")
    ranked_target = Entity.__table__.alias("ranked_program_target")
    ranked_disease = Entity.__table__.alias("ranked_program_disease")
    ranked_organization = Entity.__table__.alias("ranked_program_organization")
    ranked_from = (
        ranked_program.join(ranked_drug, ranked_drug.c.id == ranked_program.c.drug_entity_id)
        .outerjoin(ranked_target, ranked_target.c.id == ranked_program.c.target_entity_id)
        .outerjoin(ranked_disease, ranked_disease.c.id == ranked_program.c.disease_entity_id)
        .outerjoin(ranked_organization, ranked_organization.c.id == ranked_program.c.organization_entity_id)
    )
    duplicate_rank = (
        func.row_number()
        .over(
            partition_by=[
                ranked_program.c.tenant_id,
                ranked_program.c.source_document_id,
                ranked_program.c.target_combination_key,
                ranked_program.c.phase,
                ranked_program.c.program_status,
                ranked_program.c.status_date,
                ranked_program.c.modality,
                ranked_program.c.mechanism_of_action,
                ranked_drug.c.normalized_name,
                ranked_target.c.normalized_name,
                ranked_disease.c.normalized_name,
                ranked_organization.c.normalized_name,
            ],
            order_by=ranked_program.c.id,
        )
        .label("duplicate_rank")
    )
    ranked_records = (
        select(ranked_program.c.id.label("program_id"), duplicate_rank)
        .select_from(ranked_from)
        .where(
            ranked_program.c.tenant_id == context.tenant_id,
            ranked_program.c.source_document_id.is_not(None),
        )
        .subquery("deduplicated_program_records")
    )
    retained_ids = select(ranked_records.c.program_id).where(ranked_records.c.duplicate_rank == 1)
    return or_(DevelopmentProgram.source_document_id.is_(None), DevelopmentProgram.id.in_(retained_ids))


def _program_target_name_exists(context: QueryContext, normalized_query: str) -> ColumnElement[bool]:
    link = DevelopmentProgramTarget.__table__.alias("program_target_name_filter")
    target = Entity.__table__.alias("program_target_name_entity")
    return (
        select(literal(1))
        .select_from(link.join(target, target.c.id == link.c.target_entity_id))
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == DevelopmentProgram.id,
            link.c.target_set_version == DevelopmentProgram.target_set_version,
            _published_entity_exists(context, target.c.id),
            func.lower(target.c.name).contains(normalized_query, autoescape=True),
        )
        .correlate(DevelopmentProgram)
        .exists()
    )


def _program_organization_exists(context: QueryContext, organization_entity_id: str) -> ColumnElement[bool]:
    link = DevelopmentProgramOrganization.__table__.alias("program_organization_filter")
    organization = Entity.__table__.alias("program_organization_visibility_entity")
    return (
        select(literal(1))
        .select_from(link.join(organization, organization.c.id == link.c.organization_entity_id))
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == DevelopmentProgram.id,
            link.c.organization_set_version == DevelopmentProgram.organization_set_version,
            link.c.organization_entity_id == organization_entity_id,
            _published_entity_exists(context, organization.c.id),
        )
        .correlate(DevelopmentProgram)
        .exists()
    )


def _program_organization_name_exists(context: QueryContext, normalized_query: str) -> ColumnElement[bool]:
    link = DevelopmentProgramOrganization.__table__.alias("program_organization_name_filter")
    organization = Entity.__table__.alias("program_organization_name_entity")
    return (
        select(literal(1))
        .select_from(link.join(organization, organization.c.id == link.c.organization_entity_id))
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == DevelopmentProgram.id,
            link.c.organization_set_version == DevelopmentProgram.organization_set_version,
            _published_entity_exists(context, organization.c.id),
            func.lower(organization.c.name).contains(normalized_query, autoescape=True),
        )
        .correlate(DevelopmentProgram)
        .exists()
    )
