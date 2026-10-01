from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.facets import _applied_filters, _json_array_facets, _json_object_array_facets
from pharma_intel.intelligence.pipeline_entities import (
    _program_organization_map,
    _program_target_map,
    _visible_program_organization_map,
    _visible_program_target_map,
)
from pharma_intel.intelligence.pipeline_filters import _program_query
from pharma_intel.intelligence.pipeline_landscape import _pipeline_landscape
from pharma_intel.intelligence.pipeline_organizations import _pipeline_organization_facets
from pharma_intel.intelligence.pipeline_signals import _pipeline_signal_facets, _pipeline_signal_maps
from pharma_intel.intelligence.scope import _canonical_target_combination_keys, _published_entity_identity_labels
from pharma_intel.intelligence.vocabulary import (
    _DEVELOPMENT_PHASE_RANK,
    _ordered_sort_expressions,
    _public_program_drug_category_sql,
    _public_program_modality_sql,
    _sort_criteria_read,
)
from pharma_intel.models import (
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityCanonicalLink,
    EntityIdentifier,
    EntityType,
    ReviewStatus,
)
from pharma_intel.program_semantics import public_program_drug_category, public_program_modality, public_program_tags
from pharma_intel.schemas import (
    PIPELINE_SORT_FIELDS,
    CompetitiveProgramRead,
    PipelineLandscapeStageScope,
    PipelineResultGrain,
    PipelineSearchResult,
    PipelineSortField,
    PipelineTargetAggregation,
    ProgramIndicationRead,
    SortDirection,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses


def _pipeline_drug_identity_expressions(
    context: QueryContext, drug: Any
) -> tuple[ColumnElement[Any], ColumnElement[Any]]:
    """Resolve the display identity without changing raw program relationships.

    Imported source rows can contain several draft entities for one drug name. The
    public-facing drug grain should use an approved canonical link or the stable
    verified representative already used by target landscape aggregation, while
    signal joins continue to use the raw ``DevelopmentProgram.drug_entity_id``.
    """

    canonical_link = EntityCanonicalLink.__table__.alias("pipeline_drug_canonical_link")
    canonical_drug = Entity.__table__.alias("pipeline_canonical_drug")
    verified_drug = Entity.__table__.alias("pipeline_verified_drug")
    canonical_drug_id = (
        select(canonical_link.c.canonical_entity_id)
        .where(
            canonical_link.c.tenant_id == context.tenant_id,
            canonical_link.c.alias_entity_id == drug.c.id,
            canonical_link.c.active.is_(True),
        )
        .correlate(drug)
        .limit(1)
        .scalar_subquery()
    )
    verified_trusted_identifier_count = (
        select(func.count(EntityIdentifier.id))
        .where(
            EntityIdentifier.tenant_id == context.tenant_id,
            EntityIdentifier.entity_id == verified_drug.c.id,
            EntityIdentifier.entity_type == EntityType.DRUG,
            EntityIdentifier.trusted_namespace.is_(True),
            EntityIdentifier.review_status == ReviewStatus.VERIFIED,
        )
        .correlate(verified_drug)
        .scalar_subquery()
    )
    verified_drug_id = (
        select(verified_drug.c.id)
        .where(
            verified_drug.c.tenant_id == context.tenant_id,
            verified_drug.c.entity_type == EntityType.DRUG,
            verified_drug.c.normalized_name == drug.c.normalized_name,
            verified_drug.c.review_status == ReviewStatus.VERIFIED,
        )
        .order_by(verified_trusted_identifier_count.desc(), verified_drug.c.id)
        .correlate(drug)
        .limit(1)
        .scalar_subquery()
    )
    canonical_drug_name = (
        select(canonical_drug.c.name)
        .select_from(canonical_link.join(canonical_drug, canonical_drug.c.id == canonical_link.c.canonical_entity_id))
        .where(
            canonical_link.c.tenant_id == context.tenant_id,
            canonical_link.c.alias_entity_id == drug.c.id,
            canonical_link.c.active.is_(True),
        )
        .correlate(drug)
        .limit(1)
        .scalar_subquery()
    )
    verified_drug_name = (
        select(verified_drug.c.name)
        .where(
            verified_drug.c.tenant_id == context.tenant_id,
            verified_drug.c.entity_type == EntityType.DRUG,
            verified_drug.c.normalized_name == drug.c.normalized_name,
            verified_drug.c.review_status == ReviewStatus.VERIFIED,
        )
        .order_by(verified_trusted_identifier_count.desc(), verified_drug.c.id)
        .correlate(drug)
        .limit(1)
        .scalar_subquery()
    )
    return (
        func.coalesce(canonical_drug_id, verified_drug_id, drug.c.id),
        func.coalesce(canonical_drug_name, verified_drug_name, drug.c.name),
    )


def search_programs(
    context: QueryContext,
    query: str | None,
    modality: list[str] | None,
    phase: str | None,
    geography: str | None,
    limit: int,
    offset: int,
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
    sort_by: PipelineSortField = "status_date",
    sort_direction: SortDirection = "desc",
    sort: Sequence[SortClause[PipelineSortField]] | None = None,
    landscape_limit: int = 20,
    landscape_stage_scope: PipelineLandscapeStageScope = "overall",
    landscape_target_aggregation: PipelineTargetAggregation = "all",
    result_grain: PipelineResultGrain = "program",
) -> PipelineSearchResult:
    drug, target, disease, organization, joined = _program_query(
        context,
        query,
        modality,
        phase,
        geography,
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
        target_combination_key=target_combination_key,
        disease_entity_id=disease_entity_id,
        organization_entity_id=organization_entity_id,
        global_phase=global_phase,
        china_phase=china_phase,
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
        clinical_result_evaluation=clinical_result_evaluation,
        has_deal=has_deal,
        deal_currency=deal_currency,
        deal_total_potential_amount_min=deal_total_potential_amount_min,
        deal_total_potential_amount_max=deal_total_potential_amount_max,
    )
    # Keep raw program relationships for signal joins, but expose one stable
    # verified drug identity in every result grain so counts and row labels agree.
    drug_identity_id, drug_identity_name = _pipeline_drug_identity_expressions(context, drug)
    result_joined = joined.add_columns(
        drug_identity_id.label("drug_identity_id"),
        drug_identity_name.label("drug_identity_name"),
    )
    phase_rank = {
        "phase": case(
            *[
                (DevelopmentProgram.phase == DevelopmentPhase(phase), rank)
                for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
            ],
            else_=-2,
        ),
        "global_phase": case(
            *[
                (DevelopmentProgram.global_phase == DevelopmentPhase(phase), rank)
                for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
            ],
            else_=-2,
        ),
        "china_phase": case(
            *[
                (DevelopmentProgram.china_phase == DevelopmentPhase(phase), rank)
                for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
            ],
            else_=-2,
        ),
    }
    effective_sort = validate_sort_clauses(
        sort,
        PIPELINE_SORT_FIELDS,
        default_field=sort_by,
        default_direction=sort_direction,
    )
    public_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    public_drug_category = _public_program_drug_category_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    sort_expressions: dict[PipelineSortField, Any] = {
        "status_date": DevelopmentProgram.status_date,
        "drug_name": func.lower(drug_identity_name),
        "target_name": func.lower(target.c.name),
        "disease_name": func.lower(disease.c.name),
        "organization_name": func.lower(organization.c.name),
        "modality": func.lower(public_modality),
        "mechanism_of_action": func.lower(DevelopmentProgram.mechanism_of_action),
        "phase": phase_rank["phase"],
        "status_detail": func.lower(DevelopmentProgram.status_detail),
        "geography": func.lower(DevelopmentProgram.geography),
        "global_phase": phase_rank["global_phase"],
        "china_phase": phase_rank["china_phase"],
        "global_phase_started_at": DevelopmentProgram.global_phase_started_at,
        "china_phase_started_at": DevelopmentProgram.china_phase_started_at,
    }
    ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
    facet_source = (
        result_joined.with_only_columns(
            DevelopmentProgram.id.label("program_id"),
            DevelopmentProgram.drug_entity_id.label("drug_entity_id"),
            drug_identity_id.label("drug_identity_id"),
            drug_identity_name.label("drug_name"),
            DevelopmentProgram.target_entity_id.label("target_entity_id"),
            target.c.name.label("target_name"),
            DevelopmentProgram.target_set_version.label("target_set_version"),
            DevelopmentProgram.organization_set_version.label("organization_set_version"),
            DevelopmentProgram.target_combination_key.label("target_combination_key"),
            DevelopmentProgram.disease_entity_id.label("disease_entity_id"),
            disease.c.name.label("disease_name"),
            DevelopmentProgram.organization_entity_id.label("organization_entity_id"),
            organization.c.name.label("organization_name"),
            public_modality.label("modality"),
            DevelopmentProgram.mechanism_of_action.label("mechanism_of_action"),
            DevelopmentProgram.innovation_type.label("innovation_type"),
            DevelopmentProgram.therapeutic_area.label("therapeutic_area"),
            public_drug_category.label("drug_category"),
            DevelopmentProgram.program_status.label("program_status"),
            DevelopmentProgram.phase.label("phase"),
            DevelopmentProgram.status_detail.label("status_detail"),
            DevelopmentProgram.status_date.label("status_date"),
            DevelopmentProgram.geography.label("geography"),
            DevelopmentProgram.global_phase.label("global_phase"),
            DevelopmentProgram.china_phase.label("china_phase"),
            DevelopmentProgram.global_phase_started_at.label("global_phase_started_at"),
            DevelopmentProgram.china_phase_started_at.label("china_phase_started_at"),
            DevelopmentProgram.development_rights_regions.label("development_rights_regions"),
            DevelopmentProgram.commercialization_rights_regions.label("commercialization_rights_regions"),
            DevelopmentProgram.program_tags.label("program_tags"),
            DevelopmentProgram.milestones.label("milestones"),
        )
        .order_by(None)
        .subquery()
    )
    project_total = context.session.scalar(select(func.count()).select_from(facet_source)) or 0
    total = project_total

    if result_grain == "drug":
        grouped_phase_rank = {
            name: func.max(
                case(
                    *[
                        (facet_source.c[name] == DevelopmentPhase(phase), rank)
                        for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
                    ],
                    else_=-2,
                )
            ).label(name)
            for name in ("phase", "global_phase", "china_phase")
        }
        drug_page_source = (
            select(
                facet_source.c.drug_identity_id.label("drug_entity_id"),
                func.min(facet_source.c.drug_name).label("drug_name"),
                func.min(facet_source.c.target_name).label("target_name"),
                func.min(facet_source.c.disease_name).label("disease_name"),
                func.min(facet_source.c.organization_name).label("organization_name"),
                func.min(facet_source.c.modality).label("modality"),
                func.min(facet_source.c.mechanism_of_action).label("mechanism_of_action"),
                grouped_phase_rank["phase"],
                func.min(facet_source.c.status_detail).label("status_detail"),
                func.max(facet_source.c.status_date).label("status_date"),
                func.min(facet_source.c.geography).label("geography"),
                grouped_phase_rank["global_phase"],
                grouped_phase_rank["china_phase"],
                func.min(facet_source.c.global_phase_started_at).label("global_phase_started_at"),
                func.min(facet_source.c.china_phase_started_at).label("china_phase_started_at"),
            )
            .group_by(facet_source.c.drug_identity_id)
            .subquery()
        )
        drug_sort_expressions = {field: drug_page_source.c[field] for field in PIPELINE_SORT_FIELDS}
        ordered_drug_sort = _ordered_sort_expressions(effective_sort, drug_sort_expressions)
        ordered_drug_ids = list(
            context.session.scalars(
                select(drug_page_source.c.drug_entity_id)
                .order_by(*ordered_drug_sort, drug_page_source.c.drug_entity_id)
                .limit(limit)
                .offset(offset)
            )
        )
        total = context.session.scalar(select(func.count()).select_from(drug_page_source)) or 0
        if ordered_drug_ids:
            selected_raw_drug_ids = list(
                context.session.scalars(
                    select(facet_source.c.drug_entity_id)
                    .where(facet_source.c.drug_identity_id.in_(ordered_drug_ids))
                    .distinct()
                )
            )
            rows = context.session.execute(
                result_joined.where(DevelopmentProgram.drug_entity_id.in_(selected_raw_drug_ids)).order_by(
                    DevelopmentProgram.drug_entity_id,
                    DevelopmentProgram.id,
                )
            ).all()
        else:
            rows = []
    else:
        ordered_drug_ids = []
        rows = context.session.execute(
            result_joined.order_by(*ordered_sort, DevelopmentProgram.id).limit(limit).offset(offset)
        ).all()

    facets: dict[str, dict[str, int]] = {}
    facet_id_name = "drug_identity_id" if result_grain == "drug" else "program_id"
    for name in (
        "modality",
        "innovation_type",
        "therapeutic_area",
        "drug_category",
        "program_status",
        "phase",
        "geography",
        "global_phase",
        "china_phase",
    ):
        count_expression = (
            func.count(func.distinct(facet_source.c.drug_identity_id)) if result_grain == "drug" else func.count()
        )
        if name == "program_status":
            # A missing governed status is a visible "unknown" bucket. The
            # row aggregation already exposes it this way; facets and filters
            # must use the same contract instead of silently dropping NULLs.
            column: ColumnElement[Any] = case(
                (facet_source.c.program_status == "active", "active"),
                (facet_source.c.program_status == "inactive", "inactive"),
                else_="unknown",
            ).label("program_status")
            counts = context.session.execute(
                select(column, count_expression)
                .select_from(facet_source)
                .group_by(column)
                .order_by(count_expression.desc(), column)
            ).all()
        else:
            column = facet_source.c[name]
            counts = context.session.execute(
                select(column, count_expression)
                .select_from(facet_source)
                .where(column.is_not(None))
                .group_by(column)
                .order_by(count_expression.desc(), column)
            ).all()
        facets[name] = {
            value.value if hasattr(value, "value") else str(value): count for value, count in counts if value
        }
    for name in (
        "development_rights_regions",
        "commercialization_rights_regions",
        "program_tags",
    ):
        facets[
            {
                "development_rights_regions": "development_rights_region",
                "commercialization_rights_regions": "commercialization_rights_region",
                "program_tags": "program_tag",
            }[name]
        ] = _json_array_facets(
            context,
            facet_source,
            name,
            facet_id_name,
            public_program_tags_only=name == "program_tags",
        )
    facets["milestone_type"] = _json_object_array_facets(
        context,
        facet_source,
        "milestones",
        "milestone_type",
        facet_id_name,
    )
    facets.update(_pipeline_organization_facets(context, facet_source, facet_id_name))
    facets.update(_pipeline_signal_facets(context, facet_source, facet_id_name))
    landscape = _pipeline_landscape(
        context,
        facet_source,
        project_total,
        limit=landscape_limit,
        stage_scope=landscape_stage_scope,
        target_aggregation=landscape_target_aggregation,
    )
    row_values = [(row[0], row[1], row[2], row[3], row[4], row[5], row[6]) for row in rows]
    target_map = _program_target_map(
        context,
        [row[0] for row in row_values],
        {row[0].id: (row[0].target_entity_id, row[2]) for row in row_values},
    )
    target_map = _visible_program_target_map(context, target_map)
    primary_targets = {program_id: targets[0] for program_id, targets in target_map.items() if targets}
    target_combination_keys = _canonical_target_combination_keys(context, target_map)
    organization_map = _program_organization_map(
        context,
        [row[0] for row in row_values],
        {row[0].id: (row[0].organization_entity_id, row[4]) for row in row_values},
    )
    organization_map = _visible_program_organization_map(context, organization_map)
    primary_organizations = {
        program_id: organizations[0] for program_id, organizations in organization_map.items() if organizations
    }
    disease_identities = (
        {}
        if context.include_unpublished
        else _published_entity_identity_labels(
            context,
            {str(row[0].disease_entity_id) for row in row_values if row[0].disease_entity_id},
            EntityType.DISEASE,
        )
    )
    trial_counts, drugs_with_results, result_evaluations, deal_counts, deal_currencies = _pipeline_signal_maps(
        context, [row[0].drug_entity_id for row in row_values]
    )

    items = [
        CompetitiveProgramRead(
            id=program.id,
            drug_entity_id=identity_id,
            drug_name=identity_name,
            target_entity_id=(primary_targets[program.id].entity_id if program.id in primary_targets else None),
            target_name=primary_targets[program.id].name if program.id in primary_targets else target_name,
            targets=target_map.get(program.id, []),
            target_combination_key=target_combination_keys.get(program.id),
            disease_entity_id=(
                program.disease_entity_id
                if context.include_unpublished
                else disease_identities.get(str(program.disease_entity_id), (None, disease_name))[0]
            ),
            disease_name=(
                disease_name
                if context.include_unpublished
                else disease_identities.get(str(program.disease_entity_id), (None, disease_name))[1]
            ),
            organization_entity_id=(
                primary_organizations[program.id].entity_id
                if program.id in primary_organizations
                else program.organization_entity_id
                if context.include_unpublished
                else None
            ),
            organization_name=(
                primary_organizations[program.id].name if program.id in primary_organizations else organization_name
            ),
            organizations=organization_map.get(program.id, []),
            modality=public_program_modality(program.modality, program.drug_category),
            innovation_type=program.innovation_type,
            therapeutic_area=program.therapeutic_area,
            drug_category=public_program_drug_category(program.modality, program.drug_category),
            mechanism_of_action=program.mechanism_of_action,
            phase=program.phase.value,
            status_detail=program.status_detail,
            program_status=program.program_status,
            status_date=program.status_date,
            geography=program.geography,
            global_phase=program.global_phase,
            china_phase=program.china_phase,
            global_phase_started_at=program.global_phase_started_at,
            china_phase_started_at=program.china_phase_started_at,
            development_rights_regions=program.development_rights_regions or [],
            commercialization_rights_regions=program.commercialization_rights_regions or [],
            program_tags=public_program_tags(program.program_tags),
            status_history=program.status_history or [],
            milestones=program.milestones or [],
            clinical_trial_count=trial_counts.get(program.drug_entity_id, 0),
            has_clinical_results=program.drug_entity_id in drugs_with_results,
            clinical_result_evaluations=result_evaluations.get(program.drug_entity_id, []),
            deal_count=deal_counts.get(program.drug_entity_id, 0),
            deal_currencies=deal_currencies.get(program.drug_entity_id, []),
            source_document_id=program.source_document_id,
        )
        for (
            program,
            raw_drug_name,
            target_name,
            disease_name,
            organization_name,
            identity_id,
            identity_name,
        ) in row_values
    ]
    if result_grain == "drug":
        programs_by_drug: dict[str, list[CompetitiveProgramRead]] = defaultdict(list)
        for item in items:
            programs_by_drug[item.drug_entity_id].append(item)

        def highest_phase(programs: Sequence[CompetitiveProgramRead], field: str) -> str | None:
            values = [getattr(program, field) for program in programs if getattr(program, field)]
            return max(values, key=lambda value: _DEVELOPMENT_PHASE_RANK.get(str(value), -2), default=None)

        def phase_started_at(
            programs: Sequence[CompetitiveProgramRead],
            phase_field: str,
            date_field: str,
            highest: str | None,
        ) -> datetime | None:
            values = [
                getattr(program, date_field)
                for program in programs
                if getattr(program, phase_field) == highest and getattr(program, date_field) is not None
            ]
            return min(values, default=None)

        aggregated_items: list[CompetitiveProgramRead] = []
        for drug_id in ordered_drug_ids:
            programs = programs_by_drug.get(drug_id, [])
            if not programs:
                continue
            representative = max(
                programs,
                key=lambda item: (
                    _DEVELOPMENT_PHASE_RANK.get(item.phase, -2),
                    item.status_date or datetime.min.replace(tzinfo=UTC),
                    item.id,
                ),
            )
            highest_overall = highest_phase(programs, "phase") or representative.phase
            highest_global = highest_phase(programs, "global_phase")
            highest_china = highest_phase(programs, "china_phase")
            targets = list({target.entity_id: target for item in programs for target in item.targets}.values())
            organizations = list(
                {
                    organization.entity_id: organization for item in programs for organization in item.organizations
                }.values()
            )
            status_counts = Counter(item.program_status or "unknown" for item in programs)
            aggregate_status = (
                "active" if status_counts["active"] else "unknown" if status_counts["unknown"] else "inactive"
            )
            aggregated_items.append(
                representative.model_copy(
                    update={
                        "targets": targets,
                        "target_combination_key": "|".join(sorted(target.entity_id for target in targets)) or None,
                        "disease_entity_id": None,
                        "disease_name": None,
                        "organizations": organizations,
                        "modality": None,
                        "mechanism_of_action": None,
                        "phase": highest_overall,
                        "global_phase": highest_global,
                        "china_phase": highest_china,
                        "global_phase_started_at": phase_started_at(
                            programs, "global_phase", "global_phase_started_at", highest_global
                        ),
                        "china_phase_started_at": phase_started_at(
                            programs, "china_phase", "china_phase_started_at", highest_china
                        ),
                        "program_status": aggregate_status,
                        "status_date": max(
                            (item.status_date for item in programs if item.status_date is not None),
                            default=None,
                        ),
                        "project_count": len(programs),
                        "indications": [
                            ProgramIndicationRead(
                                program_id=item.id,
                                disease_entity_id=item.disease_entity_id,
                                disease_name=item.disease_name,
                                phase=item.phase,
                                global_phase=item.global_phase,
                                china_phase=item.china_phase,
                                global_phase_started_at=item.global_phase_started_at,
                                china_phase_started_at=item.china_phase_started_at,
                                program_status=item.program_status,
                                status_date=item.status_date,
                                geography=item.geography,
                            )
                            for item in sorted(
                                programs,
                                key=lambda item: (
                                    -_DEVELOPMENT_PHASE_RANK.get(item.phase, -2),
                                    item.disease_name or "",
                                    item.id,
                                ),
                            )
                        ],
                        "modalities": sorted({item.modality for item in programs if item.modality}),
                        "mechanisms_of_action": sorted(
                            {item.mechanism_of_action for item in programs if item.mechanism_of_action}
                        ),
                        "innovation_types": sorted({item.innovation_type for item in programs if item.innovation_type}),
                        "therapeutic_areas": sorted(
                            {item.therapeutic_area for item in programs if item.therapeutic_area}
                        ),
                        "drug_categories": sorted({item.drug_category for item in programs if item.drug_category}),
                        "program_status_counts": dict(status_counts),
                        "clinical_trial_count": max(item.clinical_trial_count for item in programs),
                        "has_clinical_results": any(item.has_clinical_results for item in programs),
                        "clinical_result_evaluations": sorted(
                            {value for item in programs for value in item.clinical_result_evaluations}
                        ),
                        "deal_count": max(item.deal_count for item in programs),
                        "deal_currencies": sorted({value for item in programs for value in item.deal_currencies}),
                    }
                )
            )
        items = aggregated_items
    return PipelineSearchResult(
        query_schema_version="pharma.pipeline.search.v13",
        applied_filters=_applied_filters(
            ("q", "contains", query.strip() if query else None),
            ("modality", "in", modality),
            ("innovation_type", "in", innovation_type),
            ("therapeutic_area", "in", therapeutic_area),
            ("drug_category", "in", drug_category),
            ("program_status", "eq", program_status),
            ("organization_role", "eq", organization_role),
            ("organization_type", "eq", organization_type),
            ("organization_country_region", "eq", organization_country_region),
            ("phase", "eq", phase),
            ("geography", "eq", geography),
            ("status_date_from", "gte", status_date_from.isoformat() if status_date_from else None),
            ("status_date_to", "lte", status_date_to.isoformat() if status_date_to else None),
            ("drug_entity_id", "eq", drug_entity_id),
            ("target_entity_id", "eq", target_entity_id),
            ("target_combination_key", "eq", target_combination_key),
            ("disease_entity_id", "eq", disease_entity_id),
            ("organization_entity_id", "eq", organization_entity_id),
            ("global_phase", "eq", global_phase),
            ("china_phase", "eq", china_phase),
            (
                "global_phase_started_from",
                "gte",
                global_phase_started_from.isoformat() if global_phase_started_from else None,
            ),
            (
                "global_phase_started_to",
                "lte",
                global_phase_started_to.isoformat() if global_phase_started_to else None,
            ),
            (
                "china_phase_started_from",
                "gte",
                china_phase_started_from.isoformat() if china_phase_started_from else None,
            ),
            (
                "china_phase_started_to",
                "lte",
                china_phase_started_to.isoformat() if china_phase_started_to else None,
            ),
            ("development_rights_region", "eq", development_rights_region),
            ("commercialization_rights_region", "eq", commercialization_rights_region),
            ("program_tag", "in", public_program_tags(program_tag)),
            ("milestone_type", "eq", milestone_type),
            ("milestone_from", "gte", milestone_from.isoformat() if milestone_from else None),
            ("milestone_to", "lte", milestone_to.isoformat() if milestone_to else None),
            ("has_clinical_results", "eq", has_clinical_results),
            ("clinical_result_evaluation", "eq", clinical_result_evaluation),
            ("has_deal", "eq", has_deal),
            ("deal_currency", "eq", deal_currency),
            (
                "deal_total_potential_amount_min",
                "gte",
                deal_total_potential_amount_min,
            ),
            (
                "deal_total_potential_amount_max",
                "lte",
                deal_total_potential_amount_max,
            ),
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
        result_grain=result_grain,
        project_total=project_total,
        as_of=datetime.now(UTC),
        warnings=["暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。"],
    )
