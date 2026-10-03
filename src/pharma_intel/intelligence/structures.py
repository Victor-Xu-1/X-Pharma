from __future__ import annotations

from sqlalchemy import or_, select, union

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.entity_filters import _structure_filters
from pharma_intel.intelligence.pipeline_predicates import _program_target_exists
from pharma_intel.models import ActivityMeasurement, CompoundStructure, DevelopmentProgram
from pharma_intel.schemas import CompoundStructureRead


def structures(
    context: QueryContext,
    entity_id: str | None,
    inchi_key: str | None,
    limit: int,
    offset: int = 0,
) -> list[CompoundStructureRead]:
    filters = _structure_filters(context, entity_id, inchi_key)
    rows = context.session.scalars(
        select(CompoundStructure).where(*filters).order_by(CompoundStructure.id).limit(limit).offset(offset)
    ).all()
    return [CompoundStructureRead.model_validate(row) for row in rows]


def structures_for_target(
    context: QueryContext,
    target_entity_id: str,
    limit: int,
    offset: int = 0,
) -> list[CompoundStructureRead]:
    """Return structures for compounds connected to a target through governed data.

    Target dossiers must expose compound structures through activity and pipeline
    relationships; a structure row is owned by its compound entity, not by the
    target. Direct target-owned rows remain readable for legacy imports.
    """

    direct_compounds = select(CompoundStructure.entity_id.label("compound_entity_id")).where(
        CompoundStructure.tenant_id == context.tenant_id,
        CompoundStructure.entity_id == target_entity_id,
    )
    activity_compounds = select(ActivityMeasurement.compound_entity_id.label("compound_entity_id")).where(
        ActivityMeasurement.tenant_id == context.tenant_id,
        ActivityMeasurement.target_entity_id == target_entity_id,
    )
    program_compounds = select(DevelopmentProgram.drug_entity_id.label("compound_entity_id")).where(
        DevelopmentProgram.tenant_id == context.tenant_id,
        DevelopmentProgram.drug_entity_id.is_not(None),
        or_(
            DevelopmentProgram.target_entity_id == target_entity_id,
            _program_target_exists(context, target_entity_id),
        ),
    )
    compound_ids = union(direct_compounds, activity_compounds, program_compounds).subquery()
    rows = context.session.scalars(
        select(CompoundStructure)
        .where(
            CompoundStructure.tenant_id == context.tenant_id,
            CompoundStructure.entity_id.in_(select(compound_ids.c.compound_entity_id)),
        )
        .order_by(CompoundStructure.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [CompoundStructureRead.model_validate(row) for row in rows]
