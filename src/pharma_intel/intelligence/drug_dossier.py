from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, func, select, union_all
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_filters import _deal_filters
from pharma_intel.intelligence.deal_read import _deal_search_items
from pharma_intel.intelligence.entity_dossier import entity_dossier
from pharma_intel.intelligence.pipeline_predicates import _unique_program_record
from pharma_intel.intelligence.scope import (
    _canonical_entity_identity_labels,
    _entity_identity_ids,
    _entity_identity_member_ids,
    _published_identity_exists,
    _published_optional_identity_entity,
)
from pharma_intel.intelligence.vocabulary import _DEVELOPMENT_PHASE_RANK, _public_program_modality_sql
from pharma_intel.models import (
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityType,
    ReviewStatus,
)
from pharma_intel.schemas import (
    DrugComparisonProfileRead,
    DrugComparisonResult,
    DrugDossierResponse,
    DrugDossierSummaryRead,
    EntityRead,
)


def drug_dossier(context: QueryContext, entity_id: str, limit: int = 100) -> DrugDossierResponse | None:
    dossier = entity_dossier(context, entity_id, limit)
    if dossier is None or dossier.entity.entity_type != EntityType.DRUG:
        return None

    program_filters = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        _unique_program_record(context),
        DevelopmentProgram.drug_entity_id.in_(_entity_identity_ids(context, entity_id, EntityType.DRUG)),
    ]

    def phase_rank(column: Any) -> Any:
        return case(
            *((column == DevelopmentPhase(phase), rank) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()),
            else_=None,
        )

    (
        program_count,
        indication_count,
        organization_count,
        highest_phase_rank,
        highest_global_phase_rank,
        highest_china_phase_rank,
        latest_status_date,
    ) = context.session.execute(
        select(
            func.count(DevelopmentProgram.id),
            func.count(func.distinct(DevelopmentProgram.disease_entity_id)),
            func.count(func.distinct(DevelopmentProgram.organization_entity_id)),
            func.max(phase_rank(DevelopmentProgram.phase)),
            func.max(phase_rank(DevelopmentProgram.global_phase)),
            func.max(phase_rank(DevelopmentProgram.china_phase)),
            func.max(DevelopmentProgram.status_date),
        ).where(*program_filters)
    ).one()

    current_target_ids = (
        select(DevelopmentProgramTarget.target_entity_id.label("target_entity_id"))
        .join(
            DevelopmentProgram,
            and_(
                DevelopmentProgram.id == DevelopmentProgramTarget.program_id,
                DevelopmentProgram.tenant_id == DevelopmentProgramTarget.tenant_id,
                DevelopmentProgram.target_set_version == DevelopmentProgramTarget.target_set_version,
            ),
        )
        .where(*program_filters)
    )
    legacy_target_ids = select(DevelopmentProgram.target_entity_id.label("target_entity_id")).where(
        *program_filters,
        DevelopmentProgram.target_entity_id.is_not(None),
    )
    target_ids = union_all(current_target_ids, legacy_target_ids).subquery()
    target_count = int(context.session.scalar(select(func.count(func.distinct(target_ids.c.target_entity_id)))) or 0)
    program_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    modalities = list(
        context.session.scalars(
            select(program_modality)
            .where(*program_filters, program_modality.is_not(None))
            .distinct()
            .order_by(program_modality)
            .limit(50)
        )
    )

    rank_to_phase = {rank: DevelopmentPhase(phase) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()}
    deal_items = _deal_search_items(context, _deal_filters(context, entity_id), limit, 0)
    return DrugDossierResponse(
        **dossier.model_dump(exclude={"deals"}),
        deals=deal_items,
        summary=DrugDossierSummaryRead(
            program_count=int(program_count or 0),
            target_count=target_count,
            indication_count=int(indication_count or 0),
            organization_count=int(organization_count or 0),
            modalities=modalities,
            highest_phase=rank_to_phase.get(highest_phase_rank),
            highest_global_phase=rank_to_phase.get(highest_global_phase_rank),
            highest_china_phase=rank_to_phase.get(highest_china_phase_rank),
            latest_status_date=(
                latest_status_date.replace(tzinfo=UTC)
                if latest_status_date is not None and latest_status_date.tzinfo is None
                else latest_status_date
            ),
        ),
    )


def drug_comparison_profiles(context: QueryContext, entity_ids: Sequence[str]) -> DrugComparisonResult:
    """Aggregate complete development profiles for a bounded drug batch.

    The comparison workspace must not infer portfolio-level dimensions from the
    truncated record lists in a generic dossier. This method keeps the request
    count independent of the number of compared drugs and computes every metric
    over the complete authorized program set.
    """

    ordered_ids = list(dict.fromkeys(entity_ids))
    as_of = datetime.now(UTC)
    if not ordered_ids:
        return DrugComparisonResult(items=[], as_of=as_of)

    raw_ids_by_requested = {
        entity_id: _entity_identity_member_ids(context, entity_id, EntityType.DRUG) for entity_id in ordered_ids
    }
    raw_to_requested: dict[str, str] = {}
    for requested_drug_id, raw_ids in raw_ids_by_requested.items():
        for raw_id in raw_ids:
            raw_to_requested.setdefault(raw_id, requested_drug_id)
    raw_entity_ids = set(raw_to_requested)

    entity_filters: list[ColumnElement[bool]] = [
        Entity.tenant_id == context.tenant_id,
        Entity.entity_type == EntityType.DRUG,
        Entity.id.in_(ordered_ids),
    ]
    if not context.include_unpublished:
        entity_filters.append(Entity.review_status == ReviewStatus.VERIFIED)
    entities = list(context.session.scalars(select(Entity).where(*entity_filters)))
    entities_by_id = {entity.id: entity for entity in entities}

    program_filters: list[ColumnElement[bool]] = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        DevelopmentProgram.drug_entity_id.in_(raw_entity_ids),
    ]
    if not context.include_unpublished:
        program_filters.extend(
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

    def phase_rank(column: Any) -> Any:
        return case(
            *((column == DevelopmentPhase(phase), rank) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()),
            else_=None,
        )

    summary_rows = context.session.execute(
        select(
            DevelopmentProgram.drug_entity_id,
            func.count(DevelopmentProgram.id),
            func.max(phase_rank(DevelopmentProgram.phase)),
            func.max(phase_rank(DevelopmentProgram.global_phase)),
            func.max(phase_rank(DevelopmentProgram.china_phase)),
            func.max(DevelopmentProgram.status_date),
        )
        .where(*program_filters)
        .group_by(DevelopmentProgram.drug_entity_id)
    ).all()
    summary_by_id: dict[str, tuple[int, int | None, int | None, int | None, datetime | None]] = {}
    for drug_id, count, phase, global_phase, china_phase, latest_status_date in summary_rows:
        requested_id = raw_to_requested.get(str(drug_id))
        if requested_id is None:
            continue
        previous = summary_by_id.get(requested_id)
        summary_by_id[requested_id] = (
            int(count or 0) + (previous[0] if previous else 0),
            max((previous[1] if previous else None), phase, key=lambda value: value if value is not None else -1),
            max(
                (previous[2] if previous else None),
                global_phase,
                key=lambda value: value if value is not None else -1,
            ),
            max(
                (previous[3] if previous else None),
                china_phase,
                key=lambda value: value if value is not None else -1,
            ),
            max(
                (previous[4] if previous else None),
                latest_status_date,
                key=lambda value: value if value is not None else datetime.min,
            ),
        )

    target_ids: dict[str, set[str]] = {entity_id: set() for entity_id in ordered_ids}
    target_names: dict[str, set[str]] = {entity_id: set() for entity_id in ordered_ids}
    indication_ids: dict[str, set[str]] = {entity_id: set() for entity_id in ordered_ids}
    indication_names: dict[str, set[str]] = {entity_id: set() for entity_id in ordered_ids}
    organization_ids: dict[str, set[str]] = {entity_id: set() for entity_id in ordered_ids}
    organization_names: dict[str, set[str]] = {entity_id: set() for entity_id in ordered_ids}
    modalities: dict[str, set[str]] = {entity_id: set() for entity_id in ordered_ids}
    status_counts: dict[str, dict[str, int]] = {entity_id: {} for entity_id in ordered_ids}

    current_target_filters = list(program_filters)
    if not context.include_unpublished:
        current_target_filters.append(
            _published_identity_exists(
                context,
                DevelopmentProgramTarget.target_entity_id,
                EntityType.TARGET,
                correlate_from=DevelopmentProgramTarget.__table__,
            )
        )
    current_targets = context.session.execute(
        select(
            DevelopmentProgram.drug_entity_id,
            DevelopmentProgramTarget.target_entity_id,
        )
        .join(
            DevelopmentProgramTarget,
            and_(
                DevelopmentProgramTarget.program_id == DevelopmentProgram.id,
                DevelopmentProgramTarget.tenant_id == DevelopmentProgram.tenant_id,
                DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
            ),
        )
        .where(*current_target_filters)
    ).all()
    legacy_targets = context.session.execute(
        select(DevelopmentProgram.drug_entity_id, DevelopmentProgram.target_entity_id).where(
            *program_filters,
            DevelopmentProgram.target_entity_id.is_not(None),
        )
    ).all()
    target_rows = [(drug_id, target_id) for drug_id, target_id in current_targets] + [
        (drug_id, target_id) for drug_id, target_id in legacy_targets if target_id is not None
    ]
    target_identities = _canonical_entity_identity_labels(
        context,
        {str(target_id) for _, target_id in target_rows},
        EntityType.TARGET,
    )
    for drug_id, raw_target_id in target_rows:
        requested_id = raw_to_requested.get(str(drug_id))
        identity = target_identities.get(str(raw_target_id))
        if requested_id is None or identity is None:
            continue
        target_id, name = identity
        target_ids[requested_id].add(target_id)
        target_names[requested_id].add(name)

    disease_rows = context.session.execute(
        select(DevelopmentProgram.drug_entity_id, DevelopmentProgram.disease_entity_id).where(
            *program_filters,
            DevelopmentProgram.disease_entity_id.is_not(None),
        )
    ).all()
    disease_identities = _canonical_entity_identity_labels(
        context,
        {str(disease_id) for _, disease_id in disease_rows},
        EntityType.DISEASE,
    )
    for drug_id, raw_disease_id in disease_rows:
        requested_id = raw_to_requested.get(str(drug_id))
        identity = disease_identities.get(str(raw_disease_id))
        if requested_id is None or identity is None:
            continue
        disease_id, name = identity
        indication_ids[requested_id].add(disease_id)
        indication_names[requested_id].add(name)

    current_organization_filters = list(program_filters)
    if not context.include_unpublished:
        current_organization_filters.append(
            _published_identity_exists(
                context,
                DevelopmentProgramOrganization.organization_entity_id,
                EntityType.ORGANIZATION,
                correlate_from=DevelopmentProgramOrganization.__table__,
            )
        )
    current_organizations = context.session.execute(
        select(
            DevelopmentProgram.drug_entity_id,
            DevelopmentProgramOrganization.organization_entity_id,
        )
        .join(
            DevelopmentProgramOrganization,
            and_(
                DevelopmentProgramOrganization.program_id == DevelopmentProgram.id,
                DevelopmentProgramOrganization.tenant_id == DevelopmentProgram.tenant_id,
                DevelopmentProgramOrganization.organization_set_version == DevelopmentProgram.organization_set_version,
            ),
        )
        .where(*current_organization_filters)
    ).all()
    legacy_organizations = context.session.execute(
        select(DevelopmentProgram.drug_entity_id, DevelopmentProgram.organization_entity_id).where(
            *program_filters,
            DevelopmentProgram.organization_entity_id.is_not(None),
        )
    ).all()
    organization_rows = [(drug_id, organization_id) for drug_id, organization_id in current_organizations] + [
        (drug_id, organization_id) for drug_id, organization_id in legacy_organizations if organization_id is not None
    ]
    organization_identities = _canonical_entity_identity_labels(
        context,
        {str(organization_id) for _, organization_id in organization_rows},
        EntityType.ORGANIZATION,
    )
    for drug_id, raw_organization_id in organization_rows:
        requested_id = raw_to_requested.get(str(drug_id))
        identity = organization_identities.get(str(raw_organization_id))
        if requested_id is None or identity is None:
            continue
        organization_id, name = identity
        organization_ids[requested_id].add(organization_id)
        organization_names[requested_id].add(name)

    program_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    for drug_id, modality in context.session.execute(
        select(DevelopmentProgram.drug_entity_id, program_modality)
        .where(*program_filters, program_modality.is_not(None))
        .distinct()
    ).all():
        requested_id = raw_to_requested.get(str(drug_id))
        if requested_id is not None:
            modalities[requested_id].add(modality)
    for drug_id, raw_status, count in context.session.execute(
        select(
            DevelopmentProgram.drug_entity_id,
            DevelopmentProgram.program_status,
            func.count(DevelopmentProgram.id),
        )
        .where(*program_filters)
        .group_by(DevelopmentProgram.drug_entity_id, DevelopmentProgram.program_status)
    ).all():
        requested_id = raw_to_requested.get(str(drug_id))
        if requested_id is not None:
            status_counts[requested_id][raw_status or "unknown"] = status_counts[requested_id].get(
                raw_status or "unknown", 0
            ) + int(count or 0)

    rank_to_phase = {rank: DevelopmentPhase(phase) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()}
    items: list[DrugComparisonProfileRead] = []
    for entity_id in ordered_ids:
        entity = entities_by_id.get(entity_id)
        if entity is None:
            continue
        summary = summary_by_id.get(entity_id)
        program_count, highest_phase, highest_global_phase, highest_china_phase, latest_status_date = (
            summary if summary is not None else (0, None, None, None, None)
        )
        items.append(
            DrugComparisonProfileRead(
                entity=EntityRead.model_validate(entity),
                summary=DrugDossierSummaryRead(
                    program_count=int(program_count or 0),
                    target_count=len(target_ids[entity_id]),
                    indication_count=len(indication_ids[entity_id]),
                    organization_count=len(organization_ids[entity_id]),
                    modalities=sorted(modalities[entity_id], key=str.casefold),
                    highest_phase=rank_to_phase.get(highest_phase) if highest_phase is not None else None,
                    highest_global_phase=(
                        rank_to_phase.get(highest_global_phase) if highest_global_phase is not None else None
                    ),
                    highest_china_phase=(
                        rank_to_phase.get(highest_china_phase) if highest_china_phase is not None else None
                    ),
                    latest_status_date=(
                        latest_status_date.replace(tzinfo=UTC)
                        if latest_status_date is not None and latest_status_date.tzinfo is None
                        else latest_status_date
                    ),
                ),
                target_names=sorted(target_names[entity_id], key=str.casefold),
                indication_names=sorted(indication_names[entity_id], key=str.casefold),
                organization_names=sorted(organization_names[entity_id], key=str.casefold),
                program_status_counts=dict(sorted(status_counts[entity_id].items())),
                as_of=as_of,
            )
        )
    return DrugComparisonResult(items=items, as_of=as_of)
