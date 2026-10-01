from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.pipeline_organizations import _pipeline_organization_source
from pharma_intel.intelligence.pipeline_targets import (
    _pipeline_distinct_target_count,
    _pipeline_entity_identity_source,
    _pipeline_target_combination_source,
    _pipeline_target_source,
)
from pharma_intel.models import EntityType
from pharma_intel.schemas import (
    PipelineLandscapeBucketRead,
    PipelineLandscapeRead,
    PipelineLandscapeStageScope,
    PipelineTargetAggregation,
)


def _pipeline_landscape(
    context: QueryContext,
    source: Any,
    total: int,
    *,
    limit: int,
    stage_scope: PipelineLandscapeStageScope,
    target_aggregation: PipelineTargetAggregation,
) -> PipelineLandscapeRead:
    distinct_drugs = int(
        context.session.scalar(select(func.count(func.distinct(source.c.drug_identity_id))).select_from(source)) or 0
    )
    disease_source = _pipeline_entity_identity_source(
        context,
        source,
        "disease_entity_id",
        "disease_name",
        EntityType.DISEASE,
    )
    distinct_diseases = int(
        context.session.scalar(
            select(func.count(func.distinct(disease_source.c.entity_id))).select_from(disease_source)
        )
        or 0
    )
    organization_source = _pipeline_organization_source(context, source)
    organization_identity_source = _pipeline_entity_identity_source(
        context,
        organization_source,
        "organization_entity_id",
        "organization_name",
        EntityType.ORGANIZATION,
    )
    distinct_organizations = int(
        context.session.scalar(
            select(func.count(func.distinct(organization_identity_source.c.entity_id))).select_from(
                organization_identity_source
            )
        )
        or 0
    )
    return PipelineLandscapeRead(
        total_programs=total,
        distinct_drugs=distinct_drugs,
        distinct_targets=_pipeline_distinct_target_count(context, source, target_aggregation),
        distinct_diseases=distinct_diseases,
        distinct_organizations=distinct_organizations,
        limit=limit,
        stage_scope=stage_scope,
        target_aggregation=target_aggregation,
        overall_phase=_pipeline_scalar_landscape(context, source, "phase", total, limit=limit),
        global_phase=_pipeline_scalar_landscape(context, source, "global_phase", total, limit=limit),
        china_phase=_pipeline_scalar_landscape(context, source, "china_phase", total, limit=limit),
        targets=_pipeline_target_landscape(
            context,
            source,
            total,
            limit=limit,
            stage_scope=stage_scope,
            target_aggregation=target_aggregation,
        ),
        diseases=_pipeline_entity_landscape(
            context,
            disease_source,
            "entity_id",
            "entity_name",
            total,
            limit=limit,
            stage_scope=stage_scope,
        ),
        target_combinations=_pipeline_target_combinations(
            context,
            source,
            total,
            limit=limit,
            stage_scope=stage_scope,
        ),
        modality=_pipeline_scalar_landscape(context, source, "modality", total, limit=limit, stage_scope=stage_scope),
        geography=_pipeline_scalar_landscape(context, source, "geography", total, limit=limit, stage_scope=stage_scope),
        organizations=_pipeline_entity_landscape(
            context,
            organization_identity_source,
            "entity_id",
            "entity_name",
            total,
            limit=limit,
            stage_scope=stage_scope,
        ),
    )


def _pipeline_scalar_landscape(
    context: QueryContext,
    source: Any,
    column_name: str,
    total: int,
    *,
    limit: int = 20,
    stage_scope: PipelineLandscapeStageScope | None = None,
) -> list[PipelineLandscapeBucketRead]:
    column = source.c[column_name]
    rows = context.session.execute(
        select(column, func.count(func.distinct(source.c.program_id)))
        .select_from(source)
        .group_by(column)
        .order_by(func.count(func.distinct(source.c.program_id)).desc(), column)
        .limit(limit)
    ).all()
    buckets: list[PipelineLandscapeBucketRead] = []
    phase_counts = _pipeline_phase_counts(context, source, column, [row[0] for row in rows], stage_scope)
    for value, count in rows:
        key = value.value if hasattr(value, "value") else str(value) if value is not None else "__missing__"
        buckets.append(
            PipelineLandscapeBucketRead(
                key=key,
                label="未披露" if value is None else key,
                count=int(count),
                share=round(int(count) / total, 6) if total else 0,
                phase_counts=phase_counts.get(key, {}),
            )
        )
    return buckets


def _pipeline_entity_landscape(
    context: QueryContext,
    source: Any,
    entity_id_column: str,
    entity_name_column: str,
    total: int,
    *,
    limit: int = 20,
    stage_scope: PipelineLandscapeStageScope = "overall",
) -> list[PipelineLandscapeBucketRead]:
    entity_id = source.c[entity_id_column]
    entity_name = source.c[entity_name_column]
    rows = context.session.execute(
        select(
            entity_id,
            entity_name,
            func.count(func.distinct(source.c.program_id)),
        )
        .select_from(source)
        .group_by(entity_id, entity_name)
        .order_by(
            func.count(func.distinct(source.c.program_id)).desc(),
            entity_name,
            entity_id,
        )
        .limit(limit)
    ).all()
    phase_counts = _pipeline_phase_counts(context, source, entity_id, [row[0] for row in rows], stage_scope)
    return [
        PipelineLandscapeBucketRead(
            key=entity_id or "__missing__",
            label=entity_name or "未披露",
            count=int(count),
            share=round(int(count) / total, 6) if total else 0,
            entity_id=entity_id,
            phase_counts=phase_counts.get(entity_id or "__missing__", {}),
        )
        for entity_id, entity_name, count in rows
    ]


def _pipeline_target_landscape(
    context: QueryContext,
    source: Any,
    total: int,
    *,
    limit: int = 20,
    stage_scope: PipelineLandscapeStageScope = "overall",
    target_aggregation: PipelineTargetAggregation = "all",
) -> list[PipelineLandscapeBucketRead]:
    target_source = _pipeline_target_source(context, source, target_aggregation)
    rows = context.session.execute(
        select(
            target_source.c.target_entity_id,
            target_source.c.target_name,
            func.count(func.distinct(target_source.c.program_id)),
        )
        .group_by(target_source.c.target_entity_id, target_source.c.target_name)
        .order_by(
            func.count(func.distinct(target_source.c.program_id)).desc(),
            target_source.c.target_name,
            target_source.c.target_entity_id,
        )
        .limit(limit)
    ).all()
    phase_counts = _pipeline_phase_counts(
        context,
        target_source,
        target_source.c.target_entity_id,
        [row[0] for row in rows],
        stage_scope,
    )
    return [
        PipelineLandscapeBucketRead(
            key=target_id or "__missing__",
            label=target_name or "未披露",
            count=int(count),
            share=round(int(count) / total, 6) if total else 0,
            entity_id=target_id,
            phase_counts=phase_counts.get(target_id or "__missing__", {}),
        )
        for target_id, target_name, count in rows
    ]


def _pipeline_target_combinations(
    context: QueryContext,
    source: Any,
    total: int,
    *,
    limit: int = 20,
    stage_scope: PipelineLandscapeStageScope = "overall",
) -> list[PipelineLandscapeBucketRead]:
    combination_source = _pipeline_target_combination_source(context, source)
    rows = context.session.execute(
        select(
            combination_source.c.target_combination_key,
            combination_source.c.target_combination_label,
            func.count(func.distinct(combination_source.c.program_id)),
        )
        .select_from(combination_source)
        .group_by(
            combination_source.c.target_combination_key,
            combination_source.c.target_combination_label,
        )
        .order_by(
            func.count(func.distinct(combination_source.c.program_id)).desc(),
            combination_source.c.target_combination_label,
            combination_source.c.target_combination_key,
        )
        .limit(limit)
    ).all()
    phase_counts = _pipeline_phase_counts(
        context,
        combination_source,
        combination_source.c.target_combination_key,
        [row[0] for row in rows],
        stage_scope,
    )
    buckets: list[PipelineLandscapeBucketRead] = []
    for combination_key, combination_label, count in rows:
        ids = str(combination_key).split("|")
        buckets.append(
            PipelineLandscapeBucketRead(
                key=str(combination_key),
                label=str(combination_label),
                count=int(count),
                share=round(int(count) / total, 6) if total else 0,
                entity_id=ids[0] if len(ids) == 1 else None,
                phase_counts=phase_counts.get(str(combination_key), {}),
            )
        )
    return buckets


def _pipeline_phase_counts(
    context: QueryContext,
    source: Any,
    bucket_column: Any,
    bucket_values: list[Any],
    stage_scope: PipelineLandscapeStageScope | None,
) -> dict[str, dict[str, int]]:
    if stage_scope is None or not bucket_values:
        return {}
    stage_column = source.c[{"overall": "phase", "global": "global_phase", "china": "china_phase"}[stage_scope]]
    non_null_values = [value for value in bucket_values if value is not None]
    predicates: list[ColumnElement[bool]] = []
    if non_null_values:
        predicates.append(bucket_column.in_(non_null_values))
    if any(value is None for value in bucket_values):
        predicates.append(bucket_column.is_(None))
    rows = context.session.execute(
        select(
            bucket_column,
            stage_column,
            func.count(func.distinct(source.c.program_id)),
        )
        .select_from(source)
        .where(or_(*predicates))
        .group_by(bucket_column, stage_column)
    ).all()
    result: dict[str, dict[str, int]] = {}
    for bucket_value, stage_value, count in rows:
        bucket_key = (
            bucket_value.value
            if hasattr(bucket_value, "value")
            else str(bucket_value)
            if bucket_value is not None
            else "__missing__"
        )
        stage_key = (
            stage_value.value
            if hasattr(stage_value, "value")
            else str(stage_value)
            if stage_value is not None
            else "__missing__"
        )
        result.setdefault(bucket_key, {})[stage_key] = int(count)
    return result
