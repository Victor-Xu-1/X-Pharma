from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select, true

from pharma_intel.intelligence.clinical_filters import _clinical_trial_filters
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.entity_dossier import entity_dossier
from pharma_intel.intelligence.patents import _patent_filters
from pharma_intel.intelligence.pipeline_filters import _program_filters
from pharma_intel.intelligence.regulatory import _regulatory_filters
from pharma_intel.intelligence.structures import structures_for_target
from pharma_intel.intelligence.vocabulary import (
    _ACTIVE_PATENT_STATUSES,
    _APPROVAL_REGULATORY_EVENT_TYPES,
    _DEVELOPMENT_PHASE_RANK,
    _INACTIVE_PATENT_STATUSES,
    _NON_RECRUITING_TRIAL_STATUSES,
    _RECRUITING_TRIAL_STATUSES,
    TARGET_STATUS_VOCABULARY_VERSION,
    normalize_status_token,
)
from pharma_intel.models import (
    ActivityMeasurement,
    ClinicalTrialProfile,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    PatentFamily,
    RegulatoryEvent,
    ReviewStatus,
    TargetEvidenceObservation,
    TargetProfile,
)
from pharma_intel.schemas import EntityRead, TargetDossierResponse, TargetDossierSummaryRead, TargetProfileResponse


def target_profile(context: QueryContext, entity_id: str) -> TargetProfileResponse | None:
    entity = context.session.scalar(
        select(Entity).where(
            Entity.id == entity_id,
            Entity.tenant_id == context.tenant_id,
            Entity.review_status == ReviewStatus.VERIFIED if not context.include_unpublished else true(),
        )
    )
    if entity is None or entity.entity_type != EntityType.TARGET:
        return None
    profile = context.session.scalar(
        select(TargetProfile).where(TargetProfile.entity_id == entity_id, TargetProfile.tenant_id == context.tenant_id)
    )
    if profile is None and entity.external_ids:
        # Ingestion can briefly leave a verified target row and a second row with
        # the governed profile before entity reconciliation creates a canonical
        # link. Only reuse a profile when a tenant-scoped, target-scoped external
        # identifier matches exactly; same-name matching would merge unrelated
        # biological targets.
        profile_candidates = context.session.execute(
            select(Entity, TargetProfile)
            .join(TargetProfile, TargetProfile.entity_id == Entity.id)
            .where(
                Entity.tenant_id == context.tenant_id,
                Entity.entity_type == EntityType.TARGET,
                Entity.id != entity.id,
                TargetProfile.tenant_id == context.tenant_id,
            )
        ).all()

        def shares_external_identifier(candidate: Entity) -> bool:
            candidate_ids = {
                (str(namespace).casefold().strip(), str(value).casefold().strip())
                for namespace, value in candidate.external_ids.items()
                if str(namespace).strip() and str(value).strip()
            }
            return any(
                (str(namespace).casefold().strip(), str(value).casefold().strip()) in candidate_ids
                for namespace, value in entity.external_ids.items()
                if str(namespace).strip() and str(value).strip()
            )

        matching_profiles = [
            (candidate, candidate_profile)
            for candidate, candidate_profile in profile_candidates
            if shares_external_identifier(candidate)
        ]
        if matching_profiles:
            profile = max(
                matching_profiles,
                key=lambda item: (
                    sum(
                        bool(getattr(item[1], field))
                        for field in (
                            "gene_symbol",
                            "uniprot_accession",
                            "organism",
                            "target_class",
                            "sequence",
                            "function_summary",
                        )
                    ),
                    int(item[0].review_status == ReviewStatus.VERIFIED),
                    str(item[1].updated_at or ""),
                    str(item[1].id),
                ),
            )[1]
    activity_count = (
        context.session.scalar(
            select(func.count(ActivityMeasurement.id)).where(
                ActivityMeasurement.tenant_id == context.tenant_id,
                ActivityMeasurement.target_entity_id == entity_id,
            )
        )
        or 0
    )
    program_count = (
        context.session.scalar(select(func.count(DevelopmentProgram.id)).where(*_program_filters(context, entity_id)))
        or 0
    )
    target_evidence_count = (
        context.session.scalar(
            select(func.count(TargetEvidenceObservation.id)).where(
                TargetEvidenceObservation.tenant_id == context.tenant_id,
                TargetEvidenceObservation.target_entity_id == entity_id,
            )
        )
        or 0
    )
    return TargetProfileResponse(
        profile_id=profile.id if profile else None,
        entity=EntityRead.model_validate(entity),
        gene_symbol=profile.gene_symbol if profile else None,
        uniprot_accession=profile.uniprot_accession if profile else None,
        organism=profile.organism if profile else None,
        target_class=profile.target_class if profile else None,
        sequence=profile.sequence if profile else None,
        function_summary=profile.function_summary if profile else None,
        activity_count=activity_count,
        program_count=program_count,
        target_evidence_count=target_evidence_count,
        source_document_id=profile.source_document_id if profile else None,
        as_of=datetime.now(UTC),
    )


def target_dossier(context: QueryContext, entity_id: str, limit: int = 50) -> TargetDossierResponse | None:
    profile = target_profile(context, entity_id)
    if profile is None:
        return None
    dossier = entity_dossier(context, entity_id, limit)
    if dossier is None:
        return None
    return TargetDossierResponse(
        **dossier.model_dump(exclude={"structures"}),
        profile=profile.model_copy(update={"as_of": dossier.as_of}),
        structures=structures_for_target(context, entity_id, limit),
        summary=_target_dossier_summary(context, entity_id),
    )


def _target_dossier_summary(context: QueryContext, entity_id: str) -> TargetDossierSummaryRead:
    """Aggregate the target landscape over the complete authorized result set.

    Every count here is computed by the database across all matching records, not
    from the bounded record collections the dossier returns for display.
    """

    program_filters = _program_filters(context, entity_id)

    def phase_rank(column: Any) -> Any:
        return case(
            *((column == DevelopmentPhase(phase), rank) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()),
            else_=None,
        )

    program_count, highest_phase_rank = context.session.execute(
        select(
            func.count(DevelopmentProgram.id),
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
    rank_to_phase = {rank: DevelopmentPhase(phase) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()}

    trial_total, recruiting_trials, unclassified_trials = _classified_status_counts(
        context,
        select(ClinicalTrialProfile.overall_status, func.count(ClinicalTrialProfile.id))
        .where(*_clinical_trial_filters(context, entity_id, None))
        .group_by(ClinicalTrialProfile.overall_status),
        matching=_RECRUITING_TRIAL_STATUSES,
        known=_NON_RECRUITING_TRIAL_STATUSES,
    )
    patent_total, active_patents, unclassified_patents = _classified_status_counts(
        context,
        select(PatentFamily.legal_status, func.count(PatentFamily.id))
        .where(*_patent_filters(context, entity_id, None))
        .group_by(PatentFamily.legal_status),
        matching=_ACTIVE_PATENT_STATUSES,
        known=_INACTIVE_PATENT_STATUSES,
    )

    regulatory_total = 0
    approval_events = 0
    for event_type, count in context.session.execute(
        select(RegulatoryEvent.event_type, func.count(RegulatoryEvent.id))
        .where(*_regulatory_filters(context, entity_id, None, None))
        .group_by(RegulatoryEvent.event_type)
    ).all():
        bucket = int(count or 0)
        regulatory_total += bucket
        if str(event_type) in _APPROVAL_REGULATORY_EVENT_TYPES:
            approval_events += bucket

    return TargetDossierSummaryRead(
        program_count=int(program_count or 0),
        phase_distribution=phase_distribution,
        highest_phase=rank_to_phase.get(highest_phase_rank),
        clinical_trial_count=trial_total,
        recruiting_trial_count=recruiting_trials,
        unclassified_trial_status_count=unclassified_trials,
        patent_count=patent_total,
        active_patent_count=active_patents,
        unclassified_patent_status_count=unclassified_patents,
        regulatory_event_count=regulatory_total,
        approval_event_count=approval_events,
        status_vocabulary_version=TARGET_STATUS_VOCABULARY_VERSION,
    )


def _classified_status_counts(
    context: QueryContext,
    statement: Any,
    *,
    matching: frozenset[str],
    known: frozenset[str],
) -> tuple[int, int, int]:
    """Return (total, matching, unclassified) for a grouped free-text status query.

    A status is only counted as matching when its normalized token is an exact
    member of the vocabulary. Tokens in neither vocabulary are reported as
    unclassified so the gap stays visible instead of being silently bucketed.
    """

    total = 0
    matched = 0
    unclassified = 0
    for value, count in context.session.execute(statement).all():
        bucket = int(count or 0)
        total += bucket
        token = normalize_status_token(value)
        if token in matching:
            matched += bucket
        elif token not in known:
            unclassified += bucket
    return total, matched, unclassified
