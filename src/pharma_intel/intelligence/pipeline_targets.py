from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, func, literal, select, union_all
from sqlalchemy.dialects.postgresql import aggregate_order_by

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.vocabulary import _meaningful_entity_name_sql
from pharma_intel.models import DevelopmentProgramTarget, Entity, EntityCanonicalLink, EntityType, ReviewStatus
from pharma_intel.schemas import PipelineTargetAggregation


def _pipeline_entity_identity_source(
    context: QueryContext,
    source: Any,
    entity_id_column: str,
    entity_name_column: str,
    entity_type: EntityType,
) -> Any:
    entity = Entity.__table__.alias(f"landscape_{entity_type.value}_entity")
    canonical_link = EntityCanonicalLink.__table__.alias(f"landscape_{entity_type.value}_canonical_link")
    canonical_entity = Entity.__table__.alias(f"landscape_{entity_type.value}_canonical_entity")
    verified_entity = Entity.__table__.alias(f"landscape_{entity_type.value}_verified_entity")
    raw_entity_id = source.c[entity_id_column]
    raw_entity_name = source.c[entity_name_column]
    canonical_entity_id = (
        select(canonical_link.c.canonical_entity_id)
        .where(
            canonical_link.c.tenant_id == context.tenant_id,
            canonical_link.c.alias_entity_id == entity.c.id,
            canonical_link.c.active.is_(True),
        )
        .correlate(entity)
        .limit(1)
        .scalar_subquery()
    )
    verified_entity_id = (
        select(func.min(verified_entity.c.id))
        .where(
            verified_entity.c.tenant_id == context.tenant_id,
            verified_entity.c.entity_type == entity_type,
            verified_entity.c.normalized_name == entity.c.normalized_name,
            verified_entity.c.review_status == ReviewStatus.VERIFIED,
        )
        .correlate(entity)
        .scalar_subquery()
    )
    canonical_entity_name = (
        select(canonical_entity.c.name)
        .select_from(
            canonical_link.join(
                canonical_entity,
                canonical_entity.c.id == canonical_link.c.canonical_entity_id,
            )
        )
        .where(
            canonical_link.c.tenant_id == context.tenant_id,
            canonical_link.c.alias_entity_id == entity.c.id,
            canonical_link.c.active.is_(True),
        )
        .correlate(entity)
        .limit(1)
        .scalar_subquery()
    )
    verified_entity_name = (
        select(verified_entity.c.name)
        .where(
            verified_entity.c.tenant_id == context.tenant_id,
            verified_entity.c.entity_type == entity_type,
            verified_entity.c.normalized_name == entity.c.normalized_name,
            verified_entity.c.review_status == ReviewStatus.VERIFIED,
        )
        .order_by(verified_entity.c.id)
        .correlate(entity)
        .limit(1)
        .scalar_subquery()
    )
    identity_id = func.coalesce(canonical_entity_id, verified_entity_id, raw_entity_id)
    identity_name = func.coalesce(canonical_entity_name, verified_entity_name, entity.c.name, raw_entity_name)
    return (
        select(
            source.c.program_id.label("program_id"),
            identity_id.label("entity_id"),
            identity_name.label("entity_name"),
            source.c.phase.label("phase"),
            source.c.global_phase.label("global_phase"),
            source.c.china_phase.label("china_phase"),
        )
        .select_from(source.outerjoin(entity, entity.c.id == raw_entity_id))
        .subquery(f"pipeline_{entity_type.value}_identity")
    )


def _pipeline_target_source(
    context: QueryContext,
    source: Any,
    target_aggregation: PipelineTargetAggregation = "all",
) -> Any:
    link = DevelopmentProgramTarget.__table__.alias("landscape_program_target")
    target = Entity.__table__.alias("landscape_target")
    canonical_link = EntityCanonicalLink.__table__.alias("landscape_target_canonical_link")
    canonical_target = Entity.__table__.alias("landscape_canonical_target")
    verified_target = Entity.__table__.alias("landscape_verified_target")
    canonical_target_id = (
        select(canonical_link.c.canonical_entity_id)
        .where(
            canonical_link.c.tenant_id == context.tenant_id,
            canonical_link.c.alias_entity_id == target.c.id,
            canonical_link.c.active.is_(True),
        )
        .correlate(target)
        .limit(1)
        .scalar_subquery()
    )
    verified_target_id = (
        select(func.min(verified_target.c.id))
        .where(
            verified_target.c.tenant_id == context.tenant_id,
            verified_target.c.entity_type == EntityType.TARGET,
            verified_target.c.normalized_name == target.c.normalized_name,
            verified_target.c.review_status == ReviewStatus.VERIFIED,
        )
        .correlate(target)
        .scalar_subquery()
    )
    canonical_target_name = (
        select(canonical_target.c.name)
        .select_from(
            canonical_link.join(canonical_target, canonical_target.c.id == canonical_link.c.canonical_entity_id)
        )
        .where(
            canonical_link.c.tenant_id == context.tenant_id,
            canonical_link.c.alias_entity_id == target.c.id,
            canonical_link.c.active.is_(True),
        )
        .correlate(target)
        .limit(1)
        .scalar_subquery()
    )
    verified_target_name = (
        select(verified_target.c.name)
        .where(
            verified_target.c.tenant_id == context.tenant_id,
            verified_target.c.entity_type == EntityType.TARGET,
            verified_target.c.normalized_name == target.c.normalized_name,
            verified_target.c.review_status == ReviewStatus.VERIFIED,
        )
        .order_by(verified_target.c.id)
        .correlate(target)
        .limit(1)
        .scalar_subquery()
    )
    target_identity_id = func.coalesce(canonical_target_id, verified_target_id, target.c.id)
    target_identity_name = func.coalesce(canonical_target_name, verified_target_name, target.c.name)
    current_link = (
        select(literal(1))
        .select_from(link)
        .where(
            link.c.tenant_id == context.tenant_id,
            link.c.program_id == source.c.program_id,
            link.c.target_set_version == source.c.target_set_version,
        )
        .correlate(source)
        .exists()
    )
    linked = (
        select(
            source.c.program_id.label("program_id"),
            target_identity_id.label("target_entity_id"),
            target_identity_name.label("target_name"),
            link.c.position.label("target_position"),
            source.c.phase.label("phase"),
            source.c.global_phase.label("global_phase"),
            source.c.china_phase.label("china_phase"),
        )
        .select_from(
            source.join(
                link,
                and_(
                    link.c.tenant_id == context.tenant_id,
                    link.c.program_id == source.c.program_id,
                    link.c.target_set_version == source.c.target_set_version,
                ),
            ).join(target, target.c.id == link.c.target_entity_id)
        )
        .where(_meaningful_entity_name_sql(target.c.name))
    )
    if target_aggregation == "primary":
        candidate_link = DevelopmentProgramTarget.__table__.alias("landscape_primary_target_candidate")
        candidate_target = Entity.__table__.alias("landscape_primary_target_entity")
        first_meaningful_position = (
            select(func.min(candidate_link.c.position))
            .select_from(
                candidate_link.join(candidate_target, candidate_target.c.id == candidate_link.c.target_entity_id)
            )
            .where(
                candidate_link.c.tenant_id == context.tenant_id,
                candidate_link.c.program_id == source.c.program_id,
                candidate_link.c.target_set_version == source.c.target_set_version,
                _meaningful_entity_name_sql(candidate_target.c.name),
            )
            .correlate(source)
            .scalar_subquery()
        )
        linked = linked.where(link.c.position == first_meaningful_position)
    meaningful_legacy_target = _meaningful_entity_name_sql(source.c.target_name)
    legacy = select(
        source.c.program_id.label("program_id"),
        case((meaningful_legacy_target, source.c.target_entity_id), else_=None).label("target_entity_id"),
        case((meaningful_legacy_target, source.c.target_name), else_=None).label("target_name"),
        literal(0).label("target_position"),
        source.c.phase.label("phase"),
        source.c.global_phase.label("global_phase"),
        source.c.china_phase.label("china_phase"),
    ).where(~current_link)
    return union_all(linked, legacy).subquery("pipeline_landscape_targets")


def _pipeline_distinct_target_count(
    context: QueryContext,
    source: Any,
    target_aggregation: PipelineTargetAggregation = "all",
) -> int:
    target_source = _pipeline_target_source(context, source, target_aggregation)
    return int(
        context.session.scalar(
            select(func.count(func.distinct(target_source.c.target_entity_id))).select_from(target_source)
        )
        or 0
    )


def _pipeline_target_combination_source(context: QueryContext, source: Any) -> Any:
    target_source = _pipeline_target_source(context, source)
    canonical_targets = (
        select(
            target_source.c.program_id,
            target_source.c.target_entity_id,
            target_source.c.target_name,
            func.min(target_source.c.target_position).label("target_position"),
            target_source.c.phase,
            target_source.c.global_phase,
            target_source.c.china_phase,
        )
        .where(target_source.c.target_entity_id.is_not(None), target_source.c.target_name.is_not(None))
        .group_by(
            target_source.c.program_id,
            target_source.c.target_entity_id,
            target_source.c.target_name,
            target_source.c.phase,
            target_source.c.global_phase,
            target_source.c.china_phase,
        )
        .order_by(
            target_source.c.program_id,
            func.min(target_source.c.target_position),
            target_source.c.target_entity_id,
        )
        .subquery("pipeline_canonical_combination_targets")
    )
    if context.session.get_bind().dialect.name == "postgresql":
        combination_key = func.string_agg(
            canonical_targets.c.target_entity_id,
            aggregate_order_by(literal("|"), canonical_targets.c.target_entity_id),
        )
        combination_label = func.string_agg(
            canonical_targets.c.target_name,
            aggregate_order_by(
                literal(" + "),
                canonical_targets.c.target_position,
                canonical_targets.c.target_entity_id,
            ),
        )
    else:
        ordered_key_targets = (
            select(canonical_targets)
            .order_by(canonical_targets.c.program_id, canonical_targets.c.target_entity_id)
            .subquery("pipeline_combination_key_targets")
        )
        ordered_label_targets = (
            select(canonical_targets)
            .order_by(
                canonical_targets.c.program_id,
                canonical_targets.c.target_position,
                canonical_targets.c.target_entity_id,
            )
            .subquery("pipeline_combination_label_targets")
        )
        combination_keys = (
            select(
                ordered_key_targets.c.program_id,
                func.group_concat(ordered_key_targets.c.target_entity_id, "|").label("target_combination_key"),
            )
            .group_by(ordered_key_targets.c.program_id)
            .subquery("pipeline_combination_keys")
        )
        combination_labels = (
            select(
                ordered_label_targets.c.program_id,
                func.group_concat(ordered_label_targets.c.target_name, " + ").label("target_combination_label"),
            )
            .group_by(ordered_label_targets.c.program_id)
            .subquery("pipeline_combination_labels")
        )
        return (
            select(
                canonical_targets.c.program_id,
                combination_keys.c.target_combination_key,
                combination_labels.c.target_combination_label,
                canonical_targets.c.phase,
                canonical_targets.c.global_phase,
                canonical_targets.c.china_phase,
            )
            .join(combination_keys, combination_keys.c.program_id == canonical_targets.c.program_id)
            .join(combination_labels, combination_labels.c.program_id == canonical_targets.c.program_id)
            .group_by(
                canonical_targets.c.program_id,
                combination_keys.c.target_combination_key,
                combination_labels.c.target_combination_label,
                canonical_targets.c.phase,
                canonical_targets.c.global_phase,
                canonical_targets.c.china_phase,
            )
            .subquery("pipeline_target_combinations")
        )
    return (
        select(
            canonical_targets.c.program_id,
            combination_key.label("target_combination_key"),
            combination_label.label("target_combination_label"),
            canonical_targets.c.phase,
            canonical_targets.c.global_phase,
            canonical_targets.c.china_phase,
        )
        .group_by(
            canonical_targets.c.program_id,
            canonical_targets.c.phase,
            canonical_targets.c.global_phase,
            canonical_targets.c.china_phase,
        )
        .subquery("pipeline_target_combinations")
    )
