from __future__ import annotations

from sqlalchemy import and_, case, func, select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.entity_filters import _activity_filters, _target_evidence_filters
from pharma_intel.intelligence.vocabulary import _sar_comparability_reasons
from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    CompoundStructure,
    Entity,
    MeasurementRelation,
    TargetEvidenceObservation,
)
from pharma_intel.schemas import BioactivityRead, SarActivityRead, SarComparisonResult, TargetEvidenceRead


def target_evidence_for_entity(
    context: QueryContext,
    entity_id: str,
    limit: int,
    offset: int = 0,
    *,
    evidence_type: str | None = None,
    direction: str | None = None,
    disease_entity_id: str | None = None,
) -> list[TargetEvidenceRead]:
    target = Entity.__table__.alias("target_evidence_target")
    disease = Entity.__table__.alias("target_evidence_disease")
    rows = context.session.execute(
        select(
            TargetEvidenceObservation,
            target.c.name.label("target_name"),
            disease.c.name.label("disease_name"),
        )
        .join(target, target.c.id == TargetEvidenceObservation.target_entity_id)
        .outerjoin(disease, disease.c.id == TargetEvidenceObservation.disease_entity_id)
        .where(
            *_target_evidence_filters(
                context,
                entity_id,
                evidence_type=evidence_type,
                direction=direction,
                disease_entity_id=disease_entity_id,
            )
        )
        .order_by(
            TargetEvidenceObservation.observed_at.desc().nullslast(),
            TargetEvidenceObservation.evidence_type,
            TargetEvidenceObservation.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        TargetEvidenceRead(
            id=item.id,
            source_system=item.source_system,
            source_record_id=item.source_record_id,
            target_entity_id=item.target_entity_id,
            target_name=target_name,
            disease_entity_id=item.disease_entity_id,
            disease_name=disease_name,
            evidence_type=item.evidence_type,
            direction=item.direction,
            study_name=item.study_name,
            population=item.population,
            tissue=item.tissue,
            variant=item.variant,
            effect_size=item.effect_size,
            effect_unit=item.effect_unit,
            p_value=item.p_value,
            sample_size=item.sample_size,
            summary=item.summary,
            observed_at=item.observed_at,
            qualifiers=item.qualifiers,
            source_document_id=item.source_document_id,
        )
        for item, target_name, disease_name in rows
    ]


def bioactivities(
    context: QueryContext, target_entity_id: str, standard_type: str | None, limit: int, offset: int = 0
) -> list[BioactivityRead]:
    filters = [
        ActivityMeasurement.tenant_id == context.tenant_id,
        ActivityMeasurement.target_entity_id == target_entity_id,
    ]
    if standard_type:
        filters.append(ActivityMeasurement.standard_type == standard_type)
    return _read_bioactivities(context, filters, limit, offset)


def bioactivities_for_entity(
    context: QueryContext, entity_id: str, standard_type: str | None, limit: int, offset: int = 0
) -> list[BioactivityRead]:
    filters = _activity_filters(context, entity_id)
    if standard_type:
        filters.append(ActivityMeasurement.standard_type == standard_type)
    return _read_bioactivities(context, filters, limit, offset)


def sar_comparison(
    context: QueryContext,
    target_entity_id: str,
    *,
    standard_type: str | None,
    assay_type: str | None,
    assay_format: str | None,
    organism: str | None,
    cell_line: str | None,
    limit: int,
    offset: int,
) -> SarComparisonResult:
    filters: list[ColumnElement[bool]] = [
        ActivityMeasurement.tenant_id == context.tenant_id,
        ActivityMeasurement.target_entity_id == target_entity_id,
    ]
    for field, value in (
        (ActivityMeasurement.standard_type, standard_type),
        (Assay.assay_type, assay_type),
        (Assay.assay_format, assay_format),
        (Assay.organism, organism),
        (Assay.cell_line, cell_line),
    ):
        if value:
            filters.append(field == value)

    comparable = and_(
        ActivityMeasurement.standard_type.is_not(None),
        ActivityMeasurement.pchembl_value.is_not(None),
        ActivityMeasurement.standard_relation == MeasurementRelation.EQUAL,
        Assay.assay_type.is_not(None),
        Assay.assay_format.is_not(None),
    )
    partition = (
        ActivityMeasurement.standard_type,
        Assay.assay_type,
        Assay.assay_format,
        Assay.organism,
        Assay.cell_line,
    )
    potency_rank = case(
        (
            comparable,
            func.rank().over(
                partition_by=partition,
                order_by=(
                    case((comparable, 0), else_=1),
                    ActivityMeasurement.pchembl_value.desc(),
                ),
            ),
        ),
        else_=None,
    ).label("potency_rank")
    strongest_pchembl = (
        func.max(case((comparable, ActivityMeasurement.pchembl_value), else_=None))
        .over(partition_by=partition)
        .label("strongest_pchembl")
    )
    latest_structure = (
        select(
            CompoundStructure.entity_id.label("entity_id"),
            CompoundStructure.canonical_smiles.label("canonical_smiles"),
            CompoundStructure.standard_inchi_key.label("standard_inchi_key"),
            func.row_number()
            .over(
                partition_by=CompoundStructure.entity_id,
                order_by=(CompoundStructure.updated_at.desc(), CompoundStructure.id),
            )
            .label("position"),
        )
        .where(CompoundStructure.tenant_id == context.tenant_id)
        .subquery("latest_sar_structure")
    )
    rows = context.session.execute(
        select(
            ActivityMeasurement,
            Assay,
            Entity.name.label("compound_name"),
            latest_structure.c.canonical_smiles,
            latest_structure.c.standard_inchi_key,
            potency_rank,
            strongest_pchembl,
        )
        .join(
            Assay,
            and_(Assay.id == ActivityMeasurement.assay_id, Assay.tenant_id == context.tenant_id),
        )
        .join(
            Entity,
            and_(Entity.id == ActivityMeasurement.compound_entity_id, Entity.tenant_id == context.tenant_id),
        )
        .outerjoin(
            latest_structure,
            and_(
                latest_structure.c.entity_id == ActivityMeasurement.compound_entity_id,
                latest_structure.c.position == 1,
            ),
        )
        .where(*filters)
        .order_by(
            ActivityMeasurement.standard_type,
            Assay.assay_type,
            Assay.assay_format,
            Assay.organism,
            Assay.cell_line,
            case((comparable, 0), else_=1),
            ActivityMeasurement.pchembl_value.desc().nullslast(),
            ActivityMeasurement.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    total, as_of = context.session.execute(
        select(func.count(ActivityMeasurement.id), func.max(ActivityMeasurement.updated_at))
        .join(
            Assay,
            and_(Assay.id == ActivityMeasurement.assay_id, Assay.tenant_id == context.tenant_id),
        )
        .where(*filters)
    ).one()
    facets = _sar_facets(context, filters)
    items: list[SarActivityRead] = []
    for activity, assay, compound_name, smiles, inchi_key, rank, strongest in rows:
        reasons = _sar_comparability_reasons(activity, assay)
        group = "|".join(
            (
                f"standard_type={activity.standard_type or 'unspecified'}",
                f"assay_type={assay.assay_type or 'unspecified'}",
                f"assay_format={assay.assay_format or 'unspecified'}",
                f"organism={assay.organism or 'unspecified'}",
                f"cell_line={assay.cell_line or 'unspecified'}",
            )
        )
        delta = None
        if not reasons and strongest is not None and activity.pchembl_value is not None:
            delta = activity.pchembl_value - float(strongest)
        items.append(
            SarActivityRead(
                id=activity.id,
                compound_entity_id=activity.compound_entity_id,
                compound_name=compound_name,
                target_entity_id=target_entity_id,
                assay_id=activity.assay_id,
                assay_type=assay.assay_type,
                assay_format=assay.assay_format,
                organism=assay.organism,
                cell_line=assay.cell_line,
                standard_type=activity.standard_type,
                standard_relation=activity.standard_relation.value if activity.standard_relation else None,
                standard_value=float(activity.standard_value) if activity.standard_value is not None else None,
                standard_units=activity.standard_units,
                pchembl_value=activity.pchembl_value,
                comparison_group=group,
                comparable=not reasons,
                comparability_reasons=reasons,
                potency_rank=int(rank) if rank is not None and not reasons else None,
                delta_pchembl=delta,
                canonical_smiles=smiles,
                standard_inchi_key=inchi_key,
                validity_comment=activity.validity_comment,
                source_system=activity.source_system,
                source_activity_id=activity.source_activity_id,
                source_document_id=assay.source_document_id,
            )
        )
    return SarComparisonResult(
        items=items,
        total=int(total or 0),
        limit=limit,
        offset=offset,
        facets=facets,
        as_of=as_of,
        warnings=[
            "效力排名和 ΔpChEMBL 仅在标准类型、Assay 类型、Assay 格式、物种和细胞系完全一致的组内计算。",
            "缺失 pChEMBL、非等号关系或缺少关键 Assay 上下文的记录仅供溯源，不参与直接 SAR 排名。",
        ],
    )


def _sar_facets(context: QueryContext, filters: list[ColumnElement[bool]]) -> dict[str, dict[str, int]]:
    facets: dict[str, dict[str, int]] = {}
    for name, field in (
        ("standard_type", ActivityMeasurement.standard_type),
        ("assay_type", Assay.assay_type),
        ("assay_format", Assay.assay_format),
        ("organism", Assay.organism),
        ("cell_line", Assay.cell_line),
    ):
        rows = context.session.execute(
            select(field, func.count(ActivityMeasurement.id))
            .join(
                Assay,
                and_(Assay.id == ActivityMeasurement.assay_id, Assay.tenant_id == context.tenant_id),
            )
            .where(*filters, field.is_not(None))
            .group_by(field)
            .order_by(func.count(ActivityMeasurement.id).desc(), field)
            .limit(100)
        ).all()
        facets[name] = {str(value): int(count) for value, count in rows}
    return facets


def _read_bioactivities(
    context: QueryContext, filters: list[ColumnElement[bool]], limit: int, offset: int
) -> list[BioactivityRead]:
    rows = context.session.execute(
        select(ActivityMeasurement, Assay.source_document_id)
        .join(Assay, Assay.id == ActivityMeasurement.assay_id)
        .where(*filters)
        .order_by(
            ActivityMeasurement.pchembl_value.desc().nullslast(),
            ActivityMeasurement.id,
        )
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        BioactivityRead(
            id=activity.id,
            compound_entity_id=activity.compound_entity_id,
            target_entity_id=activity.target_entity_id,
            assay_id=activity.assay_id,
            standard_type=activity.standard_type,
            standard_relation=activity.standard_relation.value if activity.standard_relation else None,
            standard_value=float(activity.standard_value) if activity.standard_value is not None else None,
            standard_units=activity.standard_units,
            pchembl_value=activity.pchembl_value,
            reported_type=activity.reported_type,
            reported_relation=activity.reported_relation.value,
            reported_value=activity.reported_value,
            reported_units=activity.reported_units,
            source_system=activity.source_system,
            source_activity_id=activity.source_activity_id,
            source_document_id=source_document_id,
        )
        for activity, source_document_id in rows
    ]
