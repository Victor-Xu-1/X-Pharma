from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select, union_all

from pharma_intel.intelligence.company_timeline import company_timeline
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_filters import _deal_filters
from pharma_intel.intelligence.entity_dossier import entity_dossier
from pharma_intel.intelligence.vocabulary import _DEVELOPMENT_PHASE_RANK, _public_program_modality_sql
from pharma_intel.models import DealProfile, DevelopmentPhase, DevelopmentProgram, DevelopmentProgramTarget, EntityType
from pharma_intel.schemas import CompanyDossierResponse, CompanyDossierSummaryRead


def company_dossier(context: QueryContext, entity_id: str, limit: int = 100) -> CompanyDossierResponse | None:
    dossier = entity_dossier(context, entity_id, limit)
    if dossier is None or dossier.entity.entity_type != EntityType.ORGANIZATION:
        return None
    timeline = company_timeline(context, entity_id, limit, 0)
    if timeline is None:
        return None

    program_filters = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        DevelopmentProgram.organization_entity_id == entity_id,
    ]

    def phase_rank(column: Any) -> Any:
        return case(
            *((column == DevelopmentPhase(phase), rank) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()),
            else_=None,
        )

    program_count, drug_count, indication_count, highest_phase_rank = context.session.execute(
        select(
            func.count(DevelopmentProgram.id),
            func.count(func.distinct(DevelopmentProgram.drug_entity_id)),
            func.count(func.distinct(DevelopmentProgram.disease_entity_id)),
            func.max(phase_rank(DevelopmentProgram.phase)),
        ).where(*program_filters)
    ).one()
    phase_distribution = {
        phase.value if isinstance(phase, DevelopmentPhase) else str(phase): int(count)
        for phase, count in context.session.execute(
            select(DevelopmentProgram.phase, func.count(DevelopmentProgram.id))
            .where(*program_filters)
            .group_by(DevelopmentProgram.phase)
            .order_by(func.count(DevelopmentProgram.id).desc(), DevelopmentProgram.phase)
        ).all()
    }
    program_modality = _public_program_modality_sql(
        DevelopmentProgram.modality,
        DevelopmentProgram.drug_category,
    )
    modalities = [
        str(modality)
        for modality in context.session.scalars(
            select(program_modality)
            .where(*program_filters, program_modality.is_not(None))
            .distinct()
            .order_by(program_modality)
        ).all()
    ]

    current_targets = (
        select(DevelopmentProgramTarget.target_entity_id)
        .join(DevelopmentProgram, DevelopmentProgram.id == DevelopmentProgramTarget.program_id)
        .where(
            *program_filters,
            DevelopmentProgramTarget.tenant_id == context.tenant_id,
            DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
        )
    )
    legacy_targets = select(DevelopmentProgram.target_entity_id).where(
        *program_filters,
        DevelopmentProgram.target_entity_id.is_not(None),
    )
    target_source = union_all(current_targets, legacy_targets).subquery()
    target_count = context.session.scalar(select(func.count(func.distinct(target_source.c.target_entity_id)))) or 0
    deal_count = (
        context.session.scalar(select(func.count(DealProfile.id)).where(*_deal_filters(context, entity_id))) or 0
    )

    rank_to_phase = {rank: DevelopmentPhase(phase) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()}
    latest_activity_at = timeline.items[0].occurred_at if timeline.items else None
    return CompanyDossierResponse(
        **dossier.model_dump(),
        summary=CompanyDossierSummaryRead(
            program_count=int(program_count or 0),
            drug_count=int(drug_count or 0),
            target_count=int(target_count),
            indication_count=int(indication_count or 0),
            deal_count=int(deal_count),
            timeline_event_count=timeline.total,
            modalities=modalities,
            phase_distribution=phase_distribution,
            highest_phase=rank_to_phase.get(highest_phase_rank),
            latest_activity_at=latest_activity_at,
        ),
        timeline=timeline,
    )
