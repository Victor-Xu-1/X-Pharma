from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.pipeline_entities import (
    _program_organization_map,
    _program_target_map,
    _visible_program_organization_map,
    _visible_program_target_map,
)
from pharma_intel.intelligence.pipeline_filters import _program_filters
from pharma_intel.intelligence.pipeline_signals import _pipeline_signal_maps
from pharma_intel.intelligence.scope import (
    _canonical_target_combination_keys,
    _count,
    _published_entity_identity_labels,
)
from pharma_intel.models import DevelopmentProgram, Entity, EntityType
from pharma_intel.program_semantics import public_program_drug_category, public_program_modality, public_program_tags
from pharma_intel.schemas import CompetitiveProgramRead, DrugProgramSearchResult


def drug_programs(context: QueryContext, entity_id: str, limit: int, offset: int = 0) -> DrugProgramSearchResult | None:
    """Return the complete drug portfolio through a bounded page."""

    entity = context.session.scalar(
        select(Entity).where(
            Entity.tenant_id == context.tenant_id,
            Entity.id == entity_id,
            Entity.entity_type == EntityType.DRUG,
        )
    )
    if entity is None:
        return None

    filters = _program_filters(context, entity_id)
    return DrugProgramSearchResult(
        query_schema_version="pharma.drug.programs.v1",
        items=_read_programs(context, filters, limit, offset),
        total=_count(context, DevelopmentProgram, filters),
        limit=limit,
        offset=offset,
        as_of=datetime.now(UTC),
    )


def competitive_programs(
    context: QueryContext, target_entity_id: str, limit: int, offset: int = 0
) -> list[CompetitiveProgramRead]:
    return _read_programs(context, _program_filters(context, target_entity_id), limit, offset)


def programs_for_entity(
    context: QueryContext, entity_id: str, limit: int, offset: int = 0
) -> list[CompetitiveProgramRead]:
    return _read_programs(context, _program_filters(context, entity_id), limit, offset)


def _read_programs(
    context: QueryContext, filters: list[ColumnElement[bool]], limit: int, offset: int
) -> list[CompetitiveProgramRead]:
    drug = Entity.__table__.alias("drug")
    target = Entity.__table__.alias("target")
    disease = Entity.__table__.alias("disease")
    organization = Entity.__table__.alias("organization")
    rows = context.session.execute(
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
        .order_by(
            DevelopmentProgram.status_date.desc().nullslast(),
            DevelopmentProgram.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    target_map = _program_target_map(
        context,
        [program for program, *_ in rows],
        {program.id: (program.target_entity_id, target_name) for program, _, target_name, _, _ in rows},
    )
    target_map = _visible_program_target_map(context, target_map)
    primary_targets = {program_id: targets[0] for program_id, targets in target_map.items() if targets}
    target_combination_keys = _canonical_target_combination_keys(context, target_map)
    organization_map = _program_organization_map(
        context,
        [program for program, *_ in rows],
        {
            program.id: (program.organization_entity_id, organization_name)
            for program, _, _, _, organization_name in rows
        },
    )
    organization_map = _visible_program_organization_map(context, organization_map)
    primary_organizations = {
        program_id: organizations[0] for program_id, organizations in organization_map.items() if organizations
    }
    drug_identities = (
        {}
        if context.include_unpublished
        else _published_entity_identity_labels(
            context,
            {str(program.drug_entity_id) for program, *_ in rows},
            EntityType.DRUG,
        )
    )
    disease_identities = (
        {}
        if context.include_unpublished
        else _published_entity_identity_labels(
            context,
            {str(program.disease_entity_id) for program, *_ in rows if program.disease_entity_id},
            EntityType.DISEASE,
        )
    )
    trial_counts, drugs_with_results, result_evaluations, deal_counts, deal_currencies = _pipeline_signal_maps(
        context, [program.drug_entity_id for program, *_ in rows]
    )
    return [
        CompetitiveProgramRead(
            id=program.id,
            drug_entity_id=(
                program.drug_entity_id
                if context.include_unpublished
                else drug_identities[str(program.drug_entity_id)][0]
            ),
            drug_name=(drug_name if context.include_unpublished else drug_identities[str(program.drug_entity_id)][1]),
            target_entity_id=(
                primary_targets[program.id].entity_id
                if program.id in primary_targets
                else program.target_entity_id
                if context.include_unpublished
                else None
            ),
            target_name=(primary_targets[program.id].name if program.id in primary_targets else target_name),
            targets=target_map.get(program.id, []),
            target_combination_key=(
                program.target_combination_key or program.target_entity_id
                if context.include_unpublished
                else target_combination_keys.get(program.id)
            ),
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
        for program, drug_name, target_name, disease_name, organization_name in rows
    ]
