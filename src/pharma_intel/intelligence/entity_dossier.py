from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import and_, or_, select, true
from sqlalchemy.orm import selectinload

from pharma_intel.intelligence.bioactivity import bioactivities_for_entity, target_evidence_for_entity
from pharma_intel.intelligence.clinical_filters import _clinical_trial_filters
from pharma_intel.intelligence.clinical_read import clinical_trial_search_items
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_filters import _deal_filters
from pharma_intel.intelligence.deal_read import _deal_search_items
from pharma_intel.intelligence.entity_filters import (
    _activity_filters,
    _evidence_filters,
    _relationship_filters,
    _structure_filters,
    _target_evidence_filters,
)
from pharma_intel.intelligence.news import _news_event_filters, news_event_search_items
from pharma_intel.intelligence.patents import _patent_filters, patents
from pharma_intel.intelligence.pipeline_filters import _program_filters
from pharma_intel.intelligence.pipeline_read import programs_for_entity
from pharma_intel.intelligence.regulatory import _regulatory_filters, regulatory_search_items
from pharma_intel.intelligence.scope import _count
from pharma_intel.intelligence.structures import structures
from pharma_intel.models import (
    ActivityMeasurement,
    ClinicalTrialProfile,
    CompoundStructure,
    DealProfile,
    DevelopmentProgram,
    Entity,
    EvidenceClaim,
    NewsEvent,
    PatentFamily,
    RegulatoryEvent,
    Relationship,
    ReviewStatus,
    TargetEvidenceObservation,
)
from pharma_intel.schemas import (
    EntityDossierCoverageRead,
    EntityDossierDomain,
    EntityDossierResponse,
    EntityRead,
    EntityRelationshipRead,
)


def entity_dossier(context: QueryContext, entity_id: str, limit: int = 50) -> EntityDossierResponse | None:
    entity = context.session.scalar(
        select(Entity).where(
            Entity.id == entity_id,
            Entity.tenant_id == context.tenant_id,
            Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        )
    )
    if entity is None:
        return None

    relationship_items = relationships(context, entity_id, limit)
    activities = bioactivities_for_entity(context, entity_id, None, limit)
    programs = programs_for_entity(context, entity_id, limit)
    clinical_trials = clinical_trial_search_items(
        context,
        entity_id,
        None,
        None,
        None,
        None,
        None,
        None,
        limit,
    )
    patent_items = patents(context, entity_id, None, limit)
    deals = _deal_search_items(context, _deal_filters(context, entity_id), limit, 0)
    regulatory_events = regulatory_search_items(context, entity_id, None, None, None, None, None, limit)
    news_events = news_event_search_items(context, entity_id, None, None, None, None, None, None, None, limit)
    structure_items = structures(context, entity_id, None, limit)
    target_evidence = target_evidence_for_entity(context, entity_id, limit)

    counts: dict[EntityDossierDomain, int] = {
        "relationships": _count(context, Relationship, _relationship_filters(context, entity_id)),
        "evidence": _count(context, EvidenceClaim, _evidence_filters(context, entity_id)),
        "activities": _count(context, ActivityMeasurement, _activity_filters(context, entity_id)),
        "programs": _count(context, DevelopmentProgram, _program_filters(context, entity_id)),
        "clinical_trials": _count(context, ClinicalTrialProfile, _clinical_trial_filters(context, entity_id, None)),
        "patents": _count(context, PatentFamily, _patent_filters(context, entity_id, None)),
        "deals": _count(context, DealProfile, _deal_filters(context, entity_id)),
        "regulatory_events": _count(context, RegulatoryEvent, _regulatory_filters(context, entity_id, None, None)),
        "news_events": _count(
            context,
            NewsEvent,
            _news_event_filters(context, entity_id, None, None, None, None, None, None, None),
        ),
        "structures": _count(context, CompoundStructure, _structure_filters(context, entity_id, None)),
        "target_evidence": _count(
            context,
            TargetEvidenceObservation,
            _target_evidence_filters(context, entity_id),
        ),
    }
    returned: dict[EntityDossierDomain, int] = {
        "relationships": len(relationship_items),
        "evidence": 0,
        "activities": len(activities),
        "programs": len(programs),
        "clinical_trials": len(clinical_trials),
        "patents": len(patent_items),
        "deals": len(deals),
        "regulatory_events": len(regulatory_events),
        "news_events": len(news_events),
        "structures": len(structure_items),
        "target_evidence": len(target_evidence),
    }
    coverage: list[EntityDossierCoverageRead] = []
    for domain, total in counts.items():
        returned_count = returned[domain]
        status: Literal["available", "not_observed", "truncated"]
        if total == 0:
            status = "not_observed"
            note = "当前可查看范围和数据更新时间内暂无记录"
        elif domain == "evidence":
            status = "available"
            note = "实体级证据通过证据检索和记录来源接口按许可读取"
        elif returned_count < total:
            status = "truncated"
            note = f"返回前 {returned_count} 条，完整结果请使用对应分页接口"
        else:
            status = "available"
            note = "已返回当前匹配记录"
        coverage.append(
            EntityDossierCoverageRead(
                domain=domain,
                total=total,
                returned=returned_count,
                status=status,
                note=note,
            )
        )
    warnings = ["暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。"]
    return EntityDossierResponse(
        entity=EntityRead.model_validate(entity),
        relationships=relationship_items,
        activities=activities,
        programs=programs,
        clinical_trials=clinical_trials,
        patents=patent_items,
        deals=deals,
        regulatory_events=regulatory_events,
        news_events=news_events,
        structures=structure_items,
        target_evidence=target_evidence,
        coverage=coverage,
        as_of=datetime.now(UTC),
        warnings=warnings,
    )


def relationships(context: QueryContext, entity_id: str, limit: int, offset: int = 0) -> list[EntityRelationshipRead]:
    rows = context.session.execute(
        select(Relationship, Entity)
        .options(selectinload(Entity.aliases))
        .join(
            Entity,
            and_(
                Entity.tenant_id == context.tenant_id,
                or_(
                    and_(Relationship.subject_id == entity_id, Entity.id == Relationship.object_id),
                    and_(Relationship.object_id == entity_id, Entity.id == Relationship.subject_id),
                ),
            ),
        )
        .where(*_relationship_filters(context, entity_id))
        .order_by(Relationship.updated_at.desc(), Relationship.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        EntityRelationshipRead(
            id=relationship.id,
            predicate=relationship.predicate,
            direction="outgoing" if relationship.subject_id == entity_id else "incoming",
            related_entity=EntityRead.model_validate(related),
            attributes=relationship.attributes,
            review_status=relationship.review_status,
            valid_from=relationship.valid_from,
            valid_to=relationship.valid_to,
        )
        for relationship, related in rows
    ]
