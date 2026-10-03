from __future__ import annotations

from sqlalchemy import or_, true
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.scope import _published_entity_exists, _published_optional_entity
from pharma_intel.models import (
    ActivityMeasurement,
    CompoundStructure,
    EvidenceClaim,
    Relationship,
    ReviewStatus,
    TargetEvidenceObservation,
)


def _relationship_filters(context: QueryContext, entity_id: str) -> list[ColumnElement[bool]]:
    filters = [
        Relationship.tenant_id == context.tenant_id,
        Relationship.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        or_(Relationship.subject_id == entity_id, Relationship.object_id == entity_id),
    ]
    if not context.include_unpublished:
        filters.extend(
            [
                _published_entity_exists(context, Relationship.subject_id),
                _published_entity_exists(context, Relationship.object_id),
            ]
        )
    return filters


def _evidence_filters(context: QueryContext, entity_id: str) -> list[ColumnElement[bool]]:
    filters = [
        EvidenceClaim.tenant_id == context.tenant_id,
        EvidenceClaim.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        or_(EvidenceClaim.subject_id == entity_id, EvidenceClaim.object_id == entity_id),
    ]
    if not context.include_unpublished:
        filters.extend(
            [
                _published_entity_exists(context, EvidenceClaim.subject_id),
                _published_optional_entity(context, EvidenceClaim.object_id),
            ]
        )
    return filters


def _activity_filters(context: QueryContext, entity_id: str) -> list[ColumnElement[bool]]:
    filters = [
        ActivityMeasurement.tenant_id == context.tenant_id,
        or_(
            ActivityMeasurement.compound_entity_id == entity_id,
            ActivityMeasurement.target_entity_id == entity_id,
        ),
    ]
    if not context.include_unpublished:
        filters.extend(
            [
                _published_entity_exists(context, ActivityMeasurement.compound_entity_id),
                _published_entity_exists(context, ActivityMeasurement.target_entity_id),
            ]
        )
    return filters


def _structure_filters(
    context: QueryContext, entity_id: str | None, inchi_key: str | None
) -> list[ColumnElement[bool]]:
    filters = [CompoundStructure.tenant_id == context.tenant_id]
    if not context.include_unpublished:
        filters.append(_published_entity_exists(context, CompoundStructure.entity_id))
    if entity_id:
        filters.append(CompoundStructure.entity_id == entity_id)
    if inchi_key:
        filters.append(CompoundStructure.standard_inchi_key == inchi_key.upper())
    return filters


def _target_evidence_filters(
    context: QueryContext,
    entity_id: str,
    *,
    evidence_type: str | None = None,
    direction: str | None = None,
    disease_entity_id: str | None = None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = [
        TargetEvidenceObservation.tenant_id == context.tenant_id,
        or_(
            TargetEvidenceObservation.target_entity_id == entity_id,
            TargetEvidenceObservation.disease_entity_id == entity_id,
        ),
    ]
    if not context.include_unpublished:
        filters.extend(
            [
                _published_entity_exists(context, TargetEvidenceObservation.target_entity_id),
                _published_optional_entity(context, TargetEvidenceObservation.disease_entity_id),
            ]
        )
    if evidence_type is not None:
        filters.append(TargetEvidenceObservation.evidence_type == evidence_type)
    if direction is not None:
        filters.append(TargetEvidenceObservation.direction == direction)
    if disease_entity_id is not None:
        filters.append(TargetEvidenceObservation.disease_entity_id == disease_entity_id)
    return filters
