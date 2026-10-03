from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy import case, func, select, union_all

from pharma_intel.intelligence.clinical_filters import _clinical_trial_filters
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.entity_dossier import entity_dossier
from pharma_intel.intelligence.epidemiology import _epidemiology_filters, search_epidemiology_observations
from pharma_intel.intelligence.patents import _patent_filters
from pharma_intel.intelligence.scope import _count
from pharma_intel.intelligence.vocabulary import _DEVELOPMENT_PHASE_RANK, _public_program_modality_sql
from pharma_intel.models import (
    ClinicalTrialProfile,
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramTarget,
    EntityType,
    EpidemiologyObservation,
    PatentFamily,
)
from pharma_intel.schemas import DiseaseDossierResponse, DiseaseDossierSummaryRead


def disease_dossier(context: QueryContext, entity_id: str, limit: int = 100) -> DiseaseDossierResponse | None:
    dossier = entity_dossier(context, entity_id, limit)
    if dossier is None or dossier.entity.entity_type != EntityType.DISEASE:
        return None

    program_filters = [
        DevelopmentProgram.tenant_id == context.tenant_id,
        DevelopmentProgram.disease_entity_id == entity_id,
    ]

    def phase_rank(column: Any) -> Any:
        return case(
            *((column == DevelopmentPhase(phase), rank) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()),
            else_=None,
        )

    (
        program_count,
        drug_count,
        organization_count,
        highest_phase_rank,
        latest_program_at,
    ) = context.session.execute(
        select(
            func.count(DevelopmentProgram.id),
            func.count(func.distinct(DevelopmentProgram.drug_entity_id)),
            func.count(func.distinct(DevelopmentProgram.organization_entity_id)),
            func.max(phase_rank(DevelopmentProgram.phase)),
            func.max(DevelopmentProgram.status_date),
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

    epidemiology = search_epidemiology_observations(
        context,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        limit,
        0,
        disease_entity_id=entity_id,
    )
    latest_epidemiology_at = context.session.scalar(
        select(func.max(EpidemiologyObservation.period_end)).where(
            *_epidemiology_filters(context, entity_id, None, None, None, None, None, None, None, None, None, None)
        )
    )
    latest_candidates = [value for value in (latest_program_at, latest_epidemiology_at) if value is not None]
    normalized_candidates = [
        value.replace(tzinfo=UTC) if value.tzinfo is None else value for value in latest_candidates
    ]
    rank_to_phase = {rank: DevelopmentPhase(phase) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()}
    return DiseaseDossierResponse(
        **dossier.model_dump(),
        summary=DiseaseDossierSummaryRead(
            program_count=int(program_count or 0),
            drug_count=int(drug_count or 0),
            target_count=int(target_count),
            organization_count=int(organization_count or 0),
            clinical_trial_count=_count(
                context,
                ClinicalTrialProfile,
                _clinical_trial_filters(context, entity_id, None),
            ),
            patent_count=_count(context, PatentFamily, _patent_filters(context, entity_id, None)),
            epidemiology_observation_count=epidemiology.total,
            patient_population_count=len(epidemiology.patient_populations),
            modalities=modalities,
            phase_distribution=phase_distribution,
            highest_phase=rank_to_phase.get(highest_phase_rank),
            measures=sorted(epidemiology.facets.get("measure", {})),
            geographies=sorted(epidemiology.facets.get("geography", {})),
            latest_activity_at=max(normalized_candidates) if normalized_candidates else None,
        ),
        epidemiology=epidemiology,
    )
