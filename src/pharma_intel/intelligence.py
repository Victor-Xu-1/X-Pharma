from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time
from typing import Any, Literal

from sqlalchemy import DateTime, String, and_, case, cast, func, literal, or_, select, true, union, union_all
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql import Select
from sqlalchemy.sql.elements import ColumnElement

from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    CompoundStructure,
    DealAssetAssociation,
    DealPartyAssociation,
    DealProfile,
    DealRight,
    DevelopmentPhase,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityCanonicalLink,
    EntityIdentifier,
    EntityType,
    EpidemiologyObservation,
    EvidenceClaim,
    MeasurementRelation,
    NewsEvent,
    PatentFamily,
    PatientPopulation,
    PatientPopulationEntityLink,
    ProgramTargetRole,
    RegulatoryEvent,
    Relationship,
    ReviewStatus,
    TargetEvidenceObservation,
    TargetProfile,
    TrialResultDisclosureType,
    TrialResultEvaluation,
)
from pharma_intel.program_semantics import (
    MECHANISM_ACTION_TYPES,
    MISSING_PROGRAM_VALUES,
    PROGRAM_DRUG_CATEGORY_BY_MODALITY,
    public_program_drug_category,
    public_program_modality,
    public_program_tags,
)
from pharma_intel.schemas import (
    CLINICAL_TRIAL_SORT_FIELDS,
    DEAL_SORT_FIELDS,
    EPIDEMIOLOGY_SORT_FIELDS,
    NEWS_SORT_FIELDS,
    PATENT_SORT_FIELDS,
    PIPELINE_SORT_FIELDS,
    REGULATORY_SORT_FIELDS,
    AppliedFilterRead,
    BioactivityRead,
    ClinicalTrialDetailRead,
    ClinicalTrialEntityRoleRead,
    ClinicalTrialLandscapeMatrixRowRead,
    ClinicalTrialLandscapeRead,
    ClinicalTrialLinkedEntityRead,
    ClinicalTrialRead,
    ClinicalTrialResultDisclosureRead,
    ClinicalTrialSavedSearchQuery,
    ClinicalTrialSearchItemRead,
    ClinicalTrialSearchResult,
    ClinicalTrialSortField,
    CompanyDossierResponse,
    CompanyDossierSummaryRead,
    CompanyTimelineEventRead,
    CompanyTimelineResult,
    CompetitiveProgramRead,
    CompoundStructureRead,
    DealAnalysisLimit,
    DealAssetAssociationRead,
    DealLandscapeBucketRead,
    DealLandscapeRead,
    DealLinkedEntityRead,
    DealPartyAssociationRead,
    DealRead,
    DealRightRead,
    DealSavedSearchQuery,
    DealSearchItemRead,
    DealSearchResult,
    DealSortField,
    DiseaseDossierResponse,
    DiseaseDossierSummaryRead,
    DrugComparisonProfileRead,
    DrugComparisonResult,
    DrugDossierResponse,
    DrugDossierSummaryRead,
    DrugProgramSearchResult,
    EntityDossierCoverageRead,
    EntityDossierDomain,
    EntityDossierResponse,
    EntityRead,
    EntityRelationshipRead,
    EpidemiologyLandscapeBucketRead,
    EpidemiologyLandscapeRead,
    EpidemiologyLinkedEntityRead,
    EpidemiologyObservationRead,
    EpidemiologyObservationSearchItemRead,
    EpidemiologyObservationSearchResult,
    EpidemiologySavedSearchQuery,
    EpidemiologySortField,
    EpidemiologyTrendResult,
    NewsEventLinkedEntityRead,
    NewsEventRead,
    NewsEventSearchItemRead,
    NewsEventSearchResult,
    NewsLandscapeBucketRead,
    NewsLandscapeRead,
    NewsSavedSearchQuery,
    NewsSortField,
    PatentFamilyLinkedEntityRead,
    PatentFamilyRead,
    PatentFamilySearchItemRead,
    PatentFamilySearchResult,
    PatentLandscapeBucketRead,
    PatentLandscapeRead,
    PatentSavedSearchQuery,
    PatentSortField,
    PatientPopulationOptionRead,
    PatientPopulationRead,
    PipelineLandscapeBucketRead,
    PipelineLandscapeRead,
    PipelineLandscapeStageScope,
    PipelineResultGrain,
    PipelineSavedSearchQuery,
    PipelineSearchResult,
    PipelineSortField,
    PipelineTargetAggregation,
    ProgramIndicationRead,
    ProgramOrganizationRead,
    ProgramTargetRead,
    RegulatoryEventLinkedEntityRead,
    RegulatoryEventRead,
    RegulatoryEventSearchItemRead,
    RegulatoryEventSearchResult,
    RegulatoryLandscapeBucketRead,
    RegulatoryLandscapeRead,
    RegulatorySavedSearchQuery,
    RegulatorySortField,
    SarActivityRead,
    SarComparisonResult,
    SortCriterionRead,
    SortDirection,
    TargetDossierResponse,
    TargetDossierSummaryRead,
    TargetEvidenceRead,
    TargetProfileResponse,
)
from pharma_intel.sorting import SortClause, validate_sort_clauses

_DEVELOPMENT_PHASE_RANK = {
    "discontinued": -1,
    "discovery": 0,
    "preclinical": 1,
    "ind": 2,
    "phase_1": 3,
    "phase_1_2": 4,
    "phase_2": 5,
    "phase_2_3": 6,
    "phase_3": 7,
    "filed": 8,
    "approved": 9,
}

_MISSING_ENTITY_LABELS = frozenset(
    {"-", "--", "n/a", "na", "none", "null", "not available", "unknown", "未披露", "暂无"}
)


def _is_meaningful_entity_label(value: str | None) -> bool:
    return value is not None and " ".join(value.casefold().split()) not in _MISSING_ENTITY_LABELS


def _meaningful_entity_name_sql(column: Any) -> ColumnElement[bool]:
    return and_(
        column.is_not(None),
        func.lower(func.trim(column)).not_in(tuple(sorted(_MISSING_ENTITY_LABELS))),
    )


def _program_action_type_sql(modality: Any) -> ColumnElement[bool]:
    normalized = func.upper(func.trim(func.replace(func.replace(modality, "_", " "), "-", " ")))
    return normalized.in_(tuple(sorted(MECHANISM_ACTION_TYPES)))


def _public_program_modality_sql(modality: Any, drug_category: Any) -> Any:
    cleaned_modality = func.nullif(func.trim(modality), "")
    cleaned_category = func.nullif(func.trim(drug_category), "")
    category_key = func.lower(cleaned_category)
    return case(
        (
            _program_action_type_sql(modality),
            case(
                (category_key.in_(tuple(sorted(MISSING_PROGRAM_VALUES))), None),
                else_=cleaned_category,
            ),
        ),
        else_=cleaned_modality,
    )


def _public_program_drug_category_sql(modality: Any, drug_category: Any) -> Any:
    cleaned_category = func.nullif(func.trim(drug_category), "")
    category_key = func.lower(cleaned_category)
    mapped_category = case(
        *((category_key == key, value) for key, value in sorted(PROGRAM_DRUG_CATEGORY_BY_MODALITY.items())),
        else_=None,
    )
    return case(
        (_program_action_type_sql(modality), mapped_category),
        (category_key.in_(tuple(sorted(MISSING_PROGRAM_VALUES))), None),
        else_=cleaned_category,
    )


def _ordered_sort_expressions[SortField: str](
    clauses: Sequence[SortClause[SortField]],
    expressions: Mapping[SortField, Any],
) -> list[Any]:
    return [
        expressions[clause.field].asc().nullslast()
        if clause.direction == "asc"
        else expressions[clause.field].desc().nullslast()
        for clause in clauses
    ]


def _sort_criteria_read[SortField: str](
    clauses: Sequence[SortClause[SortField]],
) -> list[SortCriterionRead]:
    return [SortCriterionRead(field=clause.field, direction=clause.direction) for clause in clauses]


# Versioned server-side vocabulary for classifying ungoverned free-text source statuses.
# `clinical_trial_profiles.overall_status` and `patent_families.legal_status` are plain
# text columns, so classification must be explicit, exact and auditable. Matching is done
# on a normalized token, never on substring containment: substring matching would count
# "inactive" as active and "not yet recruiting" as recruiting.
TARGET_STATUS_VOCABULARY_VERSION = "target-dossier-status@1"
_RECRUITING_TRIAL_STATUSES = frozenset(
    {
        "recruiting",
        "enrolling by invitation",
        "active recruiting",
    }
)
_NON_RECRUITING_TRIAL_STATUSES = frozenset(
    {
        "not yet recruiting",
        "active not recruiting",
        "completed",
        "terminated",
        "withdrawn",
        "suspended",
        "no longer available",
        "temporarily not available",
        "approved for marketing",
        "unknown status",
        "unknown",
    }
)
_ACTIVE_PATENT_STATUSES = frozenset(
    {
        "active",
        "granted",
        "in force",
        "issued",
    }
)
_INACTIVE_PATENT_STATUSES = frozenset(
    {
        "inactive",
        "expired",
        "lapsed",
        "abandoned",
        "revoked",
        "rejected",
        "withdrawn",
        "pending",
        "not in force",
    }
)
_APPROVAL_REGULATORY_EVENT_TYPES = frozenset({"approval", "conditional_approval"})


def _saved_date_start(value: Any) -> datetime | None:
    """Convert a saved-contract date to the inclusive UTC start of that day."""
    return datetime.combine(value, time.min, tzinfo=UTC) if value else None


def _saved_date_end(value: Any) -> datetime | None:
    """Convert a saved-contract date to the inclusive UTC end of that day."""
    return datetime.combine(value, time.max, tzinfo=UTC) if value else None


def normalize_status_token(value: str | None) -> str:
    """Fold an ungoverned source status into a comparable token.

    Lowercases, replaces separator punctuation with spaces and collapses whitespace so
    that "Active, not recruiting", "ACTIVE_NOT_RECRUITING" and "active not recruiting"
    all resolve to the same token.
    """

    if value is None:
        return ""
    folded = value.strip().lower()
    for separator in ("_", "-", ",", "/", ";"):
        folded = folded.replace(separator, " ")
    return " ".join(folded.split())


RESEARCH_PUBLICATION_EVENT_TYPES = ("publication", "conference_abstract", "poster", "presentation")
_TRIAL_DRUG_ROLES = ("investigational_drug", "combination_drug")
_TRIAL_RESULT_EVALUATION_ORDER = (
    TrialResultEvaluation.SUPERIOR,
    TrialResultEvaluation.POSITIVE,
    TrialResultEvaluation.NON_INFERIOR,
    TrialResultEvaluation.SIMILAR,
    TrialResultEvaluation.NOT_SUPERIOR,
    TrialResultEvaluation.UNFAVORABLE,
    TrialResultEvaluation.TERMINATED,
)


class IntelligenceService:
    def __init__(self, session: Session, tenant_id: str, *, include_unpublished: bool = True) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.include_unpublished = include_unpublished
        self._placeholder_target_ids_cache: tuple[str, ...] | None = None

    def _placeholder_target_ids(self) -> tuple[str, ...]:
        if self._placeholder_target_ids_cache is None:
            self._placeholder_target_ids_cache = tuple(
                self.session.scalars(
                    select(Entity.id).where(
                        Entity.tenant_id == self.tenant_id,
                        Entity.entity_type == EntityType.TARGET,
                        func.lower(func.trim(Entity.name)).in_(tuple(sorted(_MISSING_ENTITY_LABELS))),
                    )
                )
            )
        return self._placeholder_target_ids_cache

    def _clean_target_combination_expression(self, expression: Any) -> Any:
        cleaned = expression
        for target_id in self._placeholder_target_ids():
            cleaned = func.replace(
                func.replace(func.replace(cleaned, f"{target_id}|", ""), f"|{target_id}", ""), target_id, ""
            )
        return func.nullif(cleaned, "")

    def _published_entity_exists(self, entity_id: Any) -> ColumnElement[bool]:
        """Return the public entity boundary for a linked domain identifier."""

        if self.include_unpublished:
            return true()
        published_entity = aliased(Entity)
        return (
            select(literal(1))
            .select_from(published_entity)
            .where(
                published_entity.tenant_id == self.tenant_id,
                published_entity.id == entity_id,
                published_entity.review_status == ReviewStatus.VERIFIED,
            )
            .correlate_except(published_entity)
            .exists()
        )

    def _published_optional_entity(self, entity_id: Any) -> ColumnElement[bool]:
        if self.include_unpublished:
            return true()
        return or_(entity_id.is_(None), self._published_entity_exists(entity_id))

    def _entity_identity_ids(self, entity_id: str, entity_type: EntityType) -> Select[Any]:
        """Return the tenant-scoped identity family for one governed entity.

        Imports can create a verified canonical row and a same-name draft row before
        entity resolution finishes. Domain records linked to either row must remain
        discoverable from the verified identity, while the type and tenant boundaries
        prevent accidental cross-domain or cross-tenant matches.
        """

        source = Entity.__table__.alias()
        family = Entity.__table__.alias()
        normalized_name = (
            select(source.c.normalized_name)
            .where(
                source.c.tenant_id == self.tenant_id,
                source.c.id == entity_id,
                source.c.entity_type == entity_type,
            )
            .scalar_subquery()
        )
        return select(family.c.id).where(
            family.c.tenant_id == self.tenant_id,
            family.c.entity_type == entity_type,
            family.c.normalized_name == normalized_name,
        )

    def _entity_identity_member_ids(self, entity_id: str, entity_type: EntityType) -> set[str]:
        """Materialize one bounded identity family for aggregate read models.

        The SQL identity expression is preferable for large scans. Bounded comparison
        requests also need a Python mapping from every raw row back to its requested
        entity, so this helper expands the same normalized-name family and active
        canonical links without widening the tenant or entity-type boundary.
        """

        normalized_name = self.session.scalar(
            select(Entity.normalized_name).where(
                Entity.tenant_id == self.tenant_id,
                Entity.id == entity_id,
                Entity.entity_type == entity_type,
            )
        )
        if normalized_name is None:
            return {entity_id}
        members = set(
            self.session.scalars(
                select(Entity.id).where(
                    Entity.tenant_id == self.tenant_id,
                    Entity.entity_type == entity_type,
                    Entity.normalized_name == normalized_name,
                )
            )
        )
        changed = True
        while changed:
            changed = False
            link_rows = self.session.execute(
                select(EntityCanonicalLink.alias_entity_id, EntityCanonicalLink.canonical_entity_id).where(
                    EntityCanonicalLink.tenant_id == self.tenant_id,
                    EntityCanonicalLink.active.is_(True),
                    or_(
                        EntityCanonicalLink.alias_entity_id.in_(members),
                        EntityCanonicalLink.canonical_entity_id.in_(members),
                    ),
                )
            ).all()
            for alias_id, canonical_id in link_rows:
                if alias_id not in members:
                    members.add(alias_id)
                    changed = True
                if canonical_id not in members:
                    members.add(canonical_id)
                    changed = True
        return members

    def _published_identity_exists(
        self,
        entity_id: Any,
        entity_type: EntityType,
        *,
        correlate_from: Any | None = None,
    ) -> ColumnElement[bool]:
        """Check visibility through any verified member of an identity family."""

        if self.include_unpublished:
            return true()
        source = Entity.__table__.alias()
        family = Entity.__table__.alias()
        normalized_name_query = select(source.c.normalized_name).where(
            source.c.tenant_id == self.tenant_id,
            source.c.id == entity_id,
            source.c.entity_type == entity_type,
        )
        if correlate_from is not None:
            normalized_name_query = normalized_name_query.correlate(correlate_from)
        normalized_name = normalized_name_query.scalar_subquery()
        return (
            select(literal(1))
            .select_from(family)
            .where(
                family.c.tenant_id == self.tenant_id,
                family.c.entity_type == entity_type,
                family.c.normalized_name == normalized_name,
                family.c.review_status == ReviewStatus.VERIFIED,
            )
            .correlate_except(source, family)
            .exists()
        )

    def _published_optional_identity_entity(
        self,
        entity_id: Any,
        entity_type: EntityType,
        *,
        correlate_from: Any | None = None,
    ) -> ColumnElement[bool]:
        if self.include_unpublished:
            return true()
        return or_(
            entity_id.is_(None),
            self._published_identity_exists(entity_id, entity_type, correlate_from=correlate_from),
        )

    @staticmethod
    def _applied_filters(
        *filters: tuple[
            str,
            Literal["contains", "eq", "in", "gte", "lte"],
            str | bool | int | float | list[str] | None,
        ],
    ) -> list[AppliedFilterRead]:
        applied: list[AppliedFilterRead] = []
        for field, operator, value in filters:
            if isinstance(value, str):
                normalized: str | bool | int | float | list[str] | None = value.strip()
            elif isinstance(value, list):
                normalized = list(dict.fromkeys(item.strip() for item in value if item.strip()))
            else:
                normalized = value
            if normalized is None or normalized == "" or normalized == []:
                continue
            applied.append(AppliedFilterRead(field=field, operator=operator, value=normalized))
        return applied

    def target_profile(self, entity_id: str) -> TargetProfileResponse | None:
        entity = self.session.scalar(
            select(Entity).where(
                Entity.id == entity_id,
                Entity.tenant_id == self.tenant_id,
                Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
            )
        )
        if entity is None or entity.entity_type != EntityType.TARGET:
            return None
        profile = self.session.scalar(
            select(TargetProfile).where(TargetProfile.entity_id == entity_id, TargetProfile.tenant_id == self.tenant_id)
        )
        if profile is None and entity.external_ids:
            # Ingestion can briefly leave a verified target row and a second row with
            # the governed profile before entity reconciliation creates a canonical
            # link. Only reuse a profile when a tenant-scoped, target-scoped external
            # identifier matches exactly; same-name matching would merge unrelated
            # biological targets.
            profile_candidates = self.session.execute(
                select(Entity, TargetProfile)
                .join(TargetProfile, TargetProfile.entity_id == Entity.id)
                .where(
                    Entity.tenant_id == self.tenant_id,
                    Entity.entity_type == EntityType.TARGET,
                    Entity.id != entity.id,
                    TargetProfile.tenant_id == self.tenant_id,
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
            self.session.scalar(
                select(func.count(ActivityMeasurement.id)).where(
                    ActivityMeasurement.tenant_id == self.tenant_id,
                    ActivityMeasurement.target_entity_id == entity_id,
                )
            )
            or 0
        )
        program_count = (
            self.session.scalar(select(func.count(DevelopmentProgram.id)).where(*self._program_filters(entity_id))) or 0
        )
        target_evidence_count = (
            self.session.scalar(
                select(func.count(TargetEvidenceObservation.id)).where(
                    TargetEvidenceObservation.tenant_id == self.tenant_id,
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

    def target_dossier(self, entity_id: str, limit: int = 50) -> TargetDossierResponse | None:
        profile = self.target_profile(entity_id)
        if profile is None:
            return None
        dossier = self.entity_dossier(entity_id, limit)
        if dossier is None:
            return None
        return TargetDossierResponse(
            **dossier.model_dump(exclude={"structures"}),
            profile=profile.model_copy(update={"as_of": dossier.as_of}),
            structures=self.structures_for_target(entity_id, limit),
            summary=self._target_dossier_summary(entity_id),
        )

    def _target_dossier_summary(self, entity_id: str) -> TargetDossierSummaryRead:
        """Aggregate the target landscape over the complete authorized result set.

        Every count here is computed by the database across all matching records, not
        from the bounded record collections the dossier returns for display.
        """

        program_filters = self._program_filters(entity_id)

        def phase_rank(column: Any) -> Any:
            return case(
                *((column == DevelopmentPhase(phase), rank) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()),
                else_=None,
            )

        program_count, highest_phase_rank = self.session.execute(
            select(
                func.count(DevelopmentProgram.id),
                func.max(phase_rank(DevelopmentProgram.phase)),
            ).where(*program_filters)
        ).one()
        phase_distribution = {
            phase.value if isinstance(phase, DevelopmentPhase) else str(phase): int(count)
            for phase, count in self.session.execute(
                select(DevelopmentProgram.phase, func.count(DevelopmentProgram.id))
                .where(*program_filters)
                .group_by(DevelopmentProgram.phase)
                .order_by(func.count(DevelopmentProgram.id).desc(), DevelopmentProgram.phase)
            ).all()
        }
        rank_to_phase = {rank: DevelopmentPhase(phase) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()}

        trial_total, recruiting_trials, unclassified_trials = self._classified_status_counts(
            select(ClinicalTrialProfile.overall_status, func.count(ClinicalTrialProfile.id))
            .where(*self._clinical_trial_filters(entity_id, None))
            .group_by(ClinicalTrialProfile.overall_status),
            matching=_RECRUITING_TRIAL_STATUSES,
            known=_NON_RECRUITING_TRIAL_STATUSES,
        )
        patent_total, active_patents, unclassified_patents = self._classified_status_counts(
            select(PatentFamily.legal_status, func.count(PatentFamily.id))
            .where(*self._patent_filters(entity_id, None))
            .group_by(PatentFamily.legal_status),
            matching=_ACTIVE_PATENT_STATUSES,
            known=_INACTIVE_PATENT_STATUSES,
        )

        regulatory_total = 0
        approval_events = 0
        for event_type, count in self.session.execute(
            select(RegulatoryEvent.event_type, func.count(RegulatoryEvent.id))
            .where(*self._regulatory_filters(entity_id, None, None))
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
        self,
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
        for value, count in self.session.execute(statement).all():
            bucket = int(count or 0)
            total += bucket
            token = normalize_status_token(value)
            if token in matching:
                matched += bucket
            elif token not in known:
                unclassified += bucket
        return total, matched, unclassified

    def drug_dossier(self, entity_id: str, limit: int = 100) -> DrugDossierResponse | None:
        dossier = self.entity_dossier(entity_id, limit)
        if dossier is None or dossier.entity.entity_type != EntityType.DRUG:
            return None

        program_filters = [
            DevelopmentProgram.tenant_id == self.tenant_id,
            self._unique_program_record(),
            DevelopmentProgram.drug_entity_id.in_(self._entity_identity_ids(entity_id, EntityType.DRUG)),
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
        ) = self.session.execute(
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
        target_count = int(self.session.scalar(select(func.count(func.distinct(target_ids.c.target_entity_id)))) or 0)
        program_modality = _public_program_modality_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        modalities = list(
            self.session.scalars(
                select(program_modality)
                .where(*program_filters, program_modality.is_not(None))
                .distinct()
                .order_by(program_modality)
                .limit(50)
            )
        )

        rank_to_phase = {rank: DevelopmentPhase(phase) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()}
        deal_items = self._deal_search_items(self._deal_filters(entity_id), limit, 0)
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

    def drug_programs(self, entity_id: str, limit: int, offset: int = 0) -> DrugProgramSearchResult | None:
        """Return the complete drug portfolio through a bounded page."""

        entity = self.session.scalar(
            select(Entity).where(
                Entity.tenant_id == self.tenant_id,
                Entity.id == entity_id,
                Entity.entity_type == EntityType.DRUG,
            )
        )
        if entity is None:
            return None

        filters = self._program_filters(entity_id)
        return DrugProgramSearchResult(
            query_schema_version="pharma.drug.programs.v1",
            items=self._read_programs(filters, limit, offset),
            total=self._count(DevelopmentProgram, filters),
            limit=limit,
            offset=offset,
            as_of=datetime.now(UTC),
        )

    def drug_comparison_profiles(self, entity_ids: Sequence[str]) -> DrugComparisonResult:
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
            entity_id: self._entity_identity_member_ids(entity_id, EntityType.DRUG) for entity_id in ordered_ids
        }
        raw_to_requested: dict[str, str] = {}
        for requested_drug_id, raw_ids in raw_ids_by_requested.items():
            for raw_id in raw_ids:
                raw_to_requested.setdefault(raw_id, requested_drug_id)
        raw_entity_ids = set(raw_to_requested)

        entity_filters: list[ColumnElement[bool]] = [
            Entity.tenant_id == self.tenant_id,
            Entity.entity_type == EntityType.DRUG,
            Entity.id.in_(ordered_ids),
        ]
        if not self.include_unpublished:
            entity_filters.append(Entity.review_status == ReviewStatus.VERIFIED)
        entities = list(self.session.scalars(select(Entity).where(*entity_filters)))
        entities_by_id = {entity.id: entity for entity in entities}

        program_filters: list[ColumnElement[bool]] = [
            DevelopmentProgram.tenant_id == self.tenant_id,
            DevelopmentProgram.drug_entity_id.in_(raw_entity_ids),
        ]
        if not self.include_unpublished:
            program_filters.extend(
                [
                    self._published_identity_exists(
                        DevelopmentProgram.drug_entity_id,
                        EntityType.DRUG,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.target_entity_id,
                        EntityType.TARGET,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.disease_entity_id,
                        EntityType.DISEASE,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
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

        summary_rows = self.session.execute(
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
        if not self.include_unpublished:
            current_target_filters.append(
                self._published_identity_exists(
                    DevelopmentProgramTarget.target_entity_id,
                    EntityType.TARGET,
                    correlate_from=DevelopmentProgramTarget.__table__,
                )
            )
        current_targets = self.session.execute(
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
        legacy_targets = self.session.execute(
            select(DevelopmentProgram.drug_entity_id, DevelopmentProgram.target_entity_id).where(
                *program_filters,
                DevelopmentProgram.target_entity_id.is_not(None),
            )
        ).all()
        target_rows = [(drug_id, target_id) for drug_id, target_id in current_targets] + [
            (drug_id, target_id) for drug_id, target_id in legacy_targets if target_id is not None
        ]
        target_identities = self._canonical_entity_identity_labels(
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

        disease_rows = self.session.execute(
            select(DevelopmentProgram.drug_entity_id, DevelopmentProgram.disease_entity_id).where(
                *program_filters,
                DevelopmentProgram.disease_entity_id.is_not(None),
            )
        ).all()
        disease_identities = self._canonical_entity_identity_labels(
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
        if not self.include_unpublished:
            current_organization_filters.append(
                self._published_identity_exists(
                    DevelopmentProgramOrganization.organization_entity_id,
                    EntityType.ORGANIZATION,
                    correlate_from=DevelopmentProgramOrganization.__table__,
                )
            )
        current_organizations = self.session.execute(
            select(
                DevelopmentProgram.drug_entity_id,
                DevelopmentProgramOrganization.organization_entity_id,
            )
            .join(
                DevelopmentProgramOrganization,
                and_(
                    DevelopmentProgramOrganization.program_id == DevelopmentProgram.id,
                    DevelopmentProgramOrganization.tenant_id == DevelopmentProgram.tenant_id,
                    DevelopmentProgramOrganization.organization_set_version
                    == DevelopmentProgram.organization_set_version,
                ),
            )
            .where(*current_organization_filters)
        ).all()
        legacy_organizations = self.session.execute(
            select(DevelopmentProgram.drug_entity_id, DevelopmentProgram.organization_entity_id).where(
                *program_filters,
                DevelopmentProgram.organization_entity_id.is_not(None),
            )
        ).all()
        organization_rows = [(drug_id, organization_id) for drug_id, organization_id in current_organizations] + [
            (drug_id, organization_id)
            for drug_id, organization_id in legacy_organizations
            if organization_id is not None
        ]
        organization_identities = self._canonical_entity_identity_labels(
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
        for drug_id, modality in self.session.execute(
            select(DevelopmentProgram.drug_entity_id, program_modality)
            .where(*program_filters, program_modality.is_not(None))
            .distinct()
        ).all():
            requested_id = raw_to_requested.get(str(drug_id))
            if requested_id is not None:
                modalities[requested_id].add(modality)
        for drug_id, raw_status, count in self.session.execute(
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

    def company_dossier(self, entity_id: str, limit: int = 100) -> CompanyDossierResponse | None:
        dossier = self.entity_dossier(entity_id, limit)
        if dossier is None or dossier.entity.entity_type != EntityType.ORGANIZATION:
            return None
        timeline = self.company_timeline(entity_id, limit, 0)
        if timeline is None:
            return None

        program_filters = [
            DevelopmentProgram.tenant_id == self.tenant_id,
            DevelopmentProgram.organization_entity_id == entity_id,
        ]

        def phase_rank(column: Any) -> Any:
            return case(
                *((column == DevelopmentPhase(phase), rank) for phase, rank in _DEVELOPMENT_PHASE_RANK.items()),
                else_=None,
            )

        program_count, drug_count, indication_count, highest_phase_rank = self.session.execute(
            select(
                func.count(DevelopmentProgram.id),
                func.count(func.distinct(DevelopmentProgram.drug_entity_id)),
                func.count(func.distinct(DevelopmentProgram.disease_entity_id)),
                func.max(phase_rank(DevelopmentProgram.phase)),
            ).where(*program_filters)
        ).one()
        phase_distribution = {
            phase.value if isinstance(phase, DevelopmentPhase) else str(phase): int(count)
            for phase, count in self.session.execute(
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
            for modality in self.session.scalars(
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
                DevelopmentProgramTarget.tenant_id == self.tenant_id,
                DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
            )
        )
        legacy_targets = select(DevelopmentProgram.target_entity_id).where(
            *program_filters,
            DevelopmentProgram.target_entity_id.is_not(None),
        )
        target_source = union_all(current_targets, legacy_targets).subquery()
        target_count = self.session.scalar(select(func.count(func.distinct(target_source.c.target_entity_id)))) or 0
        deal_count = self.session.scalar(select(func.count(DealProfile.id)).where(*self._deal_filters(entity_id))) or 0

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

    def disease_dossier(self, entity_id: str, limit: int = 100) -> DiseaseDossierResponse | None:
        dossier = self.entity_dossier(entity_id, limit)
        if dossier is None or dossier.entity.entity_type != EntityType.DISEASE:
            return None

        program_filters = [
            DevelopmentProgram.tenant_id == self.tenant_id,
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
        ) = self.session.execute(
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
            for phase, count in self.session.execute(
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
            for modality in self.session.scalars(
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
                DevelopmentProgramTarget.tenant_id == self.tenant_id,
                DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
            )
        )
        legacy_targets = select(DevelopmentProgram.target_entity_id).where(
            *program_filters,
            DevelopmentProgram.target_entity_id.is_not(None),
        )
        target_source = union_all(current_targets, legacy_targets).subquery()
        target_count = self.session.scalar(select(func.count(func.distinct(target_source.c.target_entity_id)))) or 0

        epidemiology = self.search_epidemiology_observations(
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
        latest_epidemiology_at = self.session.scalar(
            select(func.max(EpidemiologyObservation.period_end)).where(
                *self._epidemiology_filters(entity_id, None, None, None, None, None, None, None, None, None, None)
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
                clinical_trial_count=self._count(
                    ClinicalTrialProfile,
                    self._clinical_trial_filters(entity_id, None),
                ),
                patent_count=self._count(PatentFamily, self._patent_filters(entity_id, None)),
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

    def entity_dossier(self, entity_id: str, limit: int = 50) -> EntityDossierResponse | None:
        entity = self.session.scalar(
            select(Entity).where(
                Entity.id == entity_id,
                Entity.tenant_id == self.tenant_id,
                Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
            )
        )
        if entity is None:
            return None

        relationships = self.relationships(entity_id, limit)
        activities = self.bioactivities_for_entity(entity_id, None, limit)
        programs = self.programs_for_entity(entity_id, limit)
        clinical_trials = self.clinical_trial_search_items(
            entity_id,
            None,
            None,
            None,
            None,
            None,
            None,
            limit,
        )
        patents = self.patents(entity_id, None, limit)
        deals = self._deal_search_items(self._deal_filters(entity_id), limit, 0)
        regulatory_events = self.regulatory_search_items(entity_id, None, None, None, None, None, limit)
        news_events = self.news_event_search_items(entity_id, None, None, None, None, None, None, None, limit)
        structures = self.structures(entity_id, None, limit)
        target_evidence = self.target_evidence_for_entity(entity_id, limit)

        counts: dict[EntityDossierDomain, int] = {
            "relationships": self._count(Relationship, self._relationship_filters(entity_id)),
            "evidence": self._count(EvidenceClaim, self._evidence_filters(entity_id)),
            "activities": self._count(ActivityMeasurement, self._activity_filters(entity_id)),
            "programs": self._count(DevelopmentProgram, self._program_filters(entity_id)),
            "clinical_trials": self._count(ClinicalTrialProfile, self._clinical_trial_filters(entity_id, None)),
            "patents": self._count(PatentFamily, self._patent_filters(entity_id, None)),
            "deals": self._count(DealProfile, self._deal_filters(entity_id)),
            "regulatory_events": self._count(RegulatoryEvent, self._regulatory_filters(entity_id, None, None)),
            "news_events": self._count(
                NewsEvent,
                self._news_event_filters(entity_id, None, None, None, None, None, None, None),
            ),
            "structures": self._count(CompoundStructure, self._structure_filters(entity_id, None)),
            "target_evidence": self._count(
                TargetEvidenceObservation,
                self._target_evidence_filters(entity_id),
            ),
        }
        returned: dict[EntityDossierDomain, int] = {
            "relationships": len(relationships),
            "evidence": 0,
            "activities": len(activities),
            "programs": len(programs),
            "clinical_trials": len(clinical_trials),
            "patents": len(patents),
            "deals": len(deals),
            "regulatory_events": len(regulatory_events),
            "news_events": len(news_events),
            "structures": len(structures),
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
            relationships=relationships,
            activities=activities,
            programs=programs,
            clinical_trials=clinical_trials,
            patents=patents,
            deals=deals,
            regulatory_events=regulatory_events,
            news_events=news_events,
            structures=structures,
            target_evidence=target_evidence,
            coverage=coverage,
            as_of=datetime.now(UTC),
            warnings=warnings,
        )

    def relationships(self, entity_id: str, limit: int, offset: int = 0) -> list[EntityRelationshipRead]:
        rows = self.session.execute(
            select(Relationship, Entity)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == self.tenant_id,
                    or_(
                        and_(Relationship.subject_id == entity_id, Entity.id == Relationship.object_id),
                        and_(Relationship.object_id == entity_id, Entity.id == Relationship.subject_id),
                    ),
                ),
            )
            .where(*self._relationship_filters(entity_id))
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

    def target_evidence_for_entity(
        self,
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
        rows = self.session.execute(
            select(
                TargetEvidenceObservation,
                target.c.name.label("target_name"),
                disease.c.name.label("disease_name"),
            )
            .join(target, target.c.id == TargetEvidenceObservation.target_entity_id)
            .outerjoin(disease, disease.c.id == TargetEvidenceObservation.disease_entity_id)
            .where(
                *self._target_evidence_filters(
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
        self, target_entity_id: str, standard_type: str | None, limit: int, offset: int = 0
    ) -> list[BioactivityRead]:
        filters = [
            ActivityMeasurement.tenant_id == self.tenant_id,
            ActivityMeasurement.target_entity_id == target_entity_id,
        ]
        if standard_type:
            filters.append(ActivityMeasurement.standard_type == standard_type)
        return self._read_bioactivities(filters, limit, offset)

    def bioactivities_for_entity(
        self, entity_id: str, standard_type: str | None, limit: int, offset: int = 0
    ) -> list[BioactivityRead]:
        filters = self._activity_filters(entity_id)
        if standard_type:
            filters.append(ActivityMeasurement.standard_type == standard_type)
        return self._read_bioactivities(filters, limit, offset)

    def sar_comparison(
        self,
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
            ActivityMeasurement.tenant_id == self.tenant_id,
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
            .where(CompoundStructure.tenant_id == self.tenant_id)
            .subquery("latest_sar_structure")
        )
        rows = self.session.execute(
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
                and_(Assay.id == ActivityMeasurement.assay_id, Assay.tenant_id == self.tenant_id),
            )
            .join(
                Entity,
                and_(Entity.id == ActivityMeasurement.compound_entity_id, Entity.tenant_id == self.tenant_id),
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
        total, as_of = self.session.execute(
            select(func.count(ActivityMeasurement.id), func.max(ActivityMeasurement.updated_at))
            .join(
                Assay,
                and_(Assay.id == ActivityMeasurement.assay_id, Assay.tenant_id == self.tenant_id),
            )
            .where(*filters)
        ).one()
        facets = self._sar_facets(filters)
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

    def _sar_facets(self, filters: list[ColumnElement[bool]]) -> dict[str, dict[str, int]]:
        facets: dict[str, dict[str, int]] = {}
        for name, field in (
            ("standard_type", ActivityMeasurement.standard_type),
            ("assay_type", Assay.assay_type),
            ("assay_format", Assay.assay_format),
            ("organism", Assay.organism),
            ("cell_line", Assay.cell_line),
        ):
            rows = self.session.execute(
                select(field, func.count(ActivityMeasurement.id))
                .join(
                    Assay,
                    and_(Assay.id == ActivityMeasurement.assay_id, Assay.tenant_id == self.tenant_id),
                )
                .where(*filters, field.is_not(None))
                .group_by(field)
                .order_by(func.count(ActivityMeasurement.id).desc(), field)
                .limit(100)
            ).all()
            facets[name] = {str(value): int(count) for value, count in rows}
        return facets

    def _read_bioactivities(self, filters: list[ColumnElement[bool]], limit: int, offset: int) -> list[BioactivityRead]:
        rows = self.session.execute(
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

    def competitive_programs(self, target_entity_id: str, limit: int, offset: int = 0) -> list[CompetitiveProgramRead]:
        return self._read_programs(self._program_filters(target_entity_id), limit, offset)

    def _pipeline_trial_exists(
        self,
        drug_entity_id: Any,
        *,
        require_results: bool = False,
        result_evaluation: str | None = None,
    ) -> ColumnElement[bool]:
        role_drug = Entity.__table__.alias("pipeline_trial_role_drug")
        program_drug = Entity.__table__.alias("pipeline_trial_program_drug")
        statement = (
            select(ClinicalTrialEntityRole.id)
            .join(
                ClinicalTrialProfile,
                and_(
                    ClinicalTrialProfile.tenant_id == self.tenant_id,
                    ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
                ),
            )
            .join(
                role_drug,
                and_(
                    role_drug.c.tenant_id == self.tenant_id,
                    role_drug.c.id == ClinicalTrialEntityRole.entity_id,
                    role_drug.c.entity_type == EntityType.DRUG,
                ),
            )
            .join(
                program_drug,
                and_(
                    program_drug.c.tenant_id == self.tenant_id,
                    program_drug.c.id == drug_entity_id,
                    program_drug.c.entity_type == EntityType.DRUG,
                ),
            )
            .where(
                ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
                role_drug.c.normalized_name == program_drug.c.normalized_name,
            )
        )
        if require_results or result_evaluation:
            statement = statement.where(ClinicalTrialProfile.has_results.is_(True))
        if result_evaluation:
            statement = statement.where(ClinicalTrialProfile.result_evaluation == result_evaluation)
        return statement.exists()

    def _pipeline_deal_exists(
        self,
        drug_entity_id: Any,
        *,
        currency: str | None = None,
        total_potential_amount_min: float | None = None,
        total_potential_amount_max: float | None = None,
    ) -> ColumnElement[bool]:
        deal_filters: list[ColumnElement[bool]] = []
        if currency:
            deal_filters.append(DealProfile.currency == currency)
        if total_potential_amount_min is not None:
            deal_filters.append(DealProfile.total_potential_amount >= total_potential_amount_min)
        if total_potential_amount_max is not None:
            deal_filters.append(DealProfile.total_potential_amount <= total_potential_amount_max)
        normalized = (
            select(DealAssetAssociation.id)
            .join(
                DealProfile,
                and_(
                    DealProfile.tenant_id == self.tenant_id,
                    DealProfile.id == DealAssetAssociation.deal_id,
                ),
            )
            .where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.asset_entity_id == drug_entity_id,
                *deal_filters,
            )
        )
        relationship = (
            select(Relationship.id)
            .join(
                DealProfile,
                and_(
                    DealProfile.tenant_id == self.tenant_id,
                    DealProfile.entity_id == Relationship.subject_id,
                ),
            )
            .where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.predicate == "deal_asset",
                Relationship.object_id == drug_entity_id,
                *deal_filters,
            )
        )
        return or_(normalized.exists(), relationship.exists())

    def _clinical_trial_target_program_exists(self, target_entity_id: str) -> ColumnElement[bool]:
        role_drug = Entity.__table__.alias("target_trial_role_drug")
        program_drug = Entity.__table__.alias("target_trial_program_drug")
        target_identity_ids = self._entity_identity_ids(target_entity_id, EntityType.TARGET)
        current_target = (
            select(DevelopmentProgramTarget.id)
            .where(
                DevelopmentProgramTarget.tenant_id == self.tenant_id,
                DevelopmentProgramTarget.program_id == DevelopmentProgram.id,
                DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
                DevelopmentProgramTarget.target_entity_id.in_(target_identity_ids),
            )
            .exists()
        )
        conditions: list[ColumnElement[bool]] = [
            DevelopmentProgram.tenant_id == self.tenant_id,
            or_(DevelopmentProgram.target_entity_id.in_(target_identity_ids), current_target),
            ClinicalTrialEntityRole.tenant_id == self.tenant_id,
            ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
            ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
            role_drug.c.normalized_name == program_drug.c.normalized_name,
        ]
        if not self.include_unpublished:
            conditions.extend(
                [
                    role_drug.c.review_status == ReviewStatus.VERIFIED,
                    self._published_identity_exists(
                        DevelopmentProgram.drug_entity_id,
                        EntityType.DRUG,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                ]
            )
        return (
            select(DevelopmentProgram.id)
            .join(
                program_drug,
                and_(
                    program_drug.c.tenant_id == self.tenant_id,
                    program_drug.c.id == DevelopmentProgram.drug_entity_id,
                    program_drug.c.entity_type == EntityType.DRUG,
                ),
            )
            .join(
                role_drug,
                and_(
                    role_drug.c.tenant_id == self.tenant_id,
                    role_drug.c.entity_type == EntityType.DRUG,
                ),
            )
            .join(
                ClinicalTrialEntityRole,
                ClinicalTrialEntityRole.entity_id == role_drug.c.id,
            )
            .where(*conditions)
            .exists()
        )

    def _pipeline_related_signal_exists(
        self,
        drug_entity_id: Any,
        related_entity_id: str,
    ) -> ColumnElement[bool]:
        linked_trial = (
            select(ClinicalTrialEntityRole.id)
            .join(
                ClinicalTrialProfile,
                and_(
                    ClinicalTrialProfile.tenant_id == self.tenant_id,
                    ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
                ),
            )
            .where(
                ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                ClinicalTrialEntityRole.entity_id == drug_entity_id,
                ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
                ClinicalTrialProfile.entity_id == related_entity_id,
            )
        )
        linked_deal = (
            select(DealAssetAssociation.id)
            .join(
                DealProfile,
                and_(
                    DealProfile.tenant_id == self.tenant_id,
                    DealProfile.id == DealAssetAssociation.deal_id,
                ),
            )
            .where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.asset_entity_id == drug_entity_id,
                DealProfile.entity_id == related_entity_id,
            )
        )
        legacy_deal = select(Relationship.id).where(
            Relationship.tenant_id == self.tenant_id,
            Relationship.predicate == "deal_asset",
            Relationship.subject_id == related_entity_id,
            Relationship.object_id == drug_entity_id,
        )
        return or_(linked_trial.exists(), linked_deal.exists(), legacy_deal.exists())

    def _pipeline_drug_identity_expressions(self, drug: Any) -> tuple[ColumnElement[Any], ColumnElement[Any]]:
        """Resolve the display identity without changing raw program relationships.

        Imported source rows can contain several draft entities for one drug name. The
        public-facing drug grain should use an approved canonical link or the stable
        verified representative already used by target landscape aggregation, while
        signal joins continue to use the raw ``DevelopmentProgram.drug_entity_id``.
        """

        canonical_link = EntityCanonicalLink.__table__.alias("pipeline_drug_canonical_link")
        canonical_drug = Entity.__table__.alias("pipeline_canonical_drug")
        verified_drug = Entity.__table__.alias("pipeline_verified_drug")
        canonical_drug_id = (
            select(canonical_link.c.canonical_entity_id)
            .where(
                canonical_link.c.tenant_id == self.tenant_id,
                canonical_link.c.alias_entity_id == drug.c.id,
                canonical_link.c.active.is_(True),
            )
            .correlate(drug)
            .limit(1)
            .scalar_subquery()
        )
        verified_trusted_identifier_count = (
            select(func.count(EntityIdentifier.id))
            .where(
                EntityIdentifier.tenant_id == self.tenant_id,
                EntityIdentifier.entity_id == verified_drug.c.id,
                EntityIdentifier.entity_type == EntityType.DRUG,
                EntityIdentifier.trusted_namespace.is_(True),
                EntityIdentifier.review_status == ReviewStatus.VERIFIED,
            )
            .correlate(verified_drug)
            .scalar_subquery()
        )
        verified_drug_id = (
            select(verified_drug.c.id)
            .where(
                verified_drug.c.tenant_id == self.tenant_id,
                verified_drug.c.entity_type == EntityType.DRUG,
                verified_drug.c.normalized_name == drug.c.normalized_name,
                verified_drug.c.review_status == ReviewStatus.VERIFIED,
            )
            .order_by(verified_trusted_identifier_count.desc(), verified_drug.c.id)
            .correlate(drug)
            .limit(1)
            .scalar_subquery()
        )
        canonical_drug_name = (
            select(canonical_drug.c.name)
            .select_from(
                canonical_link.join(canonical_drug, canonical_drug.c.id == canonical_link.c.canonical_entity_id)
            )
            .where(
                canonical_link.c.tenant_id == self.tenant_id,
                canonical_link.c.alias_entity_id == drug.c.id,
                canonical_link.c.active.is_(True),
            )
            .correlate(drug)
            .limit(1)
            .scalar_subquery()
        )
        verified_drug_name = (
            select(verified_drug.c.name)
            .where(
                verified_drug.c.tenant_id == self.tenant_id,
                verified_drug.c.entity_type == EntityType.DRUG,
                verified_drug.c.normalized_name == drug.c.normalized_name,
                verified_drug.c.review_status == ReviewStatus.VERIFIED,
            )
            .order_by(verified_trusted_identifier_count.desc(), verified_drug.c.id)
            .correlate(drug)
            .limit(1)
            .scalar_subquery()
        )
        return (
            func.coalesce(canonical_drug_id, verified_drug_id, drug.c.id),
            func.coalesce(canonical_drug_name, verified_drug_name, drug.c.name),
        )

    def _program_query(
        self,
        query: str | None,
        modality: list[str] | None,
        phase: str | None,
        geography: str | None,
        *,
        innovation_type: list[str] | None = None,
        therapeutic_area: list[str] | None = None,
        drug_category: list[str] | None = None,
        program_status: str | None = None,
        organization_role: str | None = None,
        organization_type: str | None = None,
        organization_country_region: str | None = None,
        status_date_from: datetime | None = None,
        status_date_to: datetime | None = None,
        drug_entity_id: str | None = None,
        target_entity_id: str | None = None,
        target_combination_key: str | None = None,
        disease_entity_id: str | None = None,
        organization_entity_id: str | None = None,
        global_phase: str | None = None,
        china_phase: str | None = None,
        global_phase_started_from: datetime | None = None,
        global_phase_started_to: datetime | None = None,
        china_phase_started_from: datetime | None = None,
        china_phase_started_to: datetime | None = None,
        development_rights_region: str | None = None,
        commercialization_rights_region: str | None = None,
        program_tag: list[str] | None = None,
        milestone_type: str | None = None,
        milestone_from: datetime | None = None,
        milestone_to: datetime | None = None,
        has_clinical_results: bool | None = None,
        clinical_result_evaluation: str | None = None,
        has_deal: bool | None = None,
        deal_currency: str | None = None,
        deal_total_potential_amount_min: float | None = None,
        deal_total_potential_amount_max: float | None = None,
        related_entity_id: str | None = None,
    ) -> tuple[Any, Any, Any, Any, Select[Any]]:
        drug = Entity.__table__.alias("pipeline_drug")
        target = Entity.__table__.alias("pipeline_target")
        disease = Entity.__table__.alias("pipeline_disease")
        organization = Entity.__table__.alias("pipeline_organization")
        public_modality = _public_program_modality_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        public_drug_category = _public_program_drug_category_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        filters: list[ColumnElement[bool]] = [
            DevelopmentProgram.tenant_id == self.tenant_id,
            self._unique_program_record(),
        ]
        if not self.include_unpublished:
            filters.extend(
                [
                    self._published_identity_exists(
                        DevelopmentProgram.drug_entity_id,
                        EntityType.DRUG,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.target_entity_id,
                        EntityType.TARGET,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.disease_entity_id,
                        EntityType.DISEASE,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.organization_entity_id,
                        EntityType.ORGANIZATION,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                ]
            )
        normalized_query = query.strip().casefold() if query else None
        if normalized_query:
            searchable = (
                drug.c.name,
                target.c.name,
                disease.c.name,
                organization.c.name,
                DevelopmentProgram.mechanism_of_action,
            )
            filters.append(
                or_(
                    *(func.lower(column).contains(normalized_query, autoescape=True) for column in searchable),
                    self._program_target_name_exists(normalized_query),
                    self._program_organization_name_exists(normalized_query),
                )
            )
        if modality:
            # Same-dimension OR, matching the deal asset multi-select contract.
            filters.append(public_modality.in_(modality))
        if innovation_type:
            filters.append(DevelopmentProgram.innovation_type.in_(innovation_type))
        if therapeutic_area:
            filters.append(DevelopmentProgram.therapeutic_area.in_(therapeutic_area))
        if drug_category:
            filters.append(public_drug_category.in_(drug_category))
        if program_status == "unknown":
            filters.append(
                or_(
                    DevelopmentProgram.program_status == "unknown",
                    DevelopmentProgram.program_status.is_(None),
                )
            )
        elif program_status:
            filters.append(DevelopmentProgram.program_status == program_status)
        if organization_entity_id or organization_role or organization_type or organization_country_region:
            # Conditions apply to the program's current organization set version only, so
            # superseded historical rows never widen a query. When an entity and role
            # attributes are combined they must describe the same governed relationship.
            org_conditions = [
                DevelopmentProgramOrganization.tenant_id == self.tenant_id,
                DevelopmentProgramOrganization.program_id == DevelopmentProgram.id,
                DevelopmentProgramOrganization.organization_set_version == DevelopmentProgram.organization_set_version,
            ]
            if organization_entity_id:
                org_conditions.append(DevelopmentProgramOrganization.organization_entity_id == organization_entity_id)
            if organization_role:
                org_conditions.append(DevelopmentProgramOrganization.role == organization_role)
            if organization_type:
                org_conditions.append(DevelopmentProgramOrganization.organization_type == organization_type)
            if organization_country_region:
                org_conditions.append(DevelopmentProgramOrganization.country_region == organization_country_region)
            organization_match = select(literal(True)).where(*org_conditions).exists()
            if organization_entity_id and not (organization_role or organization_type or organization_country_region):
                filters.append(
                    or_(
                        DevelopmentProgram.organization_entity_id == organization_entity_id,
                        organization_match,
                    )
                )
            else:
                filters.append(organization_match)
        if phase:
            filters.append(DevelopmentProgram.phase == phase)
        if geography:
            filters.append(DevelopmentProgram.geography == geography)
        if status_date_from:
            filters.append(DevelopmentProgram.status_date >= status_date_from)
        if status_date_to:
            filters.append(DevelopmentProgram.status_date <= status_date_to)
        if drug_entity_id:
            filters.append(DevelopmentProgram.drug_entity_id == drug_entity_id)
        if target_entity_id:
            filters.append(
                or_(
                    DevelopmentProgram.target_entity_id.in_(
                        self._entity_identity_ids(target_entity_id, EntityType.TARGET)
                    ),
                    self._program_target_exists(target_entity_id),
                )
            )
        if target_combination_key:
            filters.append(self._program_target_combination_matches(target_combination_key))
        if disease_entity_id:
            filters.append(DevelopmentProgram.disease_entity_id == disease_entity_id)
        if global_phase:
            filters.append(DevelopmentProgram.global_phase == global_phase)
        if china_phase:
            filters.append(DevelopmentProgram.china_phase == china_phase)
        if global_phase_started_from:
            filters.append(DevelopmentProgram.global_phase_started_at >= global_phase_started_from)
        if global_phase_started_to:
            filters.append(DevelopmentProgram.global_phase_started_at <= global_phase_started_to)
        if china_phase_started_from:
            filters.append(DevelopmentProgram.china_phase_started_at >= china_phase_started_from)
        if china_phase_started_to:
            filters.append(DevelopmentProgram.china_phase_started_at <= china_phase_started_to)
        if development_rights_region:
            filters.append(
                self._json_array_value_exists(
                    DevelopmentProgram.development_rights_regions,
                    development_rights_region,
                )
            )
        if commercialization_rights_region:
            filters.append(
                self._json_array_value_exists(
                    DevelopmentProgram.commercialization_rights_regions,
                    commercialization_rights_region,
                )
            )
        if program_tag:
            # Same-dimension OR: a program matches when any selected tag is present.
            visible_program_tags = public_program_tags(program_tag)
            filters.append(
                or_(
                    *(
                        self._json_array_value_exists(DevelopmentProgram.program_tags, tag)
                        for tag in visible_program_tags
                    )
                )
                if visible_program_tags
                else literal(False)
            )
        if milestone_type or milestone_from or milestone_to:
            filters.append(
                self._json_object_array_exists(
                    DevelopmentProgram.milestones,
                    text_field="milestone_type",
                    text_value=milestone_type,
                    datetime_field="occurred_at",
                    datetime_from=milestone_from,
                    datetime_to=milestone_to,
                )
            )
        clinical_result_match = self._pipeline_trial_exists(
            DevelopmentProgram.drug_entity_id,
            require_results=True,
            result_evaluation=clinical_result_evaluation,
        )
        if has_clinical_results is True or clinical_result_evaluation:
            filters.append(clinical_result_match)
        elif has_clinical_results is False:
            filters.append(~clinical_result_match)
        deal_match = self._pipeline_deal_exists(
            DevelopmentProgram.drug_entity_id,
            currency=deal_currency,
            total_potential_amount_min=deal_total_potential_amount_min,
            total_potential_amount_max=deal_total_potential_amount_max,
        )
        if has_deal is True or any(
            value is not None
            for value in (deal_currency, deal_total_potential_amount_min, deal_total_potential_amount_max)
        ):
            filters.append(deal_match)
        elif has_deal is False:
            filters.append(~deal_match)
        if related_entity_id:
            filters.append(
                or_(
                    DevelopmentProgram.drug_entity_id == related_entity_id,
                    DevelopmentProgram.target_entity_id == related_entity_id,
                    self._program_target_exists(related_entity_id),
                    DevelopmentProgram.disease_entity_id == related_entity_id,
                    DevelopmentProgram.organization_entity_id == related_entity_id,
                    self._program_organization_exists(related_entity_id),
                    self._pipeline_related_signal_exists(
                        DevelopmentProgram.drug_entity_id,
                        related_entity_id,
                    ),
                )
            )
        joined = (
            select(
                DevelopmentProgram,
                drug.c.name.label("drug_name"),
                target.c.name.label("target_name"),
                disease.c.name.label("disease_name"),
                organization.c.name.label("organization_name"),
            )
            .join(drug, drug.c.id == DevelopmentProgram.drug_entity_id)
            .outerjoin(target, target.c.id == DevelopmentProgram.target_entity_id)
            .outerjoin(disease, disease.c.id == DevelopmentProgram.disease_entity_id)
            .outerjoin(organization, organization.c.id == DevelopmentProgram.organization_entity_id)
            .where(*filters)
        )
        return drug, target, disease, organization, joined

    def program_saved_search_matches_entity(self, entity_id: str, query: PipelineSavedSearchQuery) -> bool:
        def start(value: Any) -> datetime | None:
            return datetime.combine(value, time.min, tzinfo=UTC) if value else None

        def end(value: Any) -> datetime | None:
            return datetime.combine(value, time.max, tzinfo=UTC) if value else None

        *_, joined = self._program_query(
            query.q,
            query.modality,
            query.phase.value if query.phase else None,
            query.geography,
            innovation_type=query.innovation_type,
            therapeutic_area=query.therapeutic_area,
            drug_category=query.drug_category,
            program_status=query.program_status,
            organization_role=query.organization_role,
            organization_type=query.organization_type,
            organization_country_region=query.organization_country_region,
            status_date_from=start(query.status_date_from),
            status_date_to=end(query.status_date_to),
            drug_entity_id=query.drug_entity_id,
            target_entity_id=query.target_entity_id,
            target_combination_key=query.target_combination_key,
            disease_entity_id=query.disease_entity_id,
            organization_entity_id=query.organization_entity_id,
            global_phase=query.global_phase.value if query.global_phase else None,
            china_phase=query.china_phase.value if query.china_phase else None,
            global_phase_started_from=start(query.global_phase_started_from),
            global_phase_started_to=end(query.global_phase_started_to),
            china_phase_started_from=start(query.china_phase_started_from),
            china_phase_started_to=end(query.china_phase_started_to),
            development_rights_region=query.development_rights_region,
            commercialization_rights_region=query.commercialization_rights_region,
            program_tag=query.program_tag,
            milestone_type=query.milestone_type,
            milestone_from=start(query.milestone_from),
            milestone_to=end(query.milestone_to),
            has_clinical_results=query.has_clinical_results,
            clinical_result_evaluation=(
                query.clinical_result_evaluation.value if query.clinical_result_evaluation else None
            ),
            has_deal=query.has_deal,
            deal_currency=query.deal_currency,
            deal_total_potential_amount_min=query.deal_total_potential_amount_min,
            deal_total_potential_amount_max=query.deal_total_potential_amount_max,
            related_entity_id=entity_id,
        )
        return self.session.scalar(joined.with_only_columns(literal(True)).limit(1)) is True

    def search_programs(
        self,
        query: str | None,
        modality: list[str] | None,
        phase: str | None,
        geography: str | None,
        limit: int,
        offset: int,
        *,
        innovation_type: list[str] | None = None,
        therapeutic_area: list[str] | None = None,
        drug_category: list[str] | None = None,
        program_status: str | None = None,
        organization_role: str | None = None,
        organization_type: str | None = None,
        organization_country_region: str | None = None,
        status_date_from: datetime | None = None,
        status_date_to: datetime | None = None,
        drug_entity_id: str | None = None,
        target_entity_id: str | None = None,
        target_combination_key: str | None = None,
        disease_entity_id: str | None = None,
        organization_entity_id: str | None = None,
        global_phase: str | None = None,
        china_phase: str | None = None,
        global_phase_started_from: datetime | None = None,
        global_phase_started_to: datetime | None = None,
        china_phase_started_from: datetime | None = None,
        china_phase_started_to: datetime | None = None,
        development_rights_region: str | None = None,
        commercialization_rights_region: str | None = None,
        program_tag: list[str] | None = None,
        milestone_type: str | None = None,
        milestone_from: datetime | None = None,
        milestone_to: datetime | None = None,
        has_clinical_results: bool | None = None,
        clinical_result_evaluation: str | None = None,
        has_deal: bool | None = None,
        deal_currency: str | None = None,
        deal_total_potential_amount_min: float | None = None,
        deal_total_potential_amount_max: float | None = None,
        sort_by: PipelineSortField = "status_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[PipelineSortField]] | None = None,
        landscape_limit: int = 20,
        landscape_stage_scope: PipelineLandscapeStageScope = "overall",
        landscape_target_aggregation: PipelineTargetAggregation = "all",
        result_grain: PipelineResultGrain = "program",
    ) -> PipelineSearchResult:
        drug, target, disease, organization, joined = self._program_query(
            query,
            modality,
            phase,
            geography,
            innovation_type=innovation_type,
            therapeutic_area=therapeutic_area,
            drug_category=drug_category,
            program_status=program_status,
            organization_role=organization_role,
            organization_type=organization_type,
            organization_country_region=organization_country_region,
            status_date_from=status_date_from,
            status_date_to=status_date_to,
            drug_entity_id=drug_entity_id,
            target_entity_id=target_entity_id,
            target_combination_key=target_combination_key,
            disease_entity_id=disease_entity_id,
            organization_entity_id=organization_entity_id,
            global_phase=global_phase,
            china_phase=china_phase,
            global_phase_started_from=global_phase_started_from,
            global_phase_started_to=global_phase_started_to,
            china_phase_started_from=china_phase_started_from,
            china_phase_started_to=china_phase_started_to,
            development_rights_region=development_rights_region,
            commercialization_rights_region=commercialization_rights_region,
            program_tag=program_tag,
            milestone_type=milestone_type,
            milestone_from=milestone_from,
            milestone_to=milestone_to,
            has_clinical_results=has_clinical_results,
            clinical_result_evaluation=clinical_result_evaluation,
            has_deal=has_deal,
            deal_currency=deal_currency,
            deal_total_potential_amount_min=deal_total_potential_amount_min,
            deal_total_potential_amount_max=deal_total_potential_amount_max,
        )
        # Keep raw program relationships for signal joins, but expose one stable
        # verified drug identity in every result grain so counts and row labels agree.
        drug_identity_id, drug_identity_name = self._pipeline_drug_identity_expressions(drug)
        result_joined = joined.add_columns(
            drug_identity_id.label("drug_identity_id"),
            drug_identity_name.label("drug_identity_name"),
        )
        phase_rank = {
            "phase": case(
                *[
                    (DevelopmentProgram.phase == DevelopmentPhase(phase), rank)
                    for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
                ],
                else_=-2,
            ),
            "global_phase": case(
                *[
                    (DevelopmentProgram.global_phase == DevelopmentPhase(phase), rank)
                    for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
                ],
                else_=-2,
            ),
            "china_phase": case(
                *[
                    (DevelopmentProgram.china_phase == DevelopmentPhase(phase), rank)
                    for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
                ],
                else_=-2,
            ),
        }
        effective_sort = validate_sort_clauses(
            sort,
            PIPELINE_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        public_modality = _public_program_modality_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        public_drug_category = _public_program_drug_category_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        sort_expressions: dict[PipelineSortField, Any] = {
            "status_date": DevelopmentProgram.status_date,
            "drug_name": func.lower(drug_identity_name),
            "target_name": func.lower(target.c.name),
            "disease_name": func.lower(disease.c.name),
            "organization_name": func.lower(organization.c.name),
            "modality": func.lower(public_modality),
            "mechanism_of_action": func.lower(DevelopmentProgram.mechanism_of_action),
            "phase": phase_rank["phase"],
            "status_detail": func.lower(DevelopmentProgram.status_detail),
            "geography": func.lower(DevelopmentProgram.geography),
            "global_phase": phase_rank["global_phase"],
            "china_phase": phase_rank["china_phase"],
            "global_phase_started_at": DevelopmentProgram.global_phase_started_at,
            "china_phase_started_at": DevelopmentProgram.china_phase_started_at,
        }
        ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
        facet_source = (
            result_joined.with_only_columns(
                DevelopmentProgram.id.label("program_id"),
                DevelopmentProgram.drug_entity_id.label("drug_entity_id"),
                drug_identity_id.label("drug_identity_id"),
                drug_identity_name.label("drug_name"),
                DevelopmentProgram.target_entity_id.label("target_entity_id"),
                target.c.name.label("target_name"),
                DevelopmentProgram.target_set_version.label("target_set_version"),
                DevelopmentProgram.organization_set_version.label("organization_set_version"),
                DevelopmentProgram.target_combination_key.label("target_combination_key"),
                DevelopmentProgram.disease_entity_id.label("disease_entity_id"),
                disease.c.name.label("disease_name"),
                DevelopmentProgram.organization_entity_id.label("organization_entity_id"),
                organization.c.name.label("organization_name"),
                public_modality.label("modality"),
                DevelopmentProgram.mechanism_of_action.label("mechanism_of_action"),
                DevelopmentProgram.innovation_type.label("innovation_type"),
                DevelopmentProgram.therapeutic_area.label("therapeutic_area"),
                public_drug_category.label("drug_category"),
                DevelopmentProgram.program_status.label("program_status"),
                DevelopmentProgram.phase.label("phase"),
                DevelopmentProgram.status_detail.label("status_detail"),
                DevelopmentProgram.status_date.label("status_date"),
                DevelopmentProgram.geography.label("geography"),
                DevelopmentProgram.global_phase.label("global_phase"),
                DevelopmentProgram.china_phase.label("china_phase"),
                DevelopmentProgram.global_phase_started_at.label("global_phase_started_at"),
                DevelopmentProgram.china_phase_started_at.label("china_phase_started_at"),
                DevelopmentProgram.development_rights_regions.label("development_rights_regions"),
                DevelopmentProgram.commercialization_rights_regions.label("commercialization_rights_regions"),
                DevelopmentProgram.program_tags.label("program_tags"),
                DevelopmentProgram.milestones.label("milestones"),
            )
            .order_by(None)
            .subquery()
        )
        project_total = self.session.scalar(select(func.count()).select_from(facet_source)) or 0
        total = project_total

        if result_grain == "drug":
            grouped_phase_rank = {
                name: func.max(
                    case(
                        *[
                            (facet_source.c[name] == DevelopmentPhase(phase), rank)
                            for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
                        ],
                        else_=-2,
                    )
                ).label(name)
                for name in ("phase", "global_phase", "china_phase")
            }
            drug_page_source = (
                select(
                    facet_source.c.drug_identity_id.label("drug_entity_id"),
                    func.min(facet_source.c.drug_name).label("drug_name"),
                    func.min(facet_source.c.target_name).label("target_name"),
                    func.min(facet_source.c.disease_name).label("disease_name"),
                    func.min(facet_source.c.organization_name).label("organization_name"),
                    func.min(facet_source.c.modality).label("modality"),
                    func.min(facet_source.c.mechanism_of_action).label("mechanism_of_action"),
                    grouped_phase_rank["phase"],
                    func.min(facet_source.c.status_detail).label("status_detail"),
                    func.max(facet_source.c.status_date).label("status_date"),
                    func.min(facet_source.c.geography).label("geography"),
                    grouped_phase_rank["global_phase"],
                    grouped_phase_rank["china_phase"],
                    func.min(facet_source.c.global_phase_started_at).label("global_phase_started_at"),
                    func.min(facet_source.c.china_phase_started_at).label("china_phase_started_at"),
                )
                .group_by(facet_source.c.drug_identity_id)
                .subquery()
            )
            drug_sort_expressions = {field: drug_page_source.c[field] for field in PIPELINE_SORT_FIELDS}
            ordered_drug_sort = _ordered_sort_expressions(effective_sort, drug_sort_expressions)
            ordered_drug_ids = list(
                self.session.scalars(
                    select(drug_page_source.c.drug_entity_id)
                    .order_by(*ordered_drug_sort, drug_page_source.c.drug_entity_id)
                    .limit(limit)
                    .offset(offset)
                )
            )
            total = self.session.scalar(select(func.count()).select_from(drug_page_source)) or 0
            if ordered_drug_ids:
                selected_raw_drug_ids = list(
                    self.session.scalars(
                        select(facet_source.c.drug_entity_id)
                        .where(facet_source.c.drug_identity_id.in_(ordered_drug_ids))
                        .distinct()
                    )
                )
                rows = self.session.execute(
                    result_joined.where(DevelopmentProgram.drug_entity_id.in_(selected_raw_drug_ids)).order_by(
                        DevelopmentProgram.drug_entity_id,
                        DevelopmentProgram.id,
                    )
                ).all()
            else:
                rows = []
        else:
            ordered_drug_ids = []
            rows = self.session.execute(
                result_joined.order_by(*ordered_sort, DevelopmentProgram.id).limit(limit).offset(offset)
            ).all()

        facets: dict[str, dict[str, int]] = {}
        facet_id_name = "drug_identity_id" if result_grain == "drug" else "program_id"
        for name in (
            "modality",
            "innovation_type",
            "therapeutic_area",
            "drug_category",
            "program_status",
            "phase",
            "geography",
            "global_phase",
            "china_phase",
        ):
            count_expression = (
                func.count(func.distinct(facet_source.c.drug_identity_id)) if result_grain == "drug" else func.count()
            )
            if name == "program_status":
                # A missing governed status is a visible "unknown" bucket. The
                # row aggregation already exposes it this way; facets and filters
                # must use the same contract instead of silently dropping NULLs.
                column: ColumnElement[Any] = case(
                    (facet_source.c.program_status == "active", "active"),
                    (facet_source.c.program_status == "inactive", "inactive"),
                    else_="unknown",
                ).label("program_status")
                counts = self.session.execute(
                    select(column, count_expression)
                    .select_from(facet_source)
                    .group_by(column)
                    .order_by(count_expression.desc(), column)
                ).all()
            else:
                column = facet_source.c[name]
                counts = self.session.execute(
                    select(column, count_expression)
                    .select_from(facet_source)
                    .where(column.is_not(None))
                    .group_by(column)
                    .order_by(count_expression.desc(), column)
                ).all()
            facets[name] = {
                value.value if hasattr(value, "value") else str(value): count for value, count in counts if value
            }
        for name in (
            "development_rights_regions",
            "commercialization_rights_regions",
            "program_tags",
        ):
            facets[
                {
                    "development_rights_regions": "development_rights_region",
                    "commercialization_rights_regions": "commercialization_rights_region",
                    "program_tags": "program_tag",
                }[name]
            ] = self._json_array_facets(
                facet_source,
                name,
                facet_id_name,
                public_program_tags_only=name == "program_tags",
            )
        facets["milestone_type"] = self._json_object_array_facets(
            facet_source,
            "milestones",
            "milestone_type",
            facet_id_name,
        )
        facets.update(self._pipeline_organization_facets(facet_source, facet_id_name))
        facets.update(self._pipeline_signal_facets(facet_source, facet_id_name))
        landscape = self._pipeline_landscape(
            facet_source,
            project_total,
            limit=landscape_limit,
            stage_scope=landscape_stage_scope,
            target_aggregation=landscape_target_aggregation,
        )
        row_values = [(row[0], row[1], row[2], row[3], row[4], row[5], row[6]) for row in rows]
        target_map = self._program_target_map(
            [row[0] for row in row_values],
            {row[0].id: (row[0].target_entity_id, row[2]) for row in row_values},
        )
        target_map = self._visible_program_target_map(target_map)
        primary_targets = {program_id: targets[0] for program_id, targets in target_map.items() if targets}
        target_combination_keys = self._canonical_target_combination_keys(target_map)
        organization_map = self._program_organization_map(
            [row[0] for row in row_values],
            {row[0].id: (row[0].organization_entity_id, row[4]) for row in row_values},
        )
        organization_map = self._visible_program_organization_map(organization_map)
        primary_organizations = {
            program_id: organizations[0] for program_id, organizations in organization_map.items() if organizations
        }
        disease_identities = (
            {}
            if self.include_unpublished
            else self._published_entity_identity_labels(
                {str(row[0].disease_entity_id) for row in row_values if row[0].disease_entity_id},
                EntityType.DISEASE,
            )
        )
        trial_counts, drugs_with_results, result_evaluations, deal_counts, deal_currencies = self._pipeline_signal_maps(
            [row[0].drug_entity_id for row in row_values]
        )

        items = [
            CompetitiveProgramRead(
                id=program.id,
                drug_entity_id=identity_id,
                drug_name=identity_name,
                target_entity_id=(primary_targets[program.id].entity_id if program.id in primary_targets else None),
                target_name=primary_targets[program.id].name if program.id in primary_targets else target_name,
                targets=target_map.get(program.id, []),
                target_combination_key=target_combination_keys.get(program.id),
                disease_entity_id=(
                    program.disease_entity_id
                    if self.include_unpublished
                    else disease_identities.get(str(program.disease_entity_id), (None, disease_name))[0]
                ),
                disease_name=(
                    disease_name
                    if self.include_unpublished
                    else disease_identities.get(str(program.disease_entity_id), (None, disease_name))[1]
                ),
                organization_entity_id=(
                    primary_organizations[program.id].entity_id
                    if program.id in primary_organizations
                    else program.organization_entity_id
                    if self.include_unpublished
                    else None
                ),
                organization_name=(
                    primary_organizations[program.id].name if program.id in primary_organizations else organization_name
                ),
                organizations=organization_map.get(program.id, []),
                modality=public_program_modality(program.modality, program.drug_category),
                innovation_type=program.innovation_type,
                therapeutic_area=program.therapeutic_area,
                drug_category=public_program_drug_category(program.modality, program.drug_category),
                mechanism_of_action=program.mechanism_of_action,
                phase=program.phase.value,
                status_detail=program.status_detail,
                program_status=program.program_status,
                status_date=program.status_date,
                geography=program.geography,
                global_phase=program.global_phase,
                china_phase=program.china_phase,
                global_phase_started_at=program.global_phase_started_at,
                china_phase_started_at=program.china_phase_started_at,
                development_rights_regions=program.development_rights_regions or [],
                commercialization_rights_regions=program.commercialization_rights_regions or [],
                program_tags=public_program_tags(program.program_tags),
                status_history=program.status_history or [],
                milestones=program.milestones or [],
                clinical_trial_count=trial_counts.get(program.drug_entity_id, 0),
                has_clinical_results=program.drug_entity_id in drugs_with_results,
                clinical_result_evaluations=result_evaluations.get(program.drug_entity_id, []),
                deal_count=deal_counts.get(program.drug_entity_id, 0),
                deal_currencies=deal_currencies.get(program.drug_entity_id, []),
                source_document_id=program.source_document_id,
            )
            for (
                program,
                raw_drug_name,
                target_name,
                disease_name,
                organization_name,
                identity_id,
                identity_name,
            ) in row_values
        ]
        if result_grain == "drug":
            programs_by_drug: dict[str, list[CompetitiveProgramRead]] = defaultdict(list)
            for item in items:
                programs_by_drug[item.drug_entity_id].append(item)

            def highest_phase(programs: Sequence[CompetitiveProgramRead], field: str) -> str | None:
                values = [getattr(program, field) for program in programs if getattr(program, field)]
                return max(values, key=lambda value: _DEVELOPMENT_PHASE_RANK.get(str(value), -2), default=None)

            def phase_started_at(
                programs: Sequence[CompetitiveProgramRead],
                phase_field: str,
                date_field: str,
                highest: str | None,
            ) -> datetime | None:
                values = [
                    getattr(program, date_field)
                    for program in programs
                    if getattr(program, phase_field) == highest and getattr(program, date_field) is not None
                ]
                return min(values, default=None)

            aggregated_items: list[CompetitiveProgramRead] = []
            for drug_id in ordered_drug_ids:
                programs = programs_by_drug.get(drug_id, [])
                if not programs:
                    continue
                representative = max(
                    programs,
                    key=lambda item: (
                        _DEVELOPMENT_PHASE_RANK.get(item.phase, -2),
                        item.status_date or datetime.min.replace(tzinfo=UTC),
                        item.id,
                    ),
                )
                highest_overall = highest_phase(programs, "phase") or representative.phase
                highest_global = highest_phase(programs, "global_phase")
                highest_china = highest_phase(programs, "china_phase")
                targets = list({target.entity_id: target for item in programs for target in item.targets}.values())
                organizations = list(
                    {
                        organization.entity_id: organization for item in programs for organization in item.organizations
                    }.values()
                )
                status_counts = Counter(item.program_status or "unknown" for item in programs)
                aggregate_status = (
                    "active" if status_counts["active"] else "unknown" if status_counts["unknown"] else "inactive"
                )
                aggregated_items.append(
                    representative.model_copy(
                        update={
                            "targets": targets,
                            "target_combination_key": "|".join(sorted(target.entity_id for target in targets)) or None,
                            "disease_entity_id": None,
                            "disease_name": None,
                            "organizations": organizations,
                            "modality": None,
                            "mechanism_of_action": None,
                            "phase": highest_overall,
                            "global_phase": highest_global,
                            "china_phase": highest_china,
                            "global_phase_started_at": phase_started_at(
                                programs, "global_phase", "global_phase_started_at", highest_global
                            ),
                            "china_phase_started_at": phase_started_at(
                                programs, "china_phase", "china_phase_started_at", highest_china
                            ),
                            "program_status": aggregate_status,
                            "status_date": max(
                                (item.status_date for item in programs if item.status_date is not None),
                                default=None,
                            ),
                            "project_count": len(programs),
                            "indications": [
                                ProgramIndicationRead(
                                    program_id=item.id,
                                    disease_entity_id=item.disease_entity_id,
                                    disease_name=item.disease_name,
                                    phase=item.phase,
                                    global_phase=item.global_phase,
                                    china_phase=item.china_phase,
                                    global_phase_started_at=item.global_phase_started_at,
                                    china_phase_started_at=item.china_phase_started_at,
                                    program_status=item.program_status,
                                    status_date=item.status_date,
                                    geography=item.geography,
                                )
                                for item in sorted(
                                    programs,
                                    key=lambda item: (
                                        -_DEVELOPMENT_PHASE_RANK.get(item.phase, -2),
                                        item.disease_name or "",
                                        item.id,
                                    ),
                                )
                            ],
                            "modalities": sorted({item.modality for item in programs if item.modality}),
                            "mechanisms_of_action": sorted(
                                {item.mechanism_of_action for item in programs if item.mechanism_of_action}
                            ),
                            "innovation_types": sorted(
                                {item.innovation_type for item in programs if item.innovation_type}
                            ),
                            "therapeutic_areas": sorted(
                                {item.therapeutic_area for item in programs if item.therapeutic_area}
                            ),
                            "drug_categories": sorted({item.drug_category for item in programs if item.drug_category}),
                            "program_status_counts": dict(status_counts),
                            "clinical_trial_count": max(item.clinical_trial_count for item in programs),
                            "has_clinical_results": any(item.has_clinical_results for item in programs),
                            "clinical_result_evaluations": sorted(
                                {value for item in programs for value in item.clinical_result_evaluations}
                            ),
                            "deal_count": max(item.deal_count for item in programs),
                            "deal_currencies": sorted({value for item in programs for value in item.deal_currencies}),
                        }
                    )
                )
            items = aggregated_items
        return PipelineSearchResult(
            query_schema_version="pharma.pipeline.search.v13",
            applied_filters=self._applied_filters(
                ("q", "contains", query.strip() if query else None),
                ("modality", "in", modality),
                ("innovation_type", "in", innovation_type),
                ("therapeutic_area", "in", therapeutic_area),
                ("drug_category", "in", drug_category),
                ("program_status", "eq", program_status),
                ("organization_role", "eq", organization_role),
                ("organization_type", "eq", organization_type),
                ("organization_country_region", "eq", organization_country_region),
                ("phase", "eq", phase),
                ("geography", "eq", geography),
                ("status_date_from", "gte", status_date_from.isoformat() if status_date_from else None),
                ("status_date_to", "lte", status_date_to.isoformat() if status_date_to else None),
                ("drug_entity_id", "eq", drug_entity_id),
                ("target_entity_id", "eq", target_entity_id),
                ("target_combination_key", "eq", target_combination_key),
                ("disease_entity_id", "eq", disease_entity_id),
                ("organization_entity_id", "eq", organization_entity_id),
                ("global_phase", "eq", global_phase),
                ("china_phase", "eq", china_phase),
                (
                    "global_phase_started_from",
                    "gte",
                    global_phase_started_from.isoformat() if global_phase_started_from else None,
                ),
                (
                    "global_phase_started_to",
                    "lte",
                    global_phase_started_to.isoformat() if global_phase_started_to else None,
                ),
                (
                    "china_phase_started_from",
                    "gte",
                    china_phase_started_from.isoformat() if china_phase_started_from else None,
                ),
                (
                    "china_phase_started_to",
                    "lte",
                    china_phase_started_to.isoformat() if china_phase_started_to else None,
                ),
                ("development_rights_region", "eq", development_rights_region),
                ("commercialization_rights_region", "eq", commercialization_rights_region),
                ("program_tag", "in", public_program_tags(program_tag)),
                ("milestone_type", "eq", milestone_type),
                ("milestone_from", "gte", milestone_from.isoformat() if milestone_from else None),
                ("milestone_to", "lte", milestone_to.isoformat() if milestone_to else None),
                ("has_clinical_results", "eq", has_clinical_results),
                ("clinical_result_evaluation", "eq", clinical_result_evaluation),
                ("has_deal", "eq", has_deal),
                ("deal_currency", "eq", deal_currency),
                (
                    "deal_total_potential_amount_min",
                    "gte",
                    deal_total_potential_amount_min,
                ),
                (
                    "deal_total_potential_amount_max",
                    "lte",
                    deal_total_potential_amount_max,
                ),
            ),
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=effective_sort[0].field,
            sort_direction=effective_sort[0].direction,
            sort=_sort_criteria_read(effective_sort),
            facets=facets,
            landscape=landscape,
            result_grain=result_grain,
            project_total=project_total,
            as_of=datetime.now(UTC),
            warnings=["暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。"],
        )

    def _pipeline_signal_maps(
        self,
        drug_entity_ids: list[str],
    ) -> tuple[
        dict[str, int],
        set[str],
        dict[str, list[TrialResultEvaluation]],
        dict[str, int],
        dict[str, list[str]],
    ]:
        drug_ids = set(drug_entity_ids)
        if not drug_ids:
            return {}, set(), {}, {}, {}
        identity_members = {drug_id: self._entity_identity_member_ids(drug_id, EntityType.DRUG) for drug_id in drug_ids}
        all_identity_ids = set().union(*identity_members.values())
        trial_rows = self.session.execute(
            select(
                ClinicalTrialEntityRole.entity_id,
                ClinicalTrialEntityRole.trial_id,
                ClinicalTrialProfile.has_results,
            )
            .join(
                ClinicalTrialProfile,
                and_(
                    ClinicalTrialProfile.tenant_id == self.tenant_id,
                    ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
                ),
            )
            .where(
                ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                ClinicalTrialEntityRole.entity_id.in_(all_identity_ids),
                ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
            )
            .distinct()
        ).all()
        raw_trial_ids: dict[str, set[str]] = {}
        raw_drugs_with_results: set[str] = set()
        for raw_drug_id, trial_id, has_results in trial_rows:
            raw_id = str(raw_drug_id)
            raw_trial_ids.setdefault(raw_id, set()).add(str(trial_id))
            if has_results:
                raw_drugs_with_results.add(raw_id)
        trial_counts = {
            drug_id: len(set().union(*(raw_trial_ids.get(member_id, set()) for member_id in members)))
            for drug_id, members in identity_members.items()
        }
        drugs_with_results = {
            drug_id for drug_id, members in identity_members.items() if members & raw_drugs_with_results
        }
        evaluation_rows = self.session.execute(
            select(ClinicalTrialEntityRole.entity_id, ClinicalTrialProfile.result_evaluation)
            .join(
                ClinicalTrialProfile,
                and_(
                    ClinicalTrialProfile.tenant_id == self.tenant_id,
                    ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
                ),
            )
            .where(
                ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                ClinicalTrialEntityRole.entity_id.in_(all_identity_ids),
                ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
                ClinicalTrialProfile.has_results.is_(True),
                ClinicalTrialProfile.result_evaluation.is_not(None),
            )
            .distinct()
        ).all()
        evaluation_sets: dict[str, set[TrialResultEvaluation]] = {}
        raw_evaluations: dict[str, set[TrialResultEvaluation]] = {}
        for raw_drug_id, evaluation in evaluation_rows:
            raw_evaluations.setdefault(str(raw_drug_id), set()).add(TrialResultEvaluation(str(evaluation)))
        for drug_id, members in identity_members.items():
            for member_id in members:
                evaluation_sets.setdefault(drug_id, set()).update(raw_evaluations.get(member_id, set()))
        evaluation_rank = {value: index for index, value in enumerate(_TRIAL_RESULT_EVALUATION_ORDER)}
        evaluations = {
            drug_id: sorted(values, key=evaluation_rank.__getitem__) for drug_id, values in evaluation_sets.items()
        }
        deal_rows = self.session.execute(
            select(
                DealAssetAssociation.asset_entity_id,
                func.count(func.distinct(DealAssetAssociation.deal_id)),
            )
            .join(
                DealProfile,
                and_(
                    DealProfile.tenant_id == self.tenant_id,
                    DealProfile.id == DealAssetAssociation.deal_id,
                ),
            )
            .where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.asset_entity_id.in_(drug_ids),
            )
            .group_by(DealAssetAssociation.asset_entity_id)
        ).all()
        deal_counts = {str(drug_id): int(count) for drug_id, count in deal_rows}
        currency_rows = self.session.execute(
            select(DealAssetAssociation.asset_entity_id, DealProfile.currency)
            .join(
                DealProfile,
                and_(
                    DealProfile.tenant_id == self.tenant_id,
                    DealProfile.id == DealAssetAssociation.deal_id,
                ),
            )
            .where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.asset_entity_id.in_(drug_ids),
                DealProfile.currency.is_not(None),
            )
            .distinct()
        ).all()
        currency_sets: dict[str, set[str]] = {}
        for drug_id, currency in currency_rows:
            currency_sets.setdefault(str(drug_id), set()).add(str(currency))
        currencies = {drug_id: sorted(values) for drug_id, values in currency_sets.items()}
        return trial_counts, drugs_with_results, evaluations, deal_counts, currencies

    def _pipeline_signal_facets(self, source: Any, id_name: str) -> dict[str, dict[str, int]]:
        count_expression = func.count(func.distinct(source.c[id_name]))
        result_signal = case(
            (self._pipeline_trial_exists(source.c.drug_entity_id, require_results=True), "true"),
            else_="false",
        ).label("has_clinical_results")
        deal_signal = case(
            (self._pipeline_deal_exists(source.c.drug_entity_id), "true"),
            else_="false",
        ).label("has_deal")
        facets: dict[str, dict[str, int]] = {}
        for name, signal in (("has_clinical_results", result_signal), ("has_deal", deal_signal)):
            rows = self.session.execute(
                select(signal, count_expression).select_from(source).group_by(signal).order_by(signal)
            ).all()
            facets[name] = {str(value): int(count) for value, count in rows}
        evaluation_rows = self.session.execute(
            select(
                ClinicalTrialProfile.result_evaluation,
                count_expression,
            )
            .select_from(source)
            .join(
                ClinicalTrialEntityRole,
                and_(
                    ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                    ClinicalTrialEntityRole.entity_id == source.c.drug_entity_id,
                    ClinicalTrialEntityRole.role.in_(_TRIAL_DRUG_ROLES),
                ),
            )
            .join(
                ClinicalTrialProfile,
                and_(
                    ClinicalTrialProfile.tenant_id == self.tenant_id,
                    ClinicalTrialProfile.id == ClinicalTrialEntityRole.trial_id,
                    ClinicalTrialProfile.has_results.is_(True),
                ),
            )
            .where(ClinicalTrialProfile.result_evaluation.is_not(None))
            .group_by(ClinicalTrialProfile.result_evaluation)
            .order_by(count_expression.desc(), ClinicalTrialProfile.result_evaluation)
        ).all()
        facets["clinical_result_evaluation"] = {str(evaluation): int(count) for evaluation, count in evaluation_rows}
        currency_rows = self.session.execute(
            select(DealProfile.currency, count_expression)
            .select_from(source)
            .join(
                DealAssetAssociation,
                and_(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.asset_entity_id == source.c.drug_entity_id,
                ),
            )
            .join(
                DealProfile,
                and_(
                    DealProfile.tenant_id == self.tenant_id,
                    DealProfile.id == DealAssetAssociation.deal_id,
                ),
            )
            .where(DealProfile.currency.is_not(None))
            .group_by(DealProfile.currency)
            .order_by(count_expression.desc(), DealProfile.currency)
        ).all()
        facets["deal_currency"] = {str(currency): int(count) for currency, count in currency_rows}
        return facets

    def programs_for_entity(self, entity_id: str, limit: int, offset: int = 0) -> list[CompetitiveProgramRead]:
        return self._read_programs(self._program_filters(entity_id), limit, offset)

    def _read_programs(
        self, filters: list[ColumnElement[bool]], limit: int, offset: int
    ) -> list[CompetitiveProgramRead]:
        drug = Entity.__table__.alias("drug")
        target = Entity.__table__.alias("target")
        disease = Entity.__table__.alias("disease")
        organization = Entity.__table__.alias("organization")
        rows = self.session.execute(
            select(
                DevelopmentProgram,
                drug.c.name.label("drug_name"),
                target.c.name.label("target_name"),
                disease.c.name.label("disease_name"),
                organization.c.name.label("organization_name"),
            )
            .join(drug, drug.c.id == DevelopmentProgram.drug_entity_id)
            .outerjoin(target, target.c.id == DevelopmentProgram.target_entity_id)
            .outerjoin(disease, disease.c.id == DevelopmentProgram.disease_entity_id)
            .outerjoin(organization, organization.c.id == DevelopmentProgram.organization_entity_id)
            .where(*filters)
            .order_by(
                DevelopmentProgram.status_date.desc().nullslast(),
                DevelopmentProgram.id,
            )
            .limit(limit)
            .offset(offset)
        ).all()
        target_map = self._program_target_map(
            [program for program, *_ in rows],
            {program.id: (program.target_entity_id, target_name) for program, _, target_name, _, _ in rows},
        )
        target_map = self._visible_program_target_map(target_map)
        primary_targets = {program_id: targets[0] for program_id, targets in target_map.items() if targets}
        target_combination_keys = self._canonical_target_combination_keys(target_map)
        organization_map = self._program_organization_map(
            [program for program, *_ in rows],
            {
                program.id: (program.organization_entity_id, organization_name)
                for program, _, _, _, organization_name in rows
            },
        )
        organization_map = self._visible_program_organization_map(organization_map)
        primary_organizations = {
            program_id: organizations[0] for program_id, organizations in organization_map.items() if organizations
        }
        drug_identities = (
            {}
            if self.include_unpublished
            else self._published_entity_identity_labels(
                {str(program.drug_entity_id) for program, *_ in rows},
                EntityType.DRUG,
            )
        )
        disease_identities = (
            {}
            if self.include_unpublished
            else self._published_entity_identity_labels(
                {str(program.disease_entity_id) for program, *_ in rows if program.disease_entity_id},
                EntityType.DISEASE,
            )
        )
        trial_counts, drugs_with_results, result_evaluations, deal_counts, deal_currencies = self._pipeline_signal_maps(
            [program.drug_entity_id for program, *_ in rows]
        )
        return [
            CompetitiveProgramRead(
                id=program.id,
                drug_entity_id=(
                    program.drug_entity_id
                    if self.include_unpublished
                    else drug_identities[str(program.drug_entity_id)][0]
                ),
                drug_name=(drug_name if self.include_unpublished else drug_identities[str(program.drug_entity_id)][1]),
                target_entity_id=(
                    primary_targets[program.id].entity_id
                    if program.id in primary_targets
                    else program.target_entity_id
                    if self.include_unpublished
                    else None
                ),
                target_name=(primary_targets[program.id].name if program.id in primary_targets else target_name),
                targets=target_map.get(program.id, []),
                target_combination_key=(
                    program.target_combination_key or program.target_entity_id
                    if self.include_unpublished
                    else target_combination_keys.get(program.id)
                ),
                disease_entity_id=(
                    program.disease_entity_id
                    if self.include_unpublished
                    else disease_identities.get(str(program.disease_entity_id), (None, disease_name))[0]
                ),
                disease_name=(
                    disease_name
                    if self.include_unpublished
                    else disease_identities.get(str(program.disease_entity_id), (None, disease_name))[1]
                ),
                organization_entity_id=(
                    primary_organizations[program.id].entity_id
                    if program.id in primary_organizations
                    else program.organization_entity_id
                    if self.include_unpublished
                    else None
                ),
                organization_name=(
                    primary_organizations[program.id].name if program.id in primary_organizations else organization_name
                ),
                organizations=organization_map.get(program.id, []),
                modality=public_program_modality(program.modality, program.drug_category),
                innovation_type=program.innovation_type,
                therapeutic_area=program.therapeutic_area,
                drug_category=public_program_drug_category(program.modality, program.drug_category),
                mechanism_of_action=program.mechanism_of_action,
                phase=program.phase.value,
                status_detail=program.status_detail,
                program_status=program.program_status,
                status_date=program.status_date,
                geography=program.geography,
                global_phase=program.global_phase,
                china_phase=program.china_phase,
                global_phase_started_at=program.global_phase_started_at,
                china_phase_started_at=program.china_phase_started_at,
                development_rights_regions=program.development_rights_regions or [],
                commercialization_rights_regions=program.commercialization_rights_regions or [],
                program_tags=public_program_tags(program.program_tags),
                status_history=program.status_history or [],
                milestones=program.milestones or [],
                clinical_trial_count=trial_counts.get(program.drug_entity_id, 0),
                has_clinical_results=program.drug_entity_id in drugs_with_results,
                clinical_result_evaluations=result_evaluations.get(program.drug_entity_id, []),
                deal_count=deal_counts.get(program.drug_entity_id, 0),
                deal_currencies=deal_currencies.get(program.drug_entity_id, []),
                source_document_id=program.source_document_id,
            )
            for program, drug_name, target_name, disease_name, organization_name in rows
        ]

    def structures(
        self,
        entity_id: str | None,
        inchi_key: str | None,
        limit: int,
        offset: int = 0,
    ) -> list[CompoundStructureRead]:
        filters = self._structure_filters(entity_id, inchi_key)
        rows = self.session.scalars(
            select(CompoundStructure).where(*filters).order_by(CompoundStructure.id).limit(limit).offset(offset)
        ).all()
        return [CompoundStructureRead.model_validate(row) for row in rows]

    def structures_for_target(
        self,
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
            CompoundStructure.tenant_id == self.tenant_id,
            CompoundStructure.entity_id == target_entity_id,
        )
        activity_compounds = select(ActivityMeasurement.compound_entity_id.label("compound_entity_id")).where(
            ActivityMeasurement.tenant_id == self.tenant_id,
            ActivityMeasurement.target_entity_id == target_entity_id,
        )
        program_compounds = select(DevelopmentProgram.drug_entity_id.label("compound_entity_id")).where(
            DevelopmentProgram.tenant_id == self.tenant_id,
            DevelopmentProgram.drug_entity_id.is_not(None),
            or_(
                DevelopmentProgram.target_entity_id == target_entity_id,
                self._program_target_exists(target_entity_id),
            ),
        )
        compound_ids = union(direct_compounds, activity_compounds, program_compounds).subquery()
        rows = self.session.scalars(
            select(CompoundStructure)
            .where(
                CompoundStructure.tenant_id == self.tenant_id,
                CompoundStructure.entity_id.in_(select(compound_ids.c.compound_entity_id)),
            )
            .order_by(CompoundStructure.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [CompoundStructureRead.model_validate(row) for row in rows]

    def clinical_trials(
        self,
        entity_id: str | None,
        query: str | None,
        limit: int,
        offset: int = 0,
        registry: str | None = None,
        overall_status: str | None = None,
        phase: str | None = None,
        study_type: str | None = None,
        has_results: bool | None = None,
    ) -> list[ClinicalTrialRead]:
        filters = self._clinical_trial_filters(
            entity_id,
            query,
            registry=registry,
            overall_status=overall_status,
            phase=phase,
            study_type=study_type,
            has_results=has_results,
        )
        rows = self.session.scalars(
            select(ClinicalTrialProfile)
            .where(*filters)
            .order_by(
                ClinicalTrialProfile.last_update_posted.desc().nullslast(),
                ClinicalTrialProfile.id,
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return [ClinicalTrialRead.model_validate(row) for row in rows]

    def clinical_trial_saved_search_matches_entity(
        self,
        entity_id: str,
        query: ClinicalTrialSavedSearchQuery,
    ) -> bool:
        def start(value: Any) -> datetime | None:
            return datetime.combine(value, time.min, tzinfo=UTC) if value else None

        def end(value: Any) -> datetime | None:
            return datetime.combine(value, time.max, tzinfo=UTC) if value else None

        filters = self._clinical_trial_filters(
            entity_id,
            query.q,
            registry=query.registry,
            overall_status=query.status,
            phase=query.phase,
            study_type=query.study_type,
            acronym=query.acronym,
            initiation_type=query.initiation_type,
            therapy_line=query.therapy_line,
            has_results=query.has_results,
            results_posted_from=start(query.results_posted_from),
            results_posted_to=end(query.results_posted_to),
            result_evaluation=query.result_evaluation.value if query.result_evaluation else None,
            investigational_drug=query.investigational_drug,
            combination_drug=query.combination_drug,
            investigational_target=query.investigational_target,
            combination_target=query.combination_target,
            investigational_drug_entity_ids=query.investigational_drug_entity_ids,
            combination_drug_entity_ids=query.combination_drug_entity_ids,
            investigational_target_entity_ids=query.investigational_target_entity_ids,
            combination_target_entity_ids=query.combination_target_entity_ids,
            linked_drug_modality=query.linked_drug_modality,
            linked_drug_innovation_type=query.linked_drug_innovation_type,
            linked_drug_category=query.linked_drug_category,
            linked_drug_program_tag=query.linked_drug_program_tag,
            linked_drug_global_phase=query.linked_drug_global_phase,
            linked_drug_organization_country_region=query.linked_drug_organization_country_region,
            role_entity_id=query.role_entity_id,
            role_entity_ids=query.role_entity_ids,
            role_entity_role=query.role_entity_role.value if query.role_entity_role else None,
            has_key_result=query.has_key_result,
            publication_id=query.publication_id,
            conference=query.conference,
            disclosed_from=start(query.disclosed_from),
            disclosed_to=end(query.disclosed_to),
        )
        statement = select(ClinicalTrialProfile.id).where(*filters).limit(1)
        return self.session.scalar(statement.with_only_columns(literal(True))) is True

    def search_clinical_trials(
        self,
        query: str | None,
        registry: str | None,
        overall_status: str | None,
        phase: str | None,
        study_type: str | None,
        has_results: bool | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        results_posted_from: datetime | None = None,
        results_posted_to: datetime | None = None,
        result_evaluation: str | None = None,
        acronym: str | None = None,
        initiation_type: str | None = None,
        therapy_line: str | None = None,
        investigational_drug: str | None = None,
        combination_drug: str | None = None,
        investigational_target: str | None = None,
        combination_target: str | None = None,
        investigational_drug_entity_ids: list[str] | None = None,
        combination_drug_entity_ids: list[str] | None = None,
        investigational_target_entity_ids: list[str] | None = None,
        combination_target_entity_ids: list[str] | None = None,
        linked_drug_modality: list[str] | None = None,
        linked_drug_innovation_type: list[str] | None = None,
        linked_drug_category: list[str] | None = None,
        linked_drug_program_tag: list[str] | None = None,
        linked_drug_global_phase: str | None = None,
        linked_drug_organization_country_region: str | None = None,
        role_entity_id: str | None = None,
        role_entity_ids: list[str] | None = None,
        role_entity_role: str | None = None,
        has_key_result: bool | None = None,
        publication_id: str | None = None,
        conference: str | None = None,
        disclosed_from: datetime | None = None,
        disclosed_to: datetime | None = None,
        sort_by: ClinicalTrialSortField = "last_update_posted",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[ClinicalTrialSortField]] | None = None,
    ) -> ClinicalTrialSearchResult:
        effective_sort = validate_sort_clauses(
            sort,
            CLINICAL_TRIAL_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        filters = self._clinical_trial_filters(
            entity_id,
            query,
            registry=registry,
            overall_status=overall_status,
            phase=phase,
            study_type=study_type,
            acronym=acronym,
            initiation_type=initiation_type,
            therapy_line=therapy_line,
            has_results=has_results,
            results_posted_from=results_posted_from,
            results_posted_to=results_posted_to,
            result_evaluation=result_evaluation,
            investigational_drug=investigational_drug,
            combination_drug=combination_drug,
            investigational_target=investigational_target,
            combination_target=combination_target,
            investigational_drug_entity_ids=investigational_drug_entity_ids,
            combination_drug_entity_ids=combination_drug_entity_ids,
            investigational_target_entity_ids=investigational_target_entity_ids,
            combination_target_entity_ids=combination_target_entity_ids,
            linked_drug_modality=linked_drug_modality,
            linked_drug_innovation_type=linked_drug_innovation_type,
            linked_drug_category=linked_drug_category,
            linked_drug_program_tag=linked_drug_program_tag,
            linked_drug_global_phase=linked_drug_global_phase,
            linked_drug_organization_country_region=linked_drug_organization_country_region,
            role_entity_id=role_entity_id,
            role_entity_ids=role_entity_ids,
            role_entity_role=role_entity_role,
            has_key_result=has_key_result,
            publication_id=publication_id,
            conference=conference,
            disclosed_from=disclosed_from,
            disclosed_to=disclosed_to,
        )
        items = self._clinical_trial_search_items(
            filters,
            limit,
            offset,
            sort=effective_sort,
        )
        facet_source = (
            select(
                ClinicalTrialProfile.id.label("trial_id"),
                ClinicalTrialProfile.registry_name.label("registry"),
                ClinicalTrialProfile.overall_status.label("overall_status"),
                ClinicalTrialProfile.study_type.label("study_type"),
                ClinicalTrialProfile.initiation_type.label("initiation_type"),
                ClinicalTrialProfile.therapy_lines.label("therapy_lines"),
                ClinicalTrialProfile.phases.label("phases"),
                ClinicalTrialProfile.has_results.label("has_results"),
                ClinicalTrialProfile.result_evaluation.label("result_evaluation"),
                func.coalesce(
                    select(func.max(ClinicalTrialResultDisclosure.disclosed_at))
                    .where(
                        ClinicalTrialResultDisclosure.tenant_id == self.tenant_id,
                        ClinicalTrialResultDisclosure.trial_id == ClinicalTrialProfile.id,
                    )
                    .scalar_subquery(),
                    ClinicalTrialProfile.results_first_posted,
                ).label("published_at"),
                select(ClinicalTrialResultDisclosure.id)
                .where(
                    ClinicalTrialResultDisclosure.tenant_id == self.tenant_id,
                    ClinicalTrialResultDisclosure.trial_id == ClinicalTrialProfile.id,
                    ClinicalTrialResultDisclosure.is_key_result.is_(True),
                )
                .exists()
                .label("has_key_result"),
            )
            .where(*filters)
            .subquery()
        )
        total = self.session.scalar(select(func.count()).select_from(facet_source)) or 0
        facets = {
            name: self._scalar_facet_counts(facet_source, name)
            for name in (
                "registry",
                "overall_status",
                "study_type",
                "initiation_type",
                "has_results",
                "result_evaluation",
                "has_key_result",
            )
        }
        facets["phase"] = self._json_array_facets(facet_source, "phases", "trial_id")
        facets["therapy_line"] = self._json_array_facets(facet_source, "therapy_lines", "trial_id")
        facets.update(
            {
                name: counts
                for name, counts in self._clinical_trial_linked_drug_program_facets(facet_source).items()
                if counts
            }
        )
        landscape = self._clinical_trial_landscape(facet_source, total)
        return ClinicalTrialSearchResult(
            query_schema_version="pharma.clinical_trial.search.v10",
            applied_filters=self._applied_filters(
                ("entity_id", "eq", entity_id),
                ("q", "contains", query.strip() if query else None),
                ("registry", "eq", registry),
                ("status", "eq", overall_status),
                ("phase", "eq", phase),
                ("study_type", "eq", study_type),
                ("acronym", "contains", acronym),
                ("initiation_type", "eq", initiation_type),
                ("therapy_line", "eq", therapy_line),
                ("has_results", "eq", has_results),
                ("result_evaluation", "eq", result_evaluation),
                ("investigational_drug", "contains", investigational_drug),
                ("combination_drug", "contains", combination_drug),
                ("investigational_target", "contains", investigational_target),
                ("combination_target", "contains", combination_target),
                ("investigational_drug_entity_ids", "in", investigational_drug_entity_ids),
                ("combination_drug_entity_ids", "in", combination_drug_entity_ids),
                ("investigational_target_entity_ids", "in", investigational_target_entity_ids),
                ("combination_target_entity_ids", "in", combination_target_entity_ids),
                ("linked_drug_modality", "in", linked_drug_modality),
                ("linked_drug_innovation_type", "in", linked_drug_innovation_type),
                ("linked_drug_category", "in", linked_drug_category),
                ("linked_drug_program_tag", "in", public_program_tags(linked_drug_program_tag)),
                ("linked_drug_global_phase", "eq", linked_drug_global_phase),
                (
                    "linked_drug_organization_country_region",
                    "eq",
                    linked_drug_organization_country_region,
                ),
                ("role_entity_id", "eq", role_entity_id),
                ("role_entity_ids", "in", role_entity_ids),
                ("role_entity_role", "eq", role_entity_role),
                ("has_key_result", "eq", has_key_result),
                ("publication_id", "eq", publication_id),
                ("conference", "contains", conference),
                ("disclosed_from", "gte", disclosed_from.isoformat() if disclosed_from else None),
                ("disclosed_to", "lte", disclosed_to.isoformat() if disclosed_to else None),
                (
                    "results_posted_from",
                    "gte",
                    results_posted_from.isoformat() if results_posted_from else None,
                ),
                ("results_posted_to", "lte", results_posted_to.isoformat() if results_posted_to else None),
            ),
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=effective_sort[0].field,
            sort_direction=effective_sort[0].direction,
            sort=_sort_criteria_read(effective_sort),
            facets=facets,
            landscape=landscape,
            as_of=datetime.now(UTC),
            warnings=["未观察到试验不代表全球不存在；结果受数据授权、注册平台时效和治理状态限制。"],
        )

    def clinical_trial_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        registry: str | None,
        overall_status: str | None,
        phase: str | None,
        study_type: str | None,
        has_results: bool | None,
        limit: int,
        offset: int = 0,
        *,
        results_posted_from: datetime | None = None,
        results_posted_to: datetime | None = None,
        result_evaluation: str | None = None,
        acronym: str | None = None,
        initiation_type: str | None = None,
        therapy_line: str | None = None,
        investigational_drug: str | None = None,
        combination_drug: str | None = None,
        investigational_target: str | None = None,
        combination_target: str | None = None,
        investigational_drug_entity_ids: list[str] | None = None,
        combination_drug_entity_ids: list[str] | None = None,
        investigational_target_entity_ids: list[str] | None = None,
        combination_target_entity_ids: list[str] | None = None,
        linked_drug_modality: list[str] | None = None,
        linked_drug_innovation_type: list[str] | None = None,
        linked_drug_category: list[str] | None = None,
        linked_drug_program_tag: list[str] | None = None,
        linked_drug_global_phase: str | None = None,
        linked_drug_organization_country_region: str | None = None,
        role_entity_id: str | None = None,
        role_entity_ids: list[str] | None = None,
        role_entity_role: str | None = None,
        has_key_result: bool | None = None,
        publication_id: str | None = None,
        conference: str | None = None,
        disclosed_from: datetime | None = None,
        disclosed_to: datetime | None = None,
        sort_by: ClinicalTrialSortField = "last_update_posted",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[ClinicalTrialSortField]] | None = None,
    ) -> list[ClinicalTrialSearchItemRead]:
        filters = self._clinical_trial_filters(
            entity_id,
            query,
            registry=registry,
            overall_status=overall_status,
            phase=phase,
            study_type=study_type,
            acronym=acronym,
            initiation_type=initiation_type,
            therapy_line=therapy_line,
            has_results=has_results,
            results_posted_from=results_posted_from,
            results_posted_to=results_posted_to,
            result_evaluation=result_evaluation,
            investigational_drug=investigational_drug,
            combination_drug=combination_drug,
            investigational_target=investigational_target,
            combination_target=combination_target,
            investigational_drug_entity_ids=investigational_drug_entity_ids,
            combination_drug_entity_ids=combination_drug_entity_ids,
            investigational_target_entity_ids=investigational_target_entity_ids,
            combination_target_entity_ids=combination_target_entity_ids,
            linked_drug_modality=linked_drug_modality,
            linked_drug_innovation_type=linked_drug_innovation_type,
            linked_drug_category=linked_drug_category,
            linked_drug_program_tag=linked_drug_program_tag,
            linked_drug_global_phase=linked_drug_global_phase,
            linked_drug_organization_country_region=linked_drug_organization_country_region,
            role_entity_id=role_entity_id,
            role_entity_ids=role_entity_ids,
            role_entity_role=role_entity_role,
            has_key_result=has_key_result,
            publication_id=publication_id,
            conference=conference,
            disclosed_from=disclosed_from,
            disclosed_to=disclosed_to,
        )
        return self._clinical_trial_search_items(
            filters,
            limit,
            offset,
            sort=validate_sort_clauses(
                sort,
                CLINICAL_TRIAL_SORT_FIELDS,
                default_field=sort_by,
                default_direction=sort_direction,
            ),
        )

    def clinical_trial_detail(self, trial_id: str) -> ClinicalTrialDetailRead | None:
        row = self.session.scalar(
            select(ClinicalTrialProfile).where(
                ClinicalTrialProfile.tenant_id == self.tenant_id,
                ClinicalTrialProfile.id == trial_id,
                self._published_entity_exists(ClinicalTrialProfile.entity_id),
            )
        )
        if row is None:
            return None
        linked_entities = self._clinical_trial_linked_entities([row.entity_id]).get(row.entity_id, [])
        entity_roles = self._clinical_trial_entity_roles([row.id])[row.id]
        disclosures = self._clinical_trial_result_disclosures([row.id])[row.id]
        return ClinicalTrialDetailRead(
            **ClinicalTrialRead.model_validate(row).model_dump(),
            linked_entities=linked_entities,
            entity_roles=entity_roles,
            key_result_count=sum(1 for disclosure in disclosures if disclosure.is_key_result),
            latest_result_disclosure=disclosures[0] if disclosures else None,
            result_disclosures=disclosures,
        )

    def _clinical_trial_search_items(
        self,
        filters: list[ColumnElement[bool]],
        limit: int,
        offset: int,
        *,
        sort_by: ClinicalTrialSortField = "last_update_posted",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[ClinicalTrialSortField]] | None = None,
    ) -> list[ClinicalTrialSearchItemRead]:
        effective_sort = validate_sort_clauses(
            sort,
            CLINICAL_TRIAL_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        sort_expressions: dict[ClinicalTrialSortField, Any] = {
            "last_update_posted": ClinicalTrialProfile.last_update_posted,
            "registry_id": func.lower(ClinicalTrialProfile.registry_id),
            "has_results": ClinicalTrialProfile.has_results,
            "result_evaluation": func.lower(ClinicalTrialProfile.result_evaluation),
            "overall_status": func.lower(ClinicalTrialProfile.overall_status),
            "enrollment": ClinicalTrialProfile.enrollment,
            "study_type": func.lower(ClinicalTrialProfile.study_type),
            "acronym": func.lower(ClinicalTrialProfile.acronym),
            "initiation_type": func.lower(ClinicalTrialProfile.initiation_type),
        }
        ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
        rows = self.session.scalars(
            select(ClinicalTrialProfile)
            .where(*filters)
            .order_by(
                *ordered_sort,
                ClinicalTrialProfile.registry_id,
                ClinicalTrialProfile.id,
            )
            .limit(limit)
            .offset(offset)
        ).all()
        trial_ids = [row.id for row in rows]
        linked_by_trial = self._clinical_trial_linked_entities([row.entity_id for row in rows])
        entity_roles = self._clinical_trial_entity_roles(trial_ids)
        disclosure_summaries = self._clinical_trial_disclosure_summaries(trial_ids)
        return [
            ClinicalTrialSearchItemRead(
                **ClinicalTrialRead.model_validate(row).model_dump(),
                linked_entities=linked_by_trial[row.entity_id],
                entity_roles=entity_roles[row.id],
                key_result_count=disclosure_summaries[row.id]["key_result_count"],
                latest_result_disclosure=disclosure_summaries[row.id]["latest"],
            )
            for row in rows
        ]

    def _clinical_trial_linked_entities(
        self,
        trial_entity_ids: list[str],
    ) -> dict[str, list[ClinicalTrialLinkedEntityRead]]:
        linked_by_trial: dict[str, list[ClinicalTrialLinkedEntityRead]] = {
            entity_id: [] for entity_id in dict.fromkeys(trial_entity_ids)
        }
        if trial_entity_ids:
            linked_rows = self.session.execute(
                select(Relationship.subject_id, Entity)
                .join(
                    Entity,
                    and_(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id == Relationship.object_id,
                    ),
                )
                .where(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.predicate == "trial_links_entity",
                    Relationship.subject_id.in_(trial_entity_ids),
                )
                .order_by(Relationship.subject_id, Entity.entity_type, Entity.name, Entity.id)
            ).all()
            for trial_entity_id, entity in linked_rows:
                linked_by_trial[trial_entity_id].append(
                    ClinicalTrialLinkedEntityRead(
                        id=entity.id,
                        name=entity.name,
                        entity_type=entity.entity_type,
                    )
                )
        return linked_by_trial

    def _clinical_trial_entity_roles(
        self,
        trial_ids: list[str],
    ) -> dict[str, list[ClinicalTrialEntityRoleRead]]:
        roles_by_trial: dict[str, list[ClinicalTrialEntityRoleRead]] = {
            trial_id: [] for trial_id in dict.fromkeys(trial_ids)
        }
        if not trial_ids:
            return roles_by_trial
        rows = self.session.execute(
            select(ClinicalTrialEntityRole, Entity)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == self.tenant_id,
                    Entity.id == ClinicalTrialEntityRole.entity_id,
                ),
            )
            .where(
                ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                ClinicalTrialEntityRole.trial_id.in_(roles_by_trial),
            )
            .order_by(ClinicalTrialEntityRole.trial_id, ClinicalTrialEntityRole.role, Entity.name, Entity.id)
        ).all()
        for association, entity in rows:
            roles_by_trial[association.trial_id].append(
                ClinicalTrialEntityRoleRead(
                    entity_id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                    role=association.role,
                )
            )
        return roles_by_trial

    def _clinical_trial_result_disclosures(
        self,
        trial_ids: list[str],
    ) -> dict[str, list[ClinicalTrialResultDisclosureRead]]:
        disclosures_by_trial: dict[str, list[ClinicalTrialResultDisclosureRead]] = {
            trial_id: [] for trial_id in dict.fromkeys(trial_ids)
        }
        if not trial_ids:
            return disclosures_by_trial
        rows = self.session.scalars(
            select(ClinicalTrialResultDisclosure)
            .where(
                ClinicalTrialResultDisclosure.tenant_id == self.tenant_id,
                ClinicalTrialResultDisclosure.trial_id.in_(disclosures_by_trial),
            )
            .order_by(
                ClinicalTrialResultDisclosure.trial_id,
                ClinicalTrialResultDisclosure.disclosed_at.desc(),
                ClinicalTrialResultDisclosure.version.desc(),
                ClinicalTrialResultDisclosure.id,
            )
        ).all()
        for disclosure in rows:
            disclosures_by_trial[disclosure.trial_id].append(
                ClinicalTrialResultDisclosureRead(
                    id=disclosure.id,
                    disclosure_key=disclosure.disclosure_key,
                    version=disclosure.version,
                    disclosure_type=TrialResultDisclosureType(disclosure.disclosure_type),
                    external_id=disclosure.external_id,
                    title=disclosure.title,
                    disclosed_at=disclosure.disclosed_at,
                    conference_name=disclosure.conference_name,
                    is_key_result=disclosure.is_key_result,
                    result_evaluation=(
                        TrialResultEvaluation(disclosure.result_evaluation) if disclosure.result_evaluation else None
                    ),
                    source_locator=disclosure.source_locator,
                    source_quote=disclosure.source_quote,
                    source_document_id=disclosure.source_document_id,
                )
            )
        return disclosures_by_trial

    def _clinical_trial_disclosure_summaries(self, trial_ids: list[str]) -> dict[str, dict[str, Any]]:
        disclosures_by_trial = self._clinical_trial_result_disclosures(trial_ids)
        return {
            trial_id: {
                "key_result_count": sum(1 for disclosure in disclosures if disclosure.is_key_result),
                "latest": disclosures[0] if disclosures else None,
            }
            for trial_id, disclosures in disclosures_by_trial.items()
        }

    def _scalar_facet_counts(self, source: Any, name: str) -> dict[str, int]:
        column = source.c[name]
        counts = self.session.execute(
            select(column, func.count())
            .select_from(source)
            .where(column.is_not(None))
            .group_by(column)
            .order_by(func.count().desc(), column)
        ).all()
        return {
            str(value).lower() if isinstance(value, bool) else str(value): count
            for value, count in counts
            if value is not None and str(value) != ""
        }

    def _json_array_facets(
        self,
        source: Any,
        column_name: str,
        id_name: str,
        *,
        public_program_tags_only: bool = False,
    ) -> dict[str, int]:
        if self.session.get_bind().dialect.name == "postgresql":
            values = func.json_array_elements_text(source.c[column_name]).table_valued("value").alias("array_value")
        else:
            values = func.json_each(source.c[column_name]).table_valued("key", "value").alias("array_value")
        value = values.c.value
        counts = self.session.execute(
            select(value, func.count(func.distinct(source.c[id_name])))
            .select_from(source.join(values, true()))
            .where(value.is_not(None), value != "")
            .group_by(value)
            .order_by(func.count(func.distinct(source.c[id_name])).desc(), value)
        ).all()
        return {
            str(item): count
            for item, count in counts
            if item and (not public_program_tags_only or public_program_tags([str(item)]))
        }

    def _clinical_trial_linked_drug_program_facets(self, source: Any) -> dict[str, dict[str, int]]:
        public_modality = _public_program_modality_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        public_drug_category = _public_program_drug_category_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        programs = (
            select(
                source.c.trial_id,
                DevelopmentProgram.id.label("program_id"),
                DevelopmentProgram.organization_set_version,
                public_modality.label("linked_drug_modality"),
                DevelopmentProgram.innovation_type.label("linked_drug_innovation_type"),
                public_drug_category.label("linked_drug_category"),
                DevelopmentProgram.program_tags.label("linked_drug_program_tag"),
                DevelopmentProgram.global_phase.label("linked_drug_global_phase"),
            )
            .select_from(source)
            .join(
                ClinicalTrialEntityRole,
                and_(
                    ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                    ClinicalTrialEntityRole.trial_id == source.c.trial_id,
                    ClinicalTrialEntityRole.role.in_(("investigational_drug", "combination_drug")),
                ),
            )
            .join(
                DevelopmentProgram,
                and_(
                    DevelopmentProgram.tenant_id == self.tenant_id,
                    DevelopmentProgram.drug_entity_id == ClinicalTrialEntityRole.entity_id,
                ),
            )
            .subquery("clinical_trial_linked_program_facets")
        )

        def scalar(name: str) -> dict[str, int]:
            column = programs.c[name]
            rows = self.session.execute(
                select(column, func.count(func.distinct(programs.c.trial_id)))
                .select_from(programs)
                .where(column.is_not(None), column != "")
                .group_by(column)
                .order_by(func.count(func.distinct(programs.c.trial_id)).desc(), column)
            ).all()
            return {str(value): int(count) for value, count in rows if value}

        organizations = (
            select(
                programs.c.trial_id,
                DevelopmentProgramOrganization.country_region.label("linked_drug_organization_country_region"),
            )
            .select_from(programs)
            .join(
                DevelopmentProgramOrganization,
                and_(
                    DevelopmentProgramOrganization.tenant_id == self.tenant_id,
                    DevelopmentProgramOrganization.program_id == programs.c.program_id,
                    DevelopmentProgramOrganization.organization_set_version == programs.c.organization_set_version,
                ),
            )
            .distinct()
            .subquery("clinical_trial_linked_program_org_facets")
        )
        organization_country = organizations.c.linked_drug_organization_country_region
        organization_rows = self.session.execute(
            select(organization_country, func.count(func.distinct(organizations.c.trial_id)))
            .select_from(organizations)
            .where(organization_country.is_not(None), organization_country != "")
            .group_by(organization_country)
            .order_by(func.count(func.distinct(organizations.c.trial_id)).desc(), organization_country)
        ).all()
        return {
            "linked_drug_modality": scalar("linked_drug_modality"),
            "linked_drug_innovation_type": scalar("linked_drug_innovation_type"),
            "linked_drug_category": scalar("linked_drug_category"),
            "linked_drug_program_tag": self._json_array_facets(
                programs,
                "linked_drug_program_tag",
                "trial_id",
                public_program_tags_only=True,
            ),
            "linked_drug_global_phase": scalar("linked_drug_global_phase"),
            "linked_drug_organization_country_region": {
                str(value): int(count) for value, count in organization_rows if value
            },
        }

    def _clinical_trial_landscape(self, source: Any, total: int) -> ClinicalTrialLandscapeRead:
        if self.session.get_bind().dialect.name == "postgresql":
            phase_values = (
                func.json_array_elements_text(source.c.phases).table_valued("value").alias("trial_landscape_phase")
            )
        else:
            phase_values = func.json_each(source.c.phases).table_valued("key", "value").alias("trial_landscape_phase")
        phase_value = phase_values.c.value
        exploded = union_all(
            select(
                source.c.trial_id,
                phase_value.label("phase"),
                source.c.result_evaluation,
                source.c.published_at,
            )
            .select_from(source.join(phase_values, true()))
            .where(phase_value.is_not(None), phase_value != ""),
            select(
                source.c.trial_id,
                literal("__missing__").label("phase"),
                source.c.result_evaluation,
                source.c.published_at,
            ).where(func.coalesce(func.json_array_length(source.c.phases), 0) == 0),
        ).subquery("clinical_trial_landscape_rows")

        year_counts = self.session.execute(
            select(
                func.extract("year", exploded.c.published_at).label("publication_year"),
                exploded.c.phase,
                func.count(func.distinct(exploded.c.trial_id)),
            )
            .select_from(exploded)
            .group_by("publication_year", exploded.c.phase)
        ).all()
        evaluation = func.coalesce(exploded.c.result_evaluation, "__missing__")
        evaluation_counts = self.session.execute(
            select(
                exploded.c.phase,
                evaluation.label("evaluation"),
                func.count(func.distinct(exploded.c.trial_id)),
            )
            .select_from(exploded)
            .group_by(exploded.c.phase, evaluation)
        ).all()

        publication_rows: dict[str, dict[str, int]] = {}
        for year, phase, count in year_counts:
            year_key = "__missing__" if year is None else str(int(year))
            publication_rows.setdefault(year_key, {})[str(phase)] = int(count)

        evaluation_rows: dict[str, dict[str, int]] = {}
        for phase, result_evaluation, count in evaluation_counts:
            evaluation_rows.setdefault(str(phase), {})[str(result_evaluation)] = int(count)

        phase_order = {
            "EARLY_PHASE1": 0,
            "PHASE1": 1,
            "PHASE1_PHASE2": 2,
            "PHASE2": 3,
            "PHASE2_PHASE3": 4,
            "PHASE3": 5,
            "PHASE4": 6,
            "NA": 7,
            "__missing__": 8,
        }
        publication_year_phase = [
            ClinicalTrialLandscapeMatrixRowRead(key=key, total=sum(values.values()), values=values)
            for key, values in sorted(
                publication_rows.items(),
                key=lambda item: (item[0] == "__missing__", -int(item[0]) if item[0].isdigit() else 0),
            )
        ]
        phase_evaluation = [
            ClinicalTrialLandscapeMatrixRowRead(key=key, total=sum(values.values()), values=values)
            for key, values in sorted(
                evaluation_rows.items(),
                key=lambda item: (phase_order.get(item[0], 99), item[0]),
            )
        ]
        return ClinicalTrialLandscapeRead(
            total_trials=total,
            publication_year_phase=publication_year_phase,
            phase_evaluation=phase_evaluation,
        )

    def _json_array_value_exists(self, column: Any, value: str) -> ColumnElement[bool]:
        if self.session.get_bind().dialect.name == "postgresql":
            values = func.json_array_elements_text(column).table_valued("value").alias("array_filter_value")
        else:
            values = func.json_each(column).table_valued("key", "value").alias("array_filter_value")
        return select(literal(1)).select_from(values).where(values.c.value == value).exists()

    def _json_object_array_facets(
        self,
        source: Any,
        column_name: str,
        field_name: str,
        id_name: str,
    ) -> dict[str, int]:
        value: ColumnElement[Any]
        if self.session.get_bind().dialect.name == "postgresql":
            values = func.json_array_elements(source.c[column_name]).table_valued("value").alias("object_value")
            value = values.c.value.op("->>")(field_name)
        else:
            values = func.json_each(source.c[column_name]).table_valued("key", "value").alias("object_value")
            value = func.json_extract(values.c.value, f"$.{field_name}")
        counts = self.session.execute(
            select(value, func.count(func.distinct(source.c[id_name])))
            .select_from(source.join(values, true()))
            .where(value.is_not(None), value != "")
            .group_by(value)
            .order_by(func.count(func.distinct(source.c[id_name])).desc(), value)
        ).all()
        return {str(item): count for item, count in counts if item}

    def _json_object_array_exists(
        self,
        column: Any,
        *,
        text_field: str,
        text_value: str | None,
        datetime_field: str,
        datetime_from: datetime | None,
        datetime_to: datetime | None,
    ) -> ColumnElement[bool]:
        text_expression: ColumnElement[Any]
        datetime_expression: ColumnElement[Any]
        if self.session.get_bind().dialect.name == "postgresql":
            values = func.json_array_elements(column).table_valued("value").alias("object_filter_value")
            text_expression = values.c.value.op("->>")(text_field)
            datetime_expression = cast(
                values.c.value.op("->>")(datetime_field),
                DateTime(timezone=True),
            )
        else:
            values = func.json_each(column).table_valued("key", "value").alias("object_filter_value")
            text_expression = func.json_extract(values.c.value, f"$.{text_field}")
            datetime_expression = func.datetime(func.json_extract(values.c.value, f"$.{datetime_field}"))
        predicates: list[ColumnElement[bool]] = []
        if text_value:
            predicates.append(text_expression == text_value)
        if datetime_from:
            predicates.append(datetime_expression >= datetime_from)
        if datetime_to:
            predicates.append(datetime_expression <= datetime_to)
        return select(literal(1)).select_from(values).where(*predicates).exists()

    def _program_target_exists(self, target_entity_id: str) -> ColumnElement[bool]:
        link = DevelopmentProgramTarget.__table__.alias("program_target_filter")
        return (
            select(literal(1))
            .select_from(link)
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == DevelopmentProgram.id,
                link.c.target_set_version == DevelopmentProgram.target_set_version,
                link.c.target_entity_id.in_(self._entity_identity_ids(target_entity_id, EntityType.TARGET)),
                self._published_identity_exists(
                    link.c.target_entity_id,
                    EntityType.TARGET,
                    correlate_from=link,
                ),
            )
            .correlate(DevelopmentProgram)
            .exists()
        )

    def _program_target_combination_matches(self, target_combination_key: str) -> ColumnElement[bool]:
        """Match the current governed target set by canonical identity, not stale raw IDs."""

        requested_ids = tuple(sorted(set(target_combination_key.split("|"))))
        if not requested_ids:
            return literal(False)

        identity_families = [
            self._entity_identity_member_ids(target_id, EntityType.TARGET) for target_id in requested_ids
        ]
        allowed_target_ids = set().union(*identity_families)
        allowed_target_ids.difference_update(self._placeholder_target_ids())
        if not allowed_target_ids:
            return literal(False)

        link = DevelopmentProgramTarget.__table__.alias("program_target_combination_filter")
        target = Entity.__table__.alias("program_target_combination_entity")
        current_link = (
            select(literal(1))
            .select_from(link)
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == DevelopmentProgram.id,
                link.c.target_set_version == DevelopmentProgram.target_set_version,
            )
            .correlate(DevelopmentProgram)
            .exists()
        )
        required_identity_matches = [
            select(literal(1))
            .select_from(link.join(target, target.c.id == link.c.target_entity_id))
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == DevelopmentProgram.id,
                link.c.target_set_version == DevelopmentProgram.target_set_version,
                link.c.target_entity_id.in_(identity_family),
                _meaningful_entity_name_sql(target.c.name),
                self._published_identity_exists(
                    link.c.target_entity_id,
                    EntityType.TARGET,
                    correlate_from=link,
                ),
            )
            .correlate(DevelopmentProgram)
            .exists()
            for identity_family in identity_families
        ]
        unexpected_identity = (
            select(literal(1))
            .select_from(link.join(target, target.c.id == link.c.target_entity_id))
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == DevelopmentProgram.id,
                link.c.target_set_version == DevelopmentProgram.target_set_version,
                ~link.c.target_entity_id.in_(allowed_target_ids),
                _meaningful_entity_name_sql(target.c.name),
                self._published_identity_exists(
                    link.c.target_entity_id,
                    EntityType.TARGET,
                    correlate_from=link,
                ),
            )
            .correlate(DevelopmentProgram)
            .exists()
        )
        linked_match = and_(current_link, *required_identity_matches, ~unexpected_identity)
        legacy_raw_match = and_(
            ~current_link,
            self._clean_target_combination_expression(DevelopmentProgram.target_combination_key)
            == target_combination_key,
        )

        if len(identity_families) != 1:
            return or_(linked_match, legacy_raw_match)
        legacy_match = and_(
            ~current_link,
            DevelopmentProgram.target_entity_id.in_(identity_families[0]),
            self._published_identity_exists(
                DevelopmentProgram.target_entity_id,
                EntityType.TARGET,
                correlate_from=DevelopmentProgram.__table__,
            ),
        )
        return or_(linked_match, legacy_match, legacy_raw_match)

    def _unique_program_record(self) -> ColumnElement[bool]:
        """Keep one row for an exact duplicate emitted by one source document.

        Source workbooks can repeat a drug/indication row while the ingestion layer
        is still resolving duplicate entity IDs. Keep records from different source
        documents, or rows with different core development fields, because those can
        represent independent observations. Rows without a source document are not
        deduplicated here and remain visible for governance review.
        """

        ranked_program = DevelopmentProgram.__table__.alias("ranked_program")
        ranked_drug = Entity.__table__.alias("ranked_program_drug")
        ranked_target = Entity.__table__.alias("ranked_program_target")
        ranked_disease = Entity.__table__.alias("ranked_program_disease")
        ranked_organization = Entity.__table__.alias("ranked_program_organization")
        ranked_from = (
            ranked_program.join(ranked_drug, ranked_drug.c.id == ranked_program.c.drug_entity_id)
            .outerjoin(ranked_target, ranked_target.c.id == ranked_program.c.target_entity_id)
            .outerjoin(ranked_disease, ranked_disease.c.id == ranked_program.c.disease_entity_id)
            .outerjoin(ranked_organization, ranked_organization.c.id == ranked_program.c.organization_entity_id)
        )
        duplicate_rank = (
            func.row_number()
            .over(
                partition_by=[
                    ranked_program.c.tenant_id,
                    ranked_program.c.source_document_id,
                    ranked_program.c.target_combination_key,
                    ranked_program.c.phase,
                    ranked_program.c.program_status,
                    ranked_program.c.status_date,
                    ranked_program.c.modality,
                    ranked_program.c.mechanism_of_action,
                    ranked_drug.c.normalized_name,
                    ranked_target.c.normalized_name,
                    ranked_disease.c.normalized_name,
                    ranked_organization.c.normalized_name,
                ],
                order_by=ranked_program.c.id,
            )
            .label("duplicate_rank")
        )
        ranked_records = (
            select(ranked_program.c.id.label("program_id"), duplicate_rank)
            .select_from(ranked_from)
            .where(
                ranked_program.c.tenant_id == self.tenant_id,
                ranked_program.c.source_document_id.is_not(None),
            )
            .subquery("deduplicated_program_records")
        )
        retained_ids = select(ranked_records.c.program_id).where(ranked_records.c.duplicate_rank == 1)
        return or_(DevelopmentProgram.source_document_id.is_(None), DevelopmentProgram.id.in_(retained_ids))

    def _program_target_name_exists(self, normalized_query: str) -> ColumnElement[bool]:
        link = DevelopmentProgramTarget.__table__.alias("program_target_name_filter")
        target = Entity.__table__.alias("program_target_name_entity")
        return (
            select(literal(1))
            .select_from(link.join(target, target.c.id == link.c.target_entity_id))
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == DevelopmentProgram.id,
                link.c.target_set_version == DevelopmentProgram.target_set_version,
                self._published_entity_exists(target.c.id),
                func.lower(target.c.name).contains(normalized_query, autoescape=True),
            )
            .correlate(DevelopmentProgram)
            .exists()
        )

    def _program_organization_exists(self, organization_entity_id: str) -> ColumnElement[bool]:
        link = DevelopmentProgramOrganization.__table__.alias("program_organization_filter")
        organization = Entity.__table__.alias("program_organization_visibility_entity")
        return (
            select(literal(1))
            .select_from(link.join(organization, organization.c.id == link.c.organization_entity_id))
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == DevelopmentProgram.id,
                link.c.organization_set_version == DevelopmentProgram.organization_set_version,
                link.c.organization_entity_id == organization_entity_id,
                self._published_entity_exists(organization.c.id),
            )
            .correlate(DevelopmentProgram)
            .exists()
        )

    def _program_organization_name_exists(self, normalized_query: str) -> ColumnElement[bool]:
        link = DevelopmentProgramOrganization.__table__.alias("program_organization_name_filter")
        organization = Entity.__table__.alias("program_organization_name_entity")
        return (
            select(literal(1))
            .select_from(link.join(organization, organization.c.id == link.c.organization_entity_id))
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == DevelopmentProgram.id,
                link.c.organization_set_version == DevelopmentProgram.organization_set_version,
                self._published_entity_exists(organization.c.id),
                func.lower(organization.c.name).contains(normalized_query, autoescape=True),
            )
            .correlate(DevelopmentProgram)
            .exists()
        )

    def _program_target_map(
        self,
        programs: list[DevelopmentProgram],
        legacy_targets: dict[str, tuple[str | None, str | None]],
    ) -> dict[str, list[ProgramTargetRead]]:
        if not programs:
            return {}
        program_ids = [program.id for program in programs]
        rows = self.session.execute(
            select(
                DevelopmentProgramTarget.program_id,
                DevelopmentProgramTarget.target_entity_id,
                Entity.name,
                DevelopmentProgramTarget.role,
                DevelopmentProgramTarget.position,
            )
            .join(
                DevelopmentProgram,
                and_(
                    DevelopmentProgram.id == DevelopmentProgramTarget.program_id,
                    DevelopmentProgram.tenant_id == DevelopmentProgramTarget.tenant_id,
                    DevelopmentProgram.target_set_version == DevelopmentProgramTarget.target_set_version,
                ),
            )
            .join(Entity, Entity.id == DevelopmentProgramTarget.target_entity_id)
            .where(
                DevelopmentProgramTarget.tenant_id == self.tenant_id,
                DevelopmentProgramTarget.program_id.in_(program_ids),
                _meaningful_entity_name_sql(Entity.name),
            )
            .order_by(DevelopmentProgramTarget.program_id, DevelopmentProgramTarget.position)
        ).all()
        result: dict[str, list[ProgramTargetRead]] = {program_id: [] for program_id in program_ids}
        for program_id, target_id, target_name, role, position in rows:
            result[program_id].append(
                ProgramTargetRead(
                    entity_id=target_id,
                    name=target_name,
                    role=role.value if hasattr(role, "value") else str(role),
                    position=position,
                )
            )
        for program_id, (target_id, target_name) in legacy_targets.items():
            if not result.get(program_id) and target_id and _is_meaningful_entity_label(target_name):
                result[program_id] = [
                    ProgramTargetRead(
                        entity_id=target_id,
                        name=target_name,
                        role=ProgramTargetRole.PRIMARY.value,
                        position=0,
                    )
                ]
        for program_id, targets in result.items():
            result[program_id] = [
                target.model_copy(
                    update={
                        "role": ProgramTargetRole.PRIMARY.value if index == 0 else ProgramTargetRole.COMBINATION.value,
                        "position": index,
                    }
                )
                for index, target in enumerate(targets)
            ]
        return result

    def _canonical_entity_identity_ids(self, entity_ids: set[str], entity_type: EntityType) -> dict[str, str]:
        if not entity_ids:
            return {}
        identity_rows = self.session.execute(
            select(
                Entity.id,
                Entity.normalized_name,
                Entity.review_status,
                EntityCanonicalLink.canonical_entity_id,
            )
            .outerjoin(
                EntityCanonicalLink,
                and_(
                    EntityCanonicalLink.tenant_id == self.tenant_id,
                    EntityCanonicalLink.alias_entity_id == Entity.id,
                    EntityCanonicalLink.active.is_(True),
                ),
            )
            .where(
                Entity.tenant_id == self.tenant_id,
                Entity.entity_type == entity_type,
                or_(
                    Entity.id.in_(entity_ids),
                    Entity.normalized_name.in_(
                        select(Entity.normalized_name).where(
                            Entity.tenant_id == self.tenant_id,
                            Entity.id.in_(entity_ids),
                            Entity.entity_type == entity_type,
                        )
                    ),
                ),
            )
        ).all()
        verified_by_name: dict[str, str] = {}
        canonical_by_id: dict[str, str] = {}
        for entity_id, normalized_name, review_status, canonical_entity_id in identity_rows:
            if review_status == ReviewStatus.VERIFIED:
                verified_by_name[normalized_name] = min(verified_by_name.get(normalized_name, entity_id), entity_id)
            if canonical_entity_id:
                canonical_by_id[entity_id] = canonical_entity_id
        return {
            entity_id: canonical_by_id.get(entity_id, verified_by_name.get(normalized_name, entity_id))
            for entity_id, normalized_name, _, _ in identity_rows
            if entity_id in entity_ids
        }

    def _canonical_entity_identity_labels(
        self,
        entity_ids: set[str],
        entity_type: EntityType,
    ) -> dict[str, tuple[str, str]]:
        identity_ids = self._canonical_entity_identity_ids(entity_ids, entity_type)
        display_ids = set(identity_ids.values()) | entity_ids
        name_rows = self.session.execute(
            select(Entity.id, Entity.name).where(
                Entity.tenant_id == self.tenant_id,
                Entity.entity_type == entity_type,
                Entity.id.in_(display_ids),
            )
        ).all()
        names_by_id = {entity_id: name for entity_id, name in name_rows}
        return {
            raw_id: (identity_id, names_by_id.get(identity_id, names_by_id[raw_id]))
            for raw_id, identity_id in identity_ids.items()
            if raw_id in names_by_id
        }

    def _published_entity_identity_labels(
        self,
        entity_ids: set[str],
        entity_type: EntityType,
    ) -> dict[str, tuple[str, str]]:
        """Resolve raw links to stable, publicly readable entity identities.

        Ingestion can attach a program to a draft alias before entity governance has
        reconciled it. Public read models must never emit that draft UUID as a link:
        the entity endpoint correctly rejects it and the user lands on a guaranteed
        404. An explicit verified canonical link wins; otherwise choose the strongest
        verified same-name representative deterministically. Internal reads keep the
        raw relationship and therefore do not call this projection.
        """

        if not entity_ids:
            return {}
        raw_rows = self.session.execute(
            select(Entity.id, Entity.normalized_name).where(
                Entity.tenant_id == self.tenant_id,
                Entity.entity_type == entity_type,
                Entity.id.in_(entity_ids),
            )
        ).all()
        normalized_by_id = {str(entity_id): normalized_name for entity_id, normalized_name in raw_rows}
        if not normalized_by_id:
            return {}

        published_canonical = Entity.__table__.alias("published_identity_canonical")
        canonical_rows = self.session.execute(
            select(
                EntityCanonicalLink.alias_entity_id,
                published_canonical.c.id,
                published_canonical.c.name,
            )
            .select_from(
                EntityCanonicalLink.__table__.join(
                    published_canonical,
                    and_(
                        published_canonical.c.id == EntityCanonicalLink.canonical_entity_id,
                        published_canonical.c.tenant_id == self.tenant_id,
                        published_canonical.c.entity_type == entity_type,
                        published_canonical.c.review_status == ReviewStatus.VERIFIED,
                    ),
                )
            )
            .where(
                EntityCanonicalLink.tenant_id == self.tenant_id,
                EntityCanonicalLink.alias_entity_id.in_(normalized_by_id),
                EntityCanonicalLink.active.is_(True),
            )
            .order_by(EntityCanonicalLink.alias_entity_id, published_canonical.c.id)
        ).all()
        canonical_by_id: dict[str, tuple[str, str]] = {}
        for raw_id, canonical_id, canonical_name in canonical_rows:
            canonical_by_id.setdefault(str(raw_id), (str(canonical_id), str(canonical_name)))

        verified_rows = self.session.execute(
            select(Entity.id, Entity.name, Entity.normalized_name, Entity.external_ids).where(
                Entity.tenant_id == self.tenant_id,
                Entity.entity_type == entity_type,
                Entity.normalized_name.in_(set(normalized_by_id.values())),
                Entity.review_status == ReviewStatus.VERIFIED,
            )
        ).all()
        verified_ids = {str(entity_id) for entity_id, *_ in verified_rows}
        trusted_identifier_counts = {
            str(entity_id): int(count)
            for entity_id, count in self.session.execute(
                select(EntityIdentifier.entity_id, func.count(EntityIdentifier.id))
                .where(
                    EntityIdentifier.tenant_id == self.tenant_id,
                    EntityIdentifier.entity_type == entity_type,
                    EntityIdentifier.entity_id.in_(verified_ids),
                    EntityIdentifier.trusted_namespace.is_(True),
                    EntityIdentifier.review_status == ReviewStatus.VERIFIED,
                )
                .group_by(EntityIdentifier.entity_id)
            ).all()
        }
        best_verified_by_name: dict[str, tuple[str, str]] = {}
        for entity_id, name, normalized_name, _external_ids in sorted(
            verified_rows,
            key=lambda row: (
                -trusted_identifier_counts.get(str(row[0]), 0),
                -len(row[3] or {}),
                str(row[0]),
            ),
        ):
            best_verified_by_name.setdefault(normalized_name, (str(entity_id), str(name)))

        return {
            raw_id: canonical_by_id.get(raw_id, best_verified_by_name[normalized_name])
            for raw_id, normalized_name in normalized_by_id.items()
            if raw_id in canonical_by_id or normalized_name in best_verified_by_name
        }

    def _visible_program_target_map(
        self,
        target_map: Mapping[str, Sequence[ProgramTargetRead]],
    ) -> dict[str, list[ProgramTargetRead]]:
        if self.include_unpublished:
            return {program_id: list(targets) for program_id, targets in target_map.items()}
        identities = self._published_entity_identity_labels(
            {target.entity_id for targets in target_map.values() for target in targets},
            EntityType.TARGET,
        )
        visible: dict[str, list[ProgramTargetRead]] = {}
        for program_id, targets in target_map.items():
            projected: list[ProgramTargetRead] = []
            seen: set[str] = set()
            for target in targets:
                identity = identities.get(target.entity_id)
                if identity is None or identity[0] in seen:
                    continue
                seen.add(identity[0])
                projected.append(
                    target.model_copy(
                        update={
                            "entity_id": identity[0],
                            "name": identity[1],
                            "role": (
                                ProgramTargetRole.PRIMARY.value
                                if not projected
                                else ProgramTargetRole.COMBINATION.value
                            ),
                            "position": len(projected),
                        }
                    )
                )
            visible[program_id] = projected
        return visible

    def _visible_program_organization_map(
        self,
        organization_map: Mapping[str, Sequence[ProgramOrganizationRead]],
    ) -> dict[str, list[ProgramOrganizationRead]]:
        if self.include_unpublished:
            return {program_id: list(organizations) for program_id, organizations in organization_map.items()}
        identities = self._published_entity_identity_labels(
            {organization.entity_id for organizations in organization_map.values() for organization in organizations},
            EntityType.ORGANIZATION,
        )
        visible: dict[str, list[ProgramOrganizationRead]] = {}
        for program_id, organizations in organization_map.items():
            projected: list[ProgramOrganizationRead] = []
            seen: set[tuple[str, str]] = set()
            for organization in organizations:
                identity = identities.get(organization.entity_id)
                if identity is None:
                    continue
                identity_role = (identity[0], organization.role)
                if identity_role in seen:
                    continue
                seen.add(identity_role)
                projected.append(
                    organization.model_copy(
                        update={
                            "entity_id": identity[0],
                            "name": identity[1],
                            "position": len(projected),
                        }
                    )
                )
            visible[program_id] = projected
        return visible

    def _canonical_target_identity_ids(self, target_ids: set[str]) -> dict[str, str]:
        return self._canonical_entity_identity_ids(target_ids, EntityType.TARGET)

    def _canonical_target_combination_keys(
        self,
        target_map: Mapping[str, Sequence[ProgramTargetRead]],
    ) -> dict[str, str]:
        target_ids = {target.entity_id for targets in target_map.values() for target in targets}
        identity_ids = self._canonical_target_identity_ids(target_ids)
        return {
            program_id: "|".join(sorted({identity_ids.get(target.entity_id, target.entity_id) for target in targets}))
            for program_id, targets in target_map.items()
            if targets
        }

    def _program_organization_map(
        self,
        programs: list[DevelopmentProgram],
        legacy_organizations: dict[str, tuple[str | None, str | None]],
    ) -> dict[str, list[ProgramOrganizationRead]]:
        if not programs:
            return {}
        program_ids = [program.id for program in programs]
        rows = self.session.execute(
            select(
                DevelopmentProgramOrganization.program_id,
                DevelopmentProgramOrganization.organization_entity_id,
                Entity.name,
                DevelopmentProgramOrganization.role,
                DevelopmentProgramOrganization.country_region,
                DevelopmentProgramOrganization.organization_type,
                DevelopmentProgramOrganization.position,
            )
            .join(
                DevelopmentProgram,
                and_(
                    DevelopmentProgram.id == DevelopmentProgramOrganization.program_id,
                    DevelopmentProgram.tenant_id == DevelopmentProgramOrganization.tenant_id,
                    DevelopmentProgram.organization_set_version
                    == DevelopmentProgramOrganization.organization_set_version,
                ),
            )
            .join(Entity, Entity.id == DevelopmentProgramOrganization.organization_entity_id)
            .where(
                DevelopmentProgramOrganization.tenant_id == self.tenant_id,
                DevelopmentProgramOrganization.program_id.in_(program_ids),
            )
            .order_by(
                DevelopmentProgramOrganization.program_id,
                DevelopmentProgramOrganization.position,
            )
        ).all()
        result: dict[str, list[ProgramOrganizationRead]] = {program_id: [] for program_id in program_ids}
        for program_id, organization_id, name, role, country_region, organization_type, position in rows:
            result[program_id].append(
                ProgramOrganizationRead(
                    entity_id=organization_id,
                    name=name,
                    role=role,
                    country_region=country_region,
                    organization_type=organization_type,
                    position=position,
                )
            )
        for program_id, (organization_id, organization_name) in legacy_organizations.items():
            if not result.get(program_id) and organization_id and organization_name:
                result[program_id] = [
                    ProgramOrganizationRead(
                        entity_id=organization_id,
                        name=organization_name,
                        role="originator",
                        position=0,
                    )
                ]
        return result

    def _pipeline_organization_source(self, source: Any) -> Any:
        link = DevelopmentProgramOrganization.__table__.alias("landscape_program_organization")
        organization = Entity.__table__.alias("landscape_organization")
        current_link = (
            select(literal(1))
            .select_from(link)
            .where(
                link.c.tenant_id == self.tenant_id,
                link.c.program_id == source.c.program_id,
                link.c.organization_set_version == source.c.organization_set_version,
            )
            .correlate(source)
            .exists()
        )
        linked = select(
            source.c.program_id.label("program_id"),
            source.c.drug_entity_id.label("drug_entity_id"),
            source.c.drug_identity_id.label("drug_identity_id"),
            link.c.organization_entity_id.label("organization_entity_id"),
            organization.c.name.label("organization_name"),
            link.c.role.label("organization_role"),
            link.c.organization_type.label("organization_type"),
            link.c.country_region.label("organization_country_region"),
            source.c.phase.label("phase"),
            source.c.global_phase.label("global_phase"),
            source.c.china_phase.label("china_phase"),
        ).select_from(
            source.join(
                link,
                and_(
                    link.c.tenant_id == self.tenant_id,
                    link.c.program_id == source.c.program_id,
                    link.c.organization_set_version == source.c.organization_set_version,
                ),
            ).join(organization, organization.c.id == link.c.organization_entity_id)
        )
        legacy = select(
            source.c.program_id.label("program_id"),
            source.c.drug_entity_id.label("drug_entity_id"),
            source.c.drug_identity_id.label("drug_identity_id"),
            source.c.organization_entity_id.label("organization_entity_id"),
            source.c.organization_name.label("organization_name"),
            literal("originator").label("organization_role"),
            cast(literal(None), String).label("organization_type"),
            cast(literal(None), String).label("organization_country_region"),
            source.c.phase.label("phase"),
            source.c.global_phase.label("global_phase"),
            source.c.china_phase.label("china_phase"),
        ).where(~current_link)
        return union_all(linked, legacy).subquery("pipeline_landscape_organizations")

    def _pipeline_organization_facets(self, source: Any, id_name: str) -> dict[str, dict[str, int]]:
        organization_source = self._pipeline_organization_source(source)
        count_expression = func.count(func.distinct(organization_source.c[id_name]))
        facets: dict[str, dict[str, int]] = {}
        for name in ("organization_role", "organization_type", "organization_country_region"):
            column = organization_source.c[name]
            rows = self.session.execute(
                select(column, count_expression)
                .select_from(organization_source)
                .where(column.is_not(None), column != "")
                .group_by(column)
                .order_by(count_expression.desc(), column)
            ).all()
            facets[name] = {str(value): int(count) for value, count in rows}
        return facets

    def _pipeline_landscape(
        self,
        source: Any,
        total: int,
        *,
        limit: int,
        stage_scope: PipelineLandscapeStageScope,
        target_aggregation: PipelineTargetAggregation,
    ) -> PipelineLandscapeRead:
        distinct_drugs = int(
            self.session.scalar(select(func.count(func.distinct(source.c.drug_identity_id))).select_from(source)) or 0
        )
        disease_source = self._pipeline_entity_identity_source(
            source,
            "disease_entity_id",
            "disease_name",
            EntityType.DISEASE,
        )
        distinct_diseases = int(
            self.session.scalar(
                select(func.count(func.distinct(disease_source.c.entity_id))).select_from(disease_source)
            )
            or 0
        )
        organization_source = self._pipeline_organization_source(source)
        organization_identity_source = self._pipeline_entity_identity_source(
            organization_source,
            "organization_entity_id",
            "organization_name",
            EntityType.ORGANIZATION,
        )
        distinct_organizations = int(
            self.session.scalar(
                select(func.count(func.distinct(organization_identity_source.c.entity_id))).select_from(
                    organization_identity_source
                )
            )
            or 0
        )
        return PipelineLandscapeRead(
            total_programs=total,
            distinct_drugs=distinct_drugs,
            distinct_targets=self._pipeline_distinct_target_count(source, target_aggregation),
            distinct_diseases=distinct_diseases,
            distinct_organizations=distinct_organizations,
            limit=limit,
            stage_scope=stage_scope,
            target_aggregation=target_aggregation,
            overall_phase=self._pipeline_scalar_landscape(source, "phase", total, limit=limit),
            global_phase=self._pipeline_scalar_landscape(source, "global_phase", total, limit=limit),
            china_phase=self._pipeline_scalar_landscape(source, "china_phase", total, limit=limit),
            targets=self._pipeline_target_landscape(
                source,
                total,
                limit=limit,
                stage_scope=stage_scope,
                target_aggregation=target_aggregation,
            ),
            diseases=self._pipeline_entity_landscape(
                disease_source,
                "entity_id",
                "entity_name",
                total,
                limit=limit,
                stage_scope=stage_scope,
            ),
            target_combinations=self._pipeline_target_combinations(
                source,
                total,
                limit=limit,
                stage_scope=stage_scope,
            ),
            modality=self._pipeline_scalar_landscape(source, "modality", total, limit=limit, stage_scope=stage_scope),
            geography=self._pipeline_scalar_landscape(source, "geography", total, limit=limit, stage_scope=stage_scope),
            organizations=self._pipeline_entity_landscape(
                organization_identity_source,
                "entity_id",
                "entity_name",
                total,
                limit=limit,
                stage_scope=stage_scope,
            ),
        )

    def _pipeline_scalar_landscape(
        self,
        source: Any,
        column_name: str,
        total: int,
        *,
        limit: int = 20,
        stage_scope: PipelineLandscapeStageScope | None = None,
    ) -> list[PipelineLandscapeBucketRead]:
        column = source.c[column_name]
        rows = self.session.execute(
            select(column, func.count(func.distinct(source.c.program_id)))
            .select_from(source)
            .group_by(column)
            .order_by(func.count(func.distinct(source.c.program_id)).desc(), column)
            .limit(limit)
        ).all()
        buckets: list[PipelineLandscapeBucketRead] = []
        phase_counts = self._pipeline_phase_counts(source, column, [row[0] for row in rows], stage_scope)
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
        self,
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
        rows = self.session.execute(
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
        phase_counts = self._pipeline_phase_counts(source, entity_id, [row[0] for row in rows], stage_scope)
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

    def _pipeline_entity_identity_source(
        self,
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
                canonical_link.c.tenant_id == self.tenant_id,
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
                verified_entity.c.tenant_id == self.tenant_id,
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
                canonical_link.c.tenant_id == self.tenant_id,
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
                verified_entity.c.tenant_id == self.tenant_id,
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

    def _pipeline_target_landscape(
        self,
        source: Any,
        total: int,
        *,
        limit: int = 20,
        stage_scope: PipelineLandscapeStageScope = "overall",
        target_aggregation: PipelineTargetAggregation = "all",
    ) -> list[PipelineLandscapeBucketRead]:
        target_source = self._pipeline_target_source(source, target_aggregation)
        rows = self.session.execute(
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
        phase_counts = self._pipeline_phase_counts(
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

    def _pipeline_target_source(
        self,
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
                canonical_link.c.tenant_id == self.tenant_id,
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
                verified_target.c.tenant_id == self.tenant_id,
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
                canonical_link.c.tenant_id == self.tenant_id,
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
                verified_target.c.tenant_id == self.tenant_id,
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
                link.c.tenant_id == self.tenant_id,
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
                        link.c.tenant_id == self.tenant_id,
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
                    candidate_link.c.tenant_id == self.tenant_id,
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
        self,
        source: Any,
        target_aggregation: PipelineTargetAggregation = "all",
    ) -> int:
        target_source = self._pipeline_target_source(source, target_aggregation)
        return int(
            self.session.scalar(
                select(func.count(func.distinct(target_source.c.target_entity_id))).select_from(target_source)
            )
            or 0
        )

    def _pipeline_target_combinations(
        self,
        source: Any,
        total: int,
        *,
        limit: int = 20,
        stage_scope: PipelineLandscapeStageScope = "overall",
    ) -> list[PipelineLandscapeBucketRead]:
        combination_source = self._pipeline_target_combination_source(source)
        rows = self.session.execute(
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
        phase_counts = self._pipeline_phase_counts(
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

    def _pipeline_target_combination_source(self, source: Any) -> Any:
        target_source = self._pipeline_target_source(source)
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
        if self.session.get_bind().dialect.name == "postgresql":
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

    def _pipeline_phase_counts(
        self,
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
        rows = self.session.execute(
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

    def patents(
        self,
        entity_id: str | None,
        query: str | None,
        limit: int,
        offset: int = 0,
        applicant: str | None = None,
        legal_status: str | None = None,
    ) -> list[PatentFamilyRead]:
        filters = self._patent_filters(entity_id, query, applicant=applicant, legal_status=legal_status)
        rows = self.session.scalars(
            select(PatentFamily)
            .where(*filters)
            .order_by(PatentFamily.priority_date.desc().nullslast(), PatentFamily.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [PatentFamilyRead.model_validate(row) for row in rows]

    def search_patent_families(
        self,
        query: str | None,
        applicant: str | None,
        legal_status: str | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        priority_from: datetime | None = None,
        priority_to: datetime | None = None,
        expiration_from: datetime | None = None,
        expiration_to: datetime | None = None,
        sort_by: PatentSortField = "priority_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[PatentSortField]] | None = None,
    ) -> PatentFamilySearchResult:
        effective_sort = validate_sort_clauses(
            sort,
            PATENT_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        filters = self._patent_filters(
            entity_id,
            query,
            applicant=applicant,
            legal_status=legal_status,
            priority_from=priority_from,
            priority_to=priority_to,
            expiration_from=expiration_from,
            expiration_to=expiration_to,
        )
        items = self._patent_search_items(
            filters,
            limit,
            offset,
            sort=effective_sort,
        )

        facet_source = (
            select(
                PatentFamily.id.label("patent_id"),
                PatentFamily.legal_status.label("legal_status"),
                PatentFamily.applicants.label("applicants"),
                PatentFamily.priority_date.label("priority_date"),
            )
            .where(*filters)
            .subquery()
        )
        total = self.session.scalar(select(func.count()).select_from(facet_source)) or 0
        facets = {
            "legal_status": self._scalar_facet_counts(facet_source, "legal_status"),
            "applicant": self._json_array_facets(facet_source, "applicants", "patent_id"),
        }
        landscape = self._patent_landscape(facet_source, total, applicant_counts=facets["applicant"])
        return PatentFamilySearchResult(
            query_schema_version="pharma.patent.search.v2",
            applied_filters=self._applied_filters(
                ("entity_id", "eq", entity_id),
                ("q", "contains", query.strip() if query else None),
                ("applicant", "eq", applicant),
                ("legal_status", "eq", legal_status),
                ("priority_from", "gte", priority_from.isoformat() if priority_from else None),
                ("priority_to", "lte", priority_to.isoformat() if priority_to else None),
                ("expiration_from", "gte", expiration_from.isoformat() if expiration_from else None),
                ("expiration_to", "lte", expiration_to.isoformat() if expiration_to else None),
            ),
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=effective_sort[0].field,
            sort_direction=effective_sort[0].direction,
            sort=_sort_criteria_read(effective_sort),
            facets=facets,
            landscape=landscape,
            as_of=datetime.now(UTC),
            warnings=["未观察到专利族不代表不存在；结果受司法辖区、数据授权、法律状态时效和治理状态限制。"],
        )

    def _patent_landscape(
        self,
        source: Any,
        total: int,
        *,
        applicant_counts: dict[str, int],
        top_limit: int = 8,
    ) -> PatentLandscapeRead:
        """Aggregate the complete filtered patent set for the same-query statistics view."""

        def bucket(key: str, count: int) -> PatentLandscapeBucketRead:
            return PatentLandscapeBucketRead(
                key=key,
                label="未披露" if key == "__missing__" else key,
                count=count,
                share=(count / total) if total else 0.0,
            )

        status_column = func.coalesce(source.c.legal_status, "__missing__")
        status_rows = self.session.execute(
            select(status_column.label("status"), func.count())
            .select_from(source)
            .group_by("status")
            .order_by(func.count().desc(), status_column)
        ).all()
        legal_status = [bucket(str(status), int(count)) for status, count in status_rows]

        top_applicants = [
            bucket(name, count)
            for name, count in sorted(applicant_counts.items(), key=lambda item: (-item[1], item[0]))[:top_limit]
        ]

        year_column = func.extract("year", source.c.priority_date)
        year_rows = self.session.execute(
            select(year_column.label("priority_year"), func.count()).select_from(source).group_by("priority_year")
        ).all()
        priority_year = sorted(
            (bucket("__missing__" if year is None else str(int(year)), int(count)) for year, count in year_rows),
            key=lambda item: (item.key == "__missing__", item.key),
            reverse=True,
        )

        return PatentLandscapeRead(
            total_families=total,
            legal_status=legal_status,
            top_applicants=top_applicants,
            priority_year=priority_year,
        )

    def _landscape_scalar_buckets(
        self,
        source: Any,
        column_name: str,
        total: int,
        bucket_type: Any,
    ) -> list[Any]:
        column = func.coalesce(getattr(source.c, column_name), "__missing__")
        rows = self.session.execute(
            select(column.label("value"), func.count())
            .select_from(source)
            .group_by("value")
            .order_by(func.count().desc(), column)
        ).all()
        return [
            bucket_type(
                key=str(value),
                label="未披露" if str(value) == "__missing__" else str(value),
                count=int(count),
                share=(int(count) / total) if total else 0.0,
            )
            for value, count in rows
        ]

    def _regulatory_landscape(self, source: Any, total: int) -> RegulatoryLandscapeRead:
        """Aggregate the complete filtered regulatory set for the same-query statistics view."""

        def bucket(key: str, count: int) -> RegulatoryLandscapeBucketRead:
            return RegulatoryLandscapeBucketRead(
                key=key,
                label="未披露" if key == "__missing__" else key,
                count=count,
                share=(count / total) if total else 0.0,
            )

        def scalar_buckets(column_name: str) -> list[RegulatoryLandscapeBucketRead]:
            column = func.coalesce(getattr(source.c, column_name), "__missing__")
            rows = self.session.execute(
                select(column.label("value"), func.count())
                .select_from(source)
                .group_by("value")
                .order_by(func.count().desc(), column)
            ).all()
            return [bucket(str(value), int(count)) for value, count in rows]

        year_column = func.extract("year", source.c.decision_date)
        year_rows = self.session.execute(
            select(year_column.label("decision_year"), func.count()).select_from(source).group_by("decision_year")
        ).all()
        decision_year = sorted(
            (bucket("__missing__" if year is None else str(int(year)), int(count)) for year, count in year_rows),
            key=lambda item: (item.key == "__missing__", item.key),
            reverse=True,
        )

        return RegulatoryLandscapeRead(
            total_events=total,
            event_type=scalar_buckets("event_type"),
            agency=scalar_buckets("agency"),
            decision_year=decision_year,
        )

    def patent_saved_search_matches_entity(
        self,
        entity_id: str,
        query: PatentSavedSearchQuery,
    ) -> bool:
        filters = self._patent_filters(
            entity_id,
            query.q,
            applicant=query.applicant,
            legal_status=query.legal_status,
            priority_from=_saved_date_start(query.priority_from),
            priority_to=_saved_date_end(query.priority_to),
            expiration_from=_saved_date_start(query.expiration_from),
            expiration_to=_saved_date_end(query.expiration_to),
        )
        statement = select(PatentFamily.id).where(*filters).limit(1)
        return self.session.scalar(statement.with_only_columns(literal(True))) is True

    def patent_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        applicant: str | None,
        legal_status: str | None,
        limit: int,
        offset: int = 0,
        *,
        sort_by: PatentSortField = "priority_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[PatentSortField]] | None = None,
    ) -> list[PatentFamilySearchItemRead]:
        filters = self._patent_filters(entity_id, query, applicant=applicant, legal_status=legal_status)
        return self._patent_search_items(
            filters,
            limit,
            offset,
            sort=validate_sort_clauses(
                sort,
                PATENT_SORT_FIELDS,
                default_field=sort_by,
                default_direction=sort_direction,
            ),
        )

    def patent_family_detail(self, family_id: str) -> PatentFamilySearchItemRead | None:
        items = self._patent_search_items(
            [
                PatentFamily.tenant_id == self.tenant_id,
                PatentFamily.id == family_id,
                self._published_entity_exists(PatentFamily.entity_id),
            ],
            1,
            0,
        )
        return items[0] if items else None

    def _patent_search_items(
        self,
        filters: list[ColumnElement[bool]],
        limit: int,
        offset: int,
        *,
        sort_by: PatentSortField = "priority_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[PatentSortField]] | None = None,
    ) -> list[PatentFamilySearchItemRead]:
        effective_sort = validate_sort_clauses(
            sort,
            PATENT_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        sort_expressions: dict[PatentSortField, Any] = {
            "priority_date": PatentFamily.priority_date,
            "family_identifier": func.lower(PatentFamily.family_identifier),
            "legal_status": func.lower(PatentFamily.legal_status),
            "expiration_date": PatentFamily.expiration_date,
        }
        ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
        rows = self.session.scalars(
            select(PatentFamily)
            .where(*filters)
            .order_by(*ordered_sort, PatentFamily.family_identifier, PatentFamily.id)
            .limit(limit)
            .offset(offset)
        ).all()
        linked_by_patent: dict[str, dict[str, PatentFamilyLinkedEntityRead]] = {row.entity_id: {} for row in rows}
        patent_entity_ids = list(linked_by_patent)
        if patent_entity_ids:
            linked_rows = self.session.execute(
                select(Relationship.subject_id, Entity)
                .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == Relationship.object_id))
                .where(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.predicate == "patent_links_entity",
                    Relationship.subject_id.in_(patent_entity_ids),
                )
                .order_by(Relationship.subject_id, Entity.entity_type, Entity.name, Entity.id)
            ).all()
            for patent_entity_id, entity in linked_rows:
                linked_by_patent[patent_entity_id][entity.id] = PatentFamilyLinkedEntityRead(
                    id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                )
            legacy_ids = {entity_id for row in rows for entity_id in row.linked_entity_ids}
            if legacy_ids:
                legacy_entities = self.session.scalars(
                    select(Entity)
                    .where(Entity.tenant_id == self.tenant_id, Entity.id.in_(legacy_ids))
                    .order_by(Entity.entity_type, Entity.name, Entity.id)
                ).all()
                entity_by_id = {entity.id: entity for entity in legacy_entities}
                for row in rows:
                    for entity_id in row.linked_entity_ids:
                        if entity := entity_by_id.get(entity_id):
                            linked_by_patent[row.entity_id].setdefault(
                                entity.id,
                                PatentFamilyLinkedEntityRead(
                                    id=entity.id,
                                    name=entity.name,
                                    entity_type=entity.entity_type,
                                ),
                            )
        return [
            PatentFamilySearchItemRead(
                **PatentFamilyRead.model_validate(row).model_dump(),
                linked_entities=list(linked_by_patent[row.entity_id].values()),
            )
            for row in rows
        ]

    def deals(
        self,
        entity_id: str | None,
        limit: int,
        offset: int = 0,
        query: str | None = None,
        deal_type: str | None = None,
        territory: str | None = None,
        party: str | None = None,
    ) -> list[DealRead]:
        filters = self._deal_filters(entity_id, query, deal_type, territory, party)
        rows = self.session.scalars(
            select(DealProfile)
            .where(*filters)
            .order_by(DealProfile.announced_at.desc().nullslast(), DealProfile.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [DealRead.model_validate(row) for row in rows]

    def search_deals(
        self,
        query: str | None,
        deal_type: str | None,
        territory: str | None,
        party: str | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        status: str | None = None,
        direction: str | None = None,
        direction_reference_jurisdiction: str | None = None,
        asset_entity_id: str | None = None,
        target_entity_id: str | None = None,
        disease_entity_id: str | None = None,
        asset_modality: list[str] | None = None,
        asset_program_tag: list[str] | None = None,
        party_entity_id: str | None = None,
        party_role: str | None = None,
        party_country_region: str | None = None,
        party_organization_type: str | None = None,
        development_phase_at_transaction: str | None = None,
        current_development_phase: str | None = None,
        right_type: str | None = None,
        rights_territory: str | None = None,
        currency: str | None = None,
        announced_from: datetime | None = None,
        announced_to: datetime | None = None,
        terminated_from: datetime | None = None,
        terminated_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        upfront_amount_min: float | None = None,
        upfront_amount_max: float | None = None,
        total_potential_amount_min: float | None = None,
        total_potential_amount_max: float | None = None,
        sort_by: DealSortField = "announced_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[DealSortField]] | None = None,
        landscape_limit: DealAnalysisLimit = 8,
    ) -> DealSearchResult:
        effective_sort = validate_sort_clauses(
            sort,
            DEAL_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        if (
            any(clause.field in {"upfront_amount", "total_potential_amount"} for clause in effective_sort)
            and currency is None
        ):
            raise ValueError("currency is required when sorting disclosed deal amounts")
        filters = self._deal_filters(
            entity_id,
            query,
            deal_type,
            territory,
            party,
            status=status,
            direction=direction,
            direction_reference_jurisdiction=direction_reference_jurisdiction,
            asset_entity_id=asset_entity_id,
            target_entity_id=target_entity_id,
            disease_entity_id=disease_entity_id,
            asset_modality=asset_modality,
            asset_program_tag=asset_program_tag,
            party_entity_id=party_entity_id,
            party_role=party_role,
            party_country_region=party_country_region,
            party_organization_type=party_organization_type,
            development_phase_at_transaction=development_phase_at_transaction,
            current_development_phase=current_development_phase,
            right_type=right_type,
            rights_territory=rights_territory,
            currency=currency,
            announced_from=announced_from,
            announced_to=announced_to,
            terminated_from=terminated_from,
            terminated_to=terminated_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            upfront_amount_min=upfront_amount_min,
            upfront_amount_max=upfront_amount_max,
            total_potential_amount_min=total_potential_amount_min,
            total_potential_amount_max=total_potential_amount_max,
        )
        items = self._deal_search_items(
            filters,
            limit,
            offset,
            sort=effective_sort,
        )
        facet_source = (
            select(
                DealProfile.id.label("deal_id"),
                DealProfile.entity_id.label("deal_entity_id"),
                DealProfile.deal_type.label("deal_type"),
                DealProfile.status.label("status"),
                DealProfile.direction.label("direction"),
                DealProfile.territory.label("territory"),
                DealProfile.currency.label("currency"),
            )
            .where(*filters)
            .subquery()
        )
        total = self.session.scalar(select(func.count()).select_from(facet_source)) or 0
        facets = {
            "deal_type": self._scalar_facet_counts(facet_source, "deal_type"),
            "status": self._scalar_facet_counts(facet_source, "status"),
            "direction": self._scalar_facet_counts(facet_source, "direction"),
            "territory": self._scalar_facet_counts(facet_source, "territory"),
            "currency": self._scalar_facet_counts(facet_source, "currency"),
            "asset": self._deal_asset_facets(facet_source),
            "target": self._deal_program_entity_facets(facet_source, "target"),
            "disease": self._deal_program_entity_facets(facet_source, "disease"),
            "asset_modality": self._deal_program_attribute_facets(facet_source, "modality"),
            "asset_program_tag": self._deal_program_attribute_facets(facet_source, "program_tags"),
            "party": self._deal_party_facets(facet_source),
            "party_role": self._deal_party_role_facets(facet_source),
            "party_country_region": self._deal_party_attribute_facets(facet_source, "country_region"),
            "party_organization_type": self._deal_party_attribute_facets(facet_source, "organization_type"),
            "development_phase_at_transaction": self._deal_asset_phase_facets(facet_source),
            "current_development_phase": self._deal_current_phase_facets(facet_source),
            "right_type": self._deal_right_facets(facet_source, "right_type"),
            "rights_territory": self._deal_right_facets(facet_source, "territory"),
        }
        landscape = self._deal_landscape(facets, total, limit=landscape_limit)
        return DealSearchResult(
            query_schema_version="pharma.deal.search.v8",
            applied_filters=self._applied_filters(
                ("entity_id", "eq", entity_id),
                ("q", "contains", query.strip() if query else None),
                ("deal_type", "eq", deal_type),
                ("status", "eq", status),
                ("direction", "eq", direction),
                ("direction_reference_jurisdiction", "eq", direction_reference_jurisdiction),
                ("territory", "eq", territory),
                ("asset_entity_id", "eq", asset_entity_id),
                ("target_entity_id", "eq", target_entity_id),
                ("disease_entity_id", "eq", disease_entity_id),
                ("asset_modality", "in", asset_modality),
                ("asset_program_tag", "in", public_program_tags(asset_program_tag)),
                ("party", "eq", party),
                ("party_entity_id", "eq", party_entity_id),
                ("party_role", "eq", party_role),
                ("party_country_region", "eq", party_country_region),
                ("party_organization_type", "eq", party_organization_type),
                ("development_phase_at_transaction", "eq", development_phase_at_transaction),
                ("current_development_phase", "eq", current_development_phase),
                ("right_type", "eq", right_type),
                ("rights_territory", "eq", rights_territory),
                ("currency", "eq", currency),
                ("announced_from", "gte", announced_from.isoformat() if announced_from else None),
                ("announced_to", "lte", announced_to.isoformat() if announced_to else None),
                ("terminated_from", "gte", terminated_from.isoformat() if terminated_from else None),
                ("terminated_to", "lte", terminated_to.isoformat() if terminated_to else None),
                ("source_updated_from", "gte", source_updated_from.isoformat() if source_updated_from else None),
                ("source_updated_to", "lte", source_updated_to.isoformat() if source_updated_to else None),
                ("upfront_amount_min", "gte", upfront_amount_min),
                ("upfront_amount_max", "lte", upfront_amount_max),
                ("total_potential_amount_min", "gte", total_potential_amount_min),
                ("total_potential_amount_max", "lte", total_potential_amount_max),
            ),
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=effective_sort[0].field,
            sort_direction=effective_sort[0].direction,
            sort=_sort_criteria_read(effective_sort),
            facets=facets,
            landscape=landscape,
            as_of=datetime.now(UTC),
            warnings=["未观察到交易不代表不存在；结果受数据授权、披露完整性、金额口径和治理状态限制。"],
        )

    def _deal_landscape(
        self,
        facets: dict[str, dict[str, int]],
        total: int,
        *,
        limit: DealAnalysisLimit,
    ) -> DealLandscapeRead:
        def buckets(name: str, *, exclusive: bool) -> list[DealLandscapeBucketRead]:
            counts = dict(facets.get(name, {}))
            if exclusive:
                missing = max(0, total - sum(counts.values()))
                if missing:
                    counts["__missing__"] = missing
            ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
            return [
                DealLandscapeBucketRead(
                    key=key,
                    label="未披露" if key == "__missing__" else key,
                    count=int(count),
                    share=round(int(count) / total, 6) if total else 0,
                )
                for key, count in ordered
            ]

        return DealLandscapeRead(
            total_deals=total,
            limit=limit,
            deal_type=buckets("deal_type", exclusive=True),
            status=buckets("status", exclusive=True),
            direction=buckets("direction", exclusive=True),
            territory=buckets("territory", exclusive=True),
            currency=buckets("currency", exclusive=True),
            asset_modality=buckets("asset_modality", exclusive=False),
            transaction_phase=buckets("development_phase_at_transaction", exclusive=False),
            current_phase=buckets("current_development_phase", exclusive=False),
            party_country=buckets("party_country_region", exclusive=False),
            rights_territory=buckets("rights_territory", exclusive=False),
        )

    def deal_saved_search_matches_entity(
        self,
        entity_id: str,
        query: DealSavedSearchQuery,
    ) -> bool:
        def start(value: Any) -> datetime | None:
            return datetime.combine(value, time.min, tzinfo=UTC) if value else None

        def end(value: Any) -> datetime | None:
            return datetime.combine(value, time.max, tzinfo=UTC) if value else None

        filters = self._deal_filters(
            entity_id,
            query.q,
            query.deal_type,
            query.territory,
            query.party,
            status=query.status.value if query.status else None,
            direction=query.direction.value if query.direction else None,
            direction_reference_jurisdiction=query.direction_reference_jurisdiction,
            asset_entity_id=query.asset_entity_id,
            target_entity_id=query.target_entity_id,
            disease_entity_id=query.disease_entity_id,
            asset_modality=query.asset_modality,
            asset_program_tag=query.asset_program_tag,
            party_entity_id=query.party_entity_id,
            party_role=query.party_role.value if query.party_role else None,
            party_country_region=query.party_country_region,
            party_organization_type=query.party_organization_type,
            development_phase_at_transaction=(
                query.development_phase_at_transaction.value if query.development_phase_at_transaction else None
            ),
            current_development_phase=(
                query.current_development_phase.value if query.current_development_phase else None
            ),
            right_type=query.right_type.value if query.right_type else None,
            rights_territory=query.rights_territory,
            currency=query.currency,
            announced_from=start(query.announced_from),
            announced_to=end(query.announced_to),
            terminated_from=start(query.terminated_from),
            terminated_to=end(query.terminated_to),
            source_updated_from=start(query.source_updated_from),
            source_updated_to=end(query.source_updated_to),
            upfront_amount_min=query.upfront_amount_min,
            upfront_amount_max=query.upfront_amount_max,
            total_potential_amount_min=query.total_potential_amount_min,
            total_potential_amount_max=query.total_potential_amount_max,
        )
        statement = select(DealProfile.id).where(*filters).limit(1)
        return self.session.scalar(statement.with_only_columns(literal(True))) is True

    def deal_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        deal_type: str | None,
        territory: str | None,
        party: str | None,
        limit: int,
        offset: int = 0,
        *,
        status: str | None = None,
        direction: str | None = None,
        direction_reference_jurisdiction: str | None = None,
        asset_entity_id: str | None = None,
        target_entity_id: str | None = None,
        disease_entity_id: str | None = None,
        asset_modality: list[str] | None = None,
        asset_program_tag: list[str] | None = None,
        party_entity_id: str | None = None,
        party_role: str | None = None,
        party_country_region: str | None = None,
        party_organization_type: str | None = None,
        development_phase_at_transaction: str | None = None,
        current_development_phase: str | None = None,
        right_type: str | None = None,
        rights_territory: str | None = None,
        currency: str | None = None,
        announced_from: datetime | None = None,
        announced_to: datetime | None = None,
        terminated_from: datetime | None = None,
        terminated_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        upfront_amount_min: float | None = None,
        upfront_amount_max: float | None = None,
        total_potential_amount_min: float | None = None,
        total_potential_amount_max: float | None = None,
        sort_by: DealSortField = "announced_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[DealSortField]] | None = None,
    ) -> list[DealSearchItemRead]:
        effective_sort = validate_sort_clauses(
            sort,
            DEAL_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        if (
            any(clause.field in {"upfront_amount", "total_potential_amount"} for clause in effective_sort)
            and currency is None
        ):
            raise ValueError("currency is required when sorting disclosed deal amounts")
        filters = self._deal_filters(
            entity_id,
            query,
            deal_type,
            territory,
            party,
            status=status,
            direction=direction,
            direction_reference_jurisdiction=direction_reference_jurisdiction,
            asset_entity_id=asset_entity_id,
            target_entity_id=target_entity_id,
            disease_entity_id=disease_entity_id,
            asset_modality=asset_modality,
            asset_program_tag=asset_program_tag,
            party_entity_id=party_entity_id,
            party_role=party_role,
            party_country_region=party_country_region,
            party_organization_type=party_organization_type,
            development_phase_at_transaction=development_phase_at_transaction,
            current_development_phase=current_development_phase,
            right_type=right_type,
            rights_territory=rights_territory,
            currency=currency,
            announced_from=announced_from,
            announced_to=announced_to,
            terminated_from=terminated_from,
            terminated_to=terminated_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            upfront_amount_min=upfront_amount_min,
            upfront_amount_max=upfront_amount_max,
            total_potential_amount_min=total_potential_amount_min,
            total_potential_amount_max=total_potential_amount_max,
        )
        return self._deal_search_items(
            filters,
            limit,
            offset,
            sort=effective_sort,
        )

    def deal_detail(self, deal_id: str) -> DealSearchItemRead | None:
        items = self._deal_search_items(
            [
                DealProfile.tenant_id == self.tenant_id,
                DealProfile.id == deal_id,
                self._published_entity_exists(DealProfile.entity_id),
            ],
            1,
            0,
        )
        return items[0] if items else None

    def company_timeline(
        self,
        company_entity_id: str,
        limit: int,
        offset: int = 0,
    ) -> CompanyTimelineResult | None:
        company = self.session.scalar(
            select(Entity).where(
                Entity.id == company_entity_id,
                Entity.tenant_id == self.tenant_id,
                Entity.entity_type == EntityType.ORGANIZATION,
                Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
            )
        )
        if company is None:
            return None

        deal_filters = self._deal_filters(company_entity_id)
        program_events = select(
            literal("program_status").label("event_type"),
            DevelopmentProgram.id.label("record_id"),
            DevelopmentProgram.status_date.label("occurred_at"),
        ).where(
            DevelopmentProgram.tenant_id == self.tenant_id,
            DevelopmentProgram.organization_entity_id == company_entity_id,
            DevelopmentProgram.status_date.is_not(None),
        )
        deal_events = select(
            literal("deal_announced").label("event_type"),
            DealProfile.id.label("record_id"),
            DealProfile.announced_at.label("occurred_at"),
        ).where(*deal_filters, DealProfile.announced_at.is_not(None))
        timeline = union_all(program_events, deal_events).subquery()
        total = self.session.scalar(select(func.count()).select_from(timeline)) or 0
        rows = self.session.execute(
            select(timeline.c.event_type, timeline.c.record_id, timeline.c.occurred_at)
            .order_by(timeline.c.occurred_at.desc(), timeline.c.event_type, timeline.c.record_id)
            .limit(limit)
            .offset(offset)
        ).all()

        program_ids = [record_id for event_type, record_id, _occurred_at in rows if event_type == "program_status"]
        deal_ids = [record_id for event_type, record_id, _occurred_at in rows if event_type == "deal_announced"]
        programs = {
            item.id: item
            for item in self._read_programs(
                [
                    DevelopmentProgram.tenant_id == self.tenant_id,
                    DevelopmentProgram.id.in_(program_ids),
                ],
                len(program_ids),
                0,
            )
        }
        deals = {
            item.id: item
            for item in self._deal_search_items(
                [DealProfile.tenant_id == self.tenant_id, DealProfile.id.in_(deal_ids)],
                len(deal_ids),
                0,
            )
        }

        items: list[CompanyTimelineEventRead] = []
        for event_type, record_id, occurred_at in rows:
            normalized_occurred_at = (
                occurred_at.replace(tzinfo=UTC)
                if occurred_at is not None and occurred_at.tzinfo is None
                else occurred_at
            )
            if event_type == "program_status":
                program = programs[record_id]
                items.append(
                    CompanyTimelineEventRead(
                        id=f"program_status:{record_id}",
                        event_type="program_status",
                        occurred_at=normalized_occurred_at,
                        title=f"{program.drug_name} · {program.phase}",
                        program=program,
                    )
                )
            else:
                deal = deals[record_id]
                items.append(
                    CompanyTimelineEventRead(
                        id=f"deal_announced:{record_id}",
                        event_type="deal_announced",
                        occurred_at=normalized_occurred_at,
                        title=deal.name,
                        deal=deal,
                    )
                )

        facets = {
            "event_type": {
                str(value): int(count)
                for value, count in self.session.execute(
                    select(timeline.c.event_type, func.count())
                    .select_from(timeline)
                    .group_by(timeline.c.event_type)
                    .order_by(timeline.c.event_type)
                ).all()
            },
            "phase": {
                value.value if hasattr(value, "value") else str(value): int(count)
                for value, count in self.session.execute(
                    select(DevelopmentProgram.phase, func.count(DevelopmentProgram.id))
                    .where(
                        DevelopmentProgram.tenant_id == self.tenant_id,
                        DevelopmentProgram.organization_entity_id == company_entity_id,
                        DevelopmentProgram.status_date.is_not(None),
                    )
                    .group_by(DevelopmentProgram.phase)
                    .order_by(func.count(DevelopmentProgram.id).desc(), DevelopmentProgram.phase)
                ).all()
            },
            "deal_type": {
                str(value): int(count)
                for value, count in self.session.execute(
                    select(DealProfile.deal_type, func.count(DealProfile.id))
                    .where(*deal_filters, DealProfile.announced_at.is_not(None))
                    .group_by(DealProfile.deal_type)
                    .order_by(func.count(DealProfile.id).desc(), DealProfile.deal_type)
                ).all()
            },
        }
        return CompanyTimelineResult(
            company=EntityRead.model_validate(company),
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            facets=facets,
            as_of=datetime.now(UTC),
            warnings=["时间线仅包含具有明确日期的管线当前状态和已披露交易公告；未观察到记录不代表公司不存在相关活动。"],
        )

    def _deal_search_items(
        self,
        filters: list[ColumnElement[bool]],
        limit: int,
        offset: int,
        *,
        sort_by: DealSortField = "announced_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[DealSortField]] | None = None,
    ) -> list[DealSearchItemRead]:
        effective_sort = validate_sort_clauses(
            sort,
            DEAL_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        deal_entity = aliased(Entity)
        status_rank = case(
            {
                "announced": 0,
                "active": 1,
                "completed": 2,
                "terminated": 3,
                "withdrawn": 4,
                "superseded": 5,
                "unknown": 6,
            },
            value=DealProfile.status,
            else_=7,
        )
        sort_expressions: dict[DealSortField, Any] = {
            "announced_at": DealProfile.announced_at,
            "name": func.lower(deal_entity.name),
            "deal_type": func.lower(DealProfile.deal_type),
            "status": status_rank,
            "direction": func.lower(DealProfile.direction),
            "territory": func.lower(DealProfile.territory),
            "upfront_amount": DealProfile.upfront_amount,
            "total_potential_amount": DealProfile.total_potential_amount,
        }
        ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
        deal_rows = self.session.execute(
            select(DealProfile, deal_entity.name)
            .join(
                deal_entity,
                and_(deal_entity.tenant_id == self.tenant_id, deal_entity.id == DealProfile.entity_id),
            )
            .where(*filters)
            .order_by(*ordered_sort, func.lower(deal_entity.name), DealProfile.id)
            .limit(limit)
            .offset(offset)
        ).all()
        rows = [row for row, _name in deal_rows]
        name_by_deal = {row.entity_id: name for row, name in deal_rows}
        linked_by_deal: dict[str, dict[str, dict[str, DealLinkedEntityRead]]] = {
            row.entity_id: {"party": {}, "asset": {}} for row in rows
        }
        party_roles_by_deal: dict[str, list[DealPartyAssociationRead]] = {row.id: [] for row in rows}
        asset_stages_by_deal: dict[str, list[DealAssetAssociationRead]] = {row.id: [] for row in rows}
        rights_by_deal: dict[str, list[DealRightRead]] = {row.id: [] for row in rows}
        deal_entity_ids = list(linked_by_deal)
        if deal_entity_ids:
            linked_rows = self.session.execute(
                select(Relationship.subject_id, Relationship.predicate, Entity)
                .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == Relationship.object_id))
                .where(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.predicate.in_(["deal_party", "deal_asset"]),
                    Relationship.subject_id.in_(deal_entity_ids),
                )
                .order_by(Relationship.subject_id, Relationship.predicate, Entity.entity_type, Entity.name, Entity.id)
            ).all()
            for deal_entity_id, predicate, entity in linked_rows:
                group = "party" if predicate == "deal_party" else "asset"
                linked_by_deal[deal_entity_id][group][entity.id] = DealLinkedEntityRead(
                    id=entity.id,
                    name=entity.name,
                    entity_type=entity.entity_type,
                )
            legacy_ids = {
                entity_id
                for row in rows
                for entity_id in [
                    *row.asset_entity_ids,
                    *(str(item.get("entity_id")) for item in row.parties if item.get("entity_id")),
                ]
            }
            if legacy_ids:
                legacy_entities = self.session.scalars(
                    select(Entity)
                    .where(Entity.tenant_id == self.tenant_id, Entity.id.in_(legacy_ids))
                    .order_by(Entity.entity_type, Entity.name, Entity.id)
                ).all()
                entity_by_id = {entity.id: entity for entity in legacy_entities}
                for row in rows:
                    for item in row.parties:
                        entity_id = str(item.get("entity_id") or "")
                        if entity := entity_by_id.get(entity_id):
                            linked_by_deal[row.entity_id]["party"].setdefault(
                                entity.id,
                                DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
                            )
                    for entity_id in row.asset_entity_ids:
                        if entity := entity_by_id.get(entity_id):
                            linked_by_deal[row.entity_id]["asset"].setdefault(
                                entity.id,
                                DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
                            )
        deal_ids = list(party_roles_by_deal)
        if deal_ids:
            party_rows = self.session.execute(
                select(DealPartyAssociation, Entity)
                .join(
                    Entity,
                    and_(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id == DealPartyAssociation.party_entity_id,
                    ),
                )
                .where(
                    DealPartyAssociation.tenant_id == self.tenant_id,
                    DealPartyAssociation.deal_id.in_(deal_ids),
                )
                .order_by(DealPartyAssociation.deal_id, DealPartyAssociation.role, Entity.name, Entity.id)
            ).all()
            profile_by_id = {row.id: row for row in rows}
            for association, entity in party_rows:
                party_roles_by_deal[association.deal_id].append(
                    DealPartyAssociationRead(
                        id=entity.id,
                        name=entity.name,
                        entity_type=entity.entity_type,
                        role=association.role,
                        country_region=association.country_region,
                        organization_type=association.organization_type,
                    )
                )
                deal_profile = profile_by_id[association.deal_id]
                linked_by_deal[deal_profile.entity_id]["party"].setdefault(
                    entity.id,
                    DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
                )

            asset_rows = self.session.execute(
                select(DealAssetAssociation, Entity)
                .join(
                    Entity,
                    and_(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id == DealAssetAssociation.asset_entity_id,
                    ),
                )
                .where(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id.in_(deal_ids),
                )
                .order_by(DealAssetAssociation.deal_id, Entity.entity_type, Entity.name, Entity.id)
            ).all()
            asset_entity_ids = {entity.id for _association, entity in asset_rows}
            current_program_by_asset: dict[str, tuple[str, datetime | None]] = {}
            if asset_entity_ids:
                current_programs = self._current_program_phase_projection()
                program_rows = self.session.execute(
                    select(
                        current_programs.c.drug_entity_id,
                        current_programs.c.phase,
                        current_programs.c.status_date,
                    ).where(current_programs.c.drug_entity_id.in_(asset_entity_ids))
                ).all()
                for asset_entity_id, phase, status_date in program_rows:
                    phase_value = phase.value if hasattr(phase, "value") else str(phase)
                    current_program_by_asset[asset_entity_id] = (phase_value, status_date)
            for association, entity in asset_rows:
                current_program = current_program_by_asset.get(entity.id)
                asset_stages_by_deal[association.deal_id].append(
                    DealAssetAssociationRead(
                        id=entity.id,
                        name=entity.name,
                        entity_type=entity.entity_type,
                        development_phase_at_transaction=association.development_phase_at_transaction,
                        current_development_phase=current_program[0] if current_program else None,
                        current_phase_as_of=current_program[1] if current_program else None,
                    )
                )
                deal_profile = profile_by_id[association.deal_id]
                linked_by_deal[deal_profile.entity_id]["asset"].setdefault(
                    entity.id,
                    DealLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type),
                )

            right_rows = self.session.execute(
                select(DealRight, Entity)
                .join(
                    Entity,
                    and_(Entity.tenant_id == self.tenant_id, Entity.id == DealRight.holder_entity_id),
                )
                .where(DealRight.tenant_id == self.tenant_id, DealRight.deal_id.in_(deal_ids))
                .order_by(DealRight.deal_id, DealRight.right_type, DealRight.territory, Entity.name)
            ).all()
            for right, holder in right_rows:
                rights_by_deal[right.deal_id].append(
                    DealRightRead(
                        id=right.id,
                        holder_entity_id=holder.id,
                        holder_name=holder.name,
                        right_type=right.right_type,
                        territory=right.territory,
                        exclusive=right.exclusive,
                        scope_description=right.scope_description,
                        source_document_id=right.source_document_id,
                    )
                )
        return [
            DealSearchItemRead(
                **DealRead.model_validate(row).model_dump(),
                name=name_by_deal[row.entity_id],
                party_entities=list(linked_by_deal[row.entity_id]["party"].values()),
                asset_entities=list(linked_by_deal[row.entity_id]["asset"].values()),
                party_roles=party_roles_by_deal[row.id],
                asset_stages=asset_stages_by_deal[row.id],
                rights=rights_by_deal[row.id],
            )
            for row in rows
        ]

    def regulatory_events(
        self,
        entity_id: str | None,
        query: str | None,
        agency: str | None,
        limit: int,
        offset: int = 0,
        jurisdiction: str | None = None,
        event_type: str | None = None,
        status: str | None = None,
    ) -> list[RegulatoryEventRead]:
        filters = self._regulatory_filters(
            entity_id,
            query,
            agency,
            jurisdiction=jurisdiction,
            event_type=event_type,
            status=status,
        )
        rows = self.session.scalars(
            select(RegulatoryEvent)
            .where(*filters)
            .order_by(RegulatoryEvent.decision_date.desc().nullslast(), RegulatoryEvent.id)
            .limit(limit)
            .offset(offset)
        ).all()
        return [RegulatoryEventRead.model_validate(row) for row in rows]

    def search_regulatory_events(
        self,
        query: str | None,
        agency: str | None,
        jurisdiction: str | None,
        event_type: str | None,
        status: str | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        designation_type: str | None = None,
        label_change_type: str | None = None,
        has_boxed_warning: bool | None = None,
        safety_signal_type: str | None = None,
        safety_severity: str | None = None,
        safety_status: str | None = None,
        decision_from: datetime | None = None,
        decision_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        sort_by: RegulatorySortField = "decision_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[RegulatorySortField]] | None = None,
    ) -> RegulatoryEventSearchResult:
        effective_sort = validate_sort_clauses(
            sort,
            REGULATORY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        filters = self._regulatory_filters(
            entity_id,
            query,
            agency,
            jurisdiction=jurisdiction,
            event_type=event_type,
            status=status,
            designation_type=designation_type,
            label_change_type=label_change_type,
            has_boxed_warning=has_boxed_warning,
            safety_signal_type=safety_signal_type,
            safety_severity=safety_severity,
            safety_status=safety_status,
            decision_from=decision_from,
            decision_to=decision_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
        )
        items = self._regulatory_search_items(
            filters,
            limit,
            offset,
            sort=effective_sort,
        )
        facet_source = (
            select(
                RegulatoryEvent.id.label("event_id"),
                RegulatoryEvent.agency.label("agency"),
                RegulatoryEvent.jurisdiction.label("jurisdiction"),
                RegulatoryEvent.event_type.label("event_type"),
                RegulatoryEvent.status.label("status"),
                RegulatoryEvent.designation_type.label("designation_type"),
                RegulatoryEvent.label_change_type.label("label_change_type"),
                RegulatoryEvent.has_boxed_warning.label("has_boxed_warning"),
                RegulatoryEvent.safety_signal_type.label("safety_signal_type"),
                RegulatoryEvent.safety_severity.label("safety_severity"),
                RegulatoryEvent.safety_status.label("safety_status"),
                RegulatoryEvent.decision_date.label("decision_date"),
            )
            .where(*filters)
            .subquery()
        )
        total = self.session.scalar(select(func.count()).select_from(facet_source)) or 0
        facets = {
            name: self._scalar_facet_counts(facet_source, name)
            for name in (
                "agency",
                "jurisdiction",
                "event_type",
                "status",
                "designation_type",
                "label_change_type",
                "has_boxed_warning",
                "safety_signal_type",
                "safety_severity",
                "safety_status",
            )
        }
        landscape = self._regulatory_landscape(facet_source, total)
        return RegulatoryEventSearchResult(
            query_schema_version="pharma.regulatory.search.v4",
            applied_filters=self._applied_filters(
                ("entity_id", "eq", entity_id),
                ("q", "contains", query.strip() if query else None),
                ("agency", "eq", agency),
                ("jurisdiction", "eq", jurisdiction),
                ("event_type", "eq", event_type),
                ("status", "eq", status),
                ("designation_type", "eq", designation_type),
                ("label_change_type", "eq", label_change_type),
                ("has_boxed_warning", "eq", has_boxed_warning),
                ("safety_signal_type", "eq", safety_signal_type),
                ("safety_severity", "eq", safety_severity),
                ("safety_status", "eq", safety_status),
                ("decision_from", "gte", decision_from.isoformat() if decision_from else None),
                ("decision_to", "lte", decision_to.isoformat() if decision_to else None),
                ("source_updated_from", "gte", source_updated_from.isoformat() if source_updated_from else None),
                ("source_updated_to", "lte", source_updated_to.isoformat() if source_updated_to else None),
            ),
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=effective_sort[0].field,
            sort_direction=effective_sort[0].direction,
            sort=_sort_criteria_read(effective_sort),
            facets=facets,
            landscape=landscape,
            as_of=datetime.now(UTC),
            warnings=["未观察到监管事件不代表不存在；结果受监管辖区、数据授权、更新时效和治理状态限制。"],
        )

    def regulatory_saved_search_matches_entity(
        self,
        entity_id: str,
        query: RegulatorySavedSearchQuery,
    ) -> bool:
        def start(value: Any) -> datetime | None:
            return datetime.combine(value, time.min, tzinfo=UTC) if value else None

        def end(value: Any) -> datetime | None:
            return datetime.combine(value, time.max, tzinfo=UTC) if value else None

        filters = self._regulatory_filters(
            entity_id,
            query.q,
            query.agency,
            jurisdiction=query.jurisdiction,
            event_type=query.event_type,
            status=query.status,
            designation_type=query.designation_type.value if query.designation_type else None,
            label_change_type=query.label_change_type.value if query.label_change_type else None,
            has_boxed_warning=query.has_boxed_warning,
            safety_signal_type=query.safety_signal_type.value if query.safety_signal_type else None,
            safety_severity=query.safety_severity.value if query.safety_severity else None,
            safety_status=query.safety_status.value if query.safety_status else None,
            decision_from=start(query.decision_from),
            decision_to=end(query.decision_to),
            source_updated_from=start(query.source_updated_from),
            source_updated_to=end(query.source_updated_to),
        )
        statement = select(RegulatoryEvent.id).where(*filters)
        return self.session.scalar(statement.with_only_columns(literal(True)).limit(1)) is True

    def regulatory_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        agency: str | None,
        jurisdiction: str | None,
        event_type: str | None,
        status: str | None,
        limit: int,
        offset: int = 0,
        *,
        designation_type: str | None = None,
        label_change_type: str | None = None,
        has_boxed_warning: bool | None = None,
        safety_signal_type: str | None = None,
        safety_severity: str | None = None,
        safety_status: str | None = None,
        decision_from: datetime | None = None,
        decision_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        sort_by: RegulatorySortField = "decision_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[RegulatorySortField]] | None = None,
    ) -> list[RegulatoryEventSearchItemRead]:
        filters = self._regulatory_filters(
            entity_id,
            query,
            agency,
            jurisdiction=jurisdiction,
            event_type=event_type,
            status=status,
            designation_type=designation_type,
            label_change_type=label_change_type,
            has_boxed_warning=has_boxed_warning,
            safety_signal_type=safety_signal_type,
            safety_severity=safety_severity,
            safety_status=safety_status,
            decision_from=decision_from,
            decision_to=decision_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
        )
        return self._regulatory_search_items(
            filters,
            limit,
            offset,
            sort=validate_sort_clauses(
                sort,
                REGULATORY_SORT_FIELDS,
                default_field=sort_by,
                default_direction=sort_direction,
            ),
        )

    def regulatory_event_detail(self, event_id: str) -> RegulatoryEventSearchItemRead | None:
        items = self._regulatory_search_items(
            [
                RegulatoryEvent.tenant_id == self.tenant_id,
                RegulatoryEvent.id == event_id,
                self._published_entity_exists(RegulatoryEvent.subject_entity_id),
            ],
            1,
            0,
        )
        return items[0] if items else None

    def _regulatory_search_items(
        self,
        filters: list[ColumnElement[bool]],
        limit: int,
        offset: int,
        *,
        sort_by: RegulatorySortField = "decision_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[RegulatorySortField]] | None = None,
    ) -> list[RegulatoryEventSearchItemRead]:
        effective_sort = validate_sort_clauses(
            sort,
            REGULATORY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        subject_name = (
            select(func.lower(Entity.name))
            .where(
                Entity.tenant_id == self.tenant_id,
                Entity.id == RegulatoryEvent.subject_entity_id,
            )
            .correlate(RegulatoryEvent)
            .scalar_subquery()
        )
        sort_expressions: dict[RegulatorySortField, Any] = {
            "decision_date": RegulatoryEvent.decision_date,
            "title": func.lower(RegulatoryEvent.title),
            "agency": func.lower(RegulatoryEvent.agency),
            "jurisdiction": func.lower(RegulatoryEvent.jurisdiction),
            "event_type": func.lower(RegulatoryEvent.event_type),
            "status": func.lower(RegulatoryEvent.status),
            "subject": subject_name,
            "source_updated_at": RegulatoryEvent.source_updated_at,
        }
        ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
        rows = self.session.scalars(
            select(RegulatoryEvent)
            .where(*filters)
            .order_by(
                *ordered_sort,
                RegulatoryEvent.event_identifier,
                RegulatoryEvent.id,
            )
            .limit(limit)
            .offset(offset)
        ).all()
        entity_ids = {
            entity_id
            for row in rows
            for entity_id in (row.subject_entity_id, row.indication_entity_id, row.organization_entity_id)
            if entity_id
        }
        entities = (
            self.session.scalars(
                select(Entity)
                .where(Entity.tenant_id == self.tenant_id, Entity.id.in_(entity_ids))
                .order_by(Entity.entity_type, Entity.name, Entity.id)
            ).all()
            if entity_ids
            else []
        )
        linked_by_id = {
            entity.id: RegulatoryEventLinkedEntityRead(
                id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
            )
            for entity in entities
        }
        return [
            RegulatoryEventSearchItemRead(
                **RegulatoryEventRead.model_validate(row).model_dump(),
                subject_entity=linked_by_id[row.subject_entity_id],
                indication_entity=linked_by_id.get(row.indication_entity_id or ""),
                organization_entity=linked_by_id.get(row.organization_entity_id or ""),
            )
            for row in rows
        ]

    def search_epidemiology_observations(
        self,
        query: str | None,
        measure: str | None,
        geography: str | None,
        unit: str | None,
        population_scope: str | None,
        age_group: str | None,
        sex: str | None,
        period_start_from: datetime | None,
        period_end_to: datetime | None,
        limit: int,
        offset: int,
        *,
        disease_entity_id: str | None = None,
        patient_population_id: str | None = None,
        sort_by: EpidemiologySortField = "period_end",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
    ) -> EpidemiologyObservationSearchResult:
        effective_sort = validate_sort_clauses(
            sort,
            EPIDEMIOLOGY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        filters = self._epidemiology_filters(
            disease_entity_id,
            patient_population_id,
            query,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            period_start_from,
            period_end_to,
        )
        items = self._epidemiology_search_items(
            filters,
            limit,
            offset,
            sort=effective_sort,
        )
        facet_source = (
            select(
                EpidemiologyObservation.id.label("observation_id"),
                EpidemiologyObservation.disease_entity_id.label("disease_entity_id"),
                EpidemiologyObservation.patient_population_id.label("patient_population_id"),
                EpidemiologyObservation.publisher_entity_id.label("publisher_entity_id"),
                EpidemiologyObservation.measure.label("measure"),
                EpidemiologyObservation.geography.label("geography"),
                EpidemiologyObservation.unit.label("unit"),
                EpidemiologyObservation.population_scope.label("population_scope"),
                EpidemiologyObservation.age_group.label("age_group"),
                EpidemiologyObservation.sex.label("sex"),
            )
            .where(*filters)
            .subquery()
        )
        total = self.session.scalar(select(func.count()).select_from(facet_source)) or 0
        facets = {
            name: self._scalar_facet_counts(facet_source, name)
            for name in ("measure", "geography", "unit", "population_scope", "age_group", "sex")
        }
        facets["disease"] = self._linked_entity_facets(facet_source, "disease_entity_id", "observation_id")
        facets["publisher"] = self._linked_entity_facets(facet_source, "publisher_entity_id", "observation_id")
        landscape = EpidemiologyLandscapeRead(
            total_observations=total,
            measure=self._landscape_scalar_buckets(facet_source, "measure", total, EpidemiologyLandscapeBucketRead),
            geography=self._landscape_scalar_buckets(facet_source, "geography", total, EpidemiologyLandscapeBucketRead),
            population_scope=self._landscape_scalar_buckets(
                facet_source, "population_scope", total, EpidemiologyLandscapeBucketRead
            ),
        )
        population_facet_source = (
            select(
                EpidemiologyObservation.id.label("observation_id"),
                EpidemiologyObservation.patient_population_id.label("patient_population_id"),
            )
            .where(
                *self._epidemiology_filters(
                    disease_entity_id,
                    None,
                    query,
                    measure,
                    geography,
                    unit,
                    population_scope,
                    age_group,
                    sex,
                    period_start_from,
                    period_end_to,
                )
            )
            .subquery()
        )
        population_counts = self.session.execute(
            select(
                PatientPopulation.id,
                PatientPopulation.name,
                func.count(func.distinct(population_facet_source.c.observation_id)),
            )
            .select_from(population_facet_source)
            .join(
                PatientPopulation,
                and_(
                    PatientPopulation.tenant_id == self.tenant_id,
                    PatientPopulation.id == population_facet_source.c.patient_population_id,
                    PatientPopulation.review_status == ReviewStatus.VERIFIED,
                ),
            )
            .group_by(PatientPopulation.id, PatientPopulation.name)
            .order_by(
                func.count(func.distinct(population_facet_source.c.observation_id)).desc(),
                PatientPopulation.name,
            )
        ).all()
        return EpidemiologyObservationSearchResult(
            query_schema_version="pharma.epidemiology.search.v3",
            applied_filters=self._applied_filters(
                ("disease_entity_id", "eq", disease_entity_id),
                ("patient_population_id", "eq", patient_population_id),
                ("q", "contains", query.strip() if query else None),
                ("measure", "eq", measure),
                ("geography", "eq", geography),
                ("unit", "eq", unit),
                ("population_scope", "eq", population_scope),
                ("age_group", "eq", age_group),
                ("sex", "eq", sex),
                ("period_start_from", "gte", period_start_from.isoformat() if period_start_from else None),
                ("period_end_to", "lte", period_end_to.isoformat() if period_end_to else None),
            ),
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            sort_by=effective_sort[0].field,
            sort_direction=effective_sort[0].direction,
            sort=_sort_criteria_read(effective_sort),
            facets=facets,
            landscape=landscape,
            patient_populations=[
                PatientPopulationOptionRead(id=population_id, name=name, count=count)
                for population_id, name, count in population_counts
            ],
            as_of=datetime.now(UTC),
            warnings=["未观察到流行病学估计不代表患者不存在；结果受地域、统计口径、模型方法、来源时效和数据授权限制。"],
        )

    def epidemiology_search_items(
        self,
        disease_entity_id: str | None,
        query: str | None,
        measure: str | None,
        geography: str | None,
        unit: str | None,
        population_scope: str | None,
        age_group: str | None,
        sex: str | None,
        period_start_from: datetime | None,
        period_end_to: datetime | None,
        limit: int,
        offset: int = 0,
        *,
        patient_population_id: str | None = None,
        sort_by: EpidemiologySortField = "period_end",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
    ) -> list[EpidemiologyObservationSearchItemRead]:
        filters = self._epidemiology_filters(
            disease_entity_id,
            patient_population_id,
            query,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            period_start_from,
            period_end_to,
        )
        return self._epidemiology_search_items(
            filters,
            limit,
            offset,
            sort=validate_sort_clauses(
                sort,
                EPIDEMIOLOGY_SORT_FIELDS,
                default_field=sort_by,
                default_direction=sort_direction,
            ),
        )

    def epidemiology_saved_search_matches_entity(
        self,
        entity_id: str,
        query: EpidemiologySavedSearchQuery,
    ) -> bool:
        def start(value: Any) -> datetime | None:
            return datetime.combine(value, time.min, tzinfo=UTC) if value else None

        def end(value: Any) -> datetime | None:
            return datetime.combine(value, time.max, tzinfo=UTC) if value else None

        filters = self._epidemiology_filters(
            query.disease_entity_id,
            query.patient_population_id,
            query.q,
            query.measure,
            query.geography,
            query.unit,
            query.population_scope,
            query.age_group,
            query.sex,
            start(query.period_start_from),
            end(query.period_end_to),
        )
        related_populations = select(PatientPopulationEntityLink.patient_population_id).where(
            PatientPopulationEntityLink.tenant_id == self.tenant_id,
            PatientPopulationEntityLink.entity_id == entity_id,
        )
        filters.append(
            or_(
                EpidemiologyObservation.disease_entity_id == entity_id,
                EpidemiologyObservation.publisher_entity_id == entity_id,
                EpidemiologyObservation.patient_population_id.in_(related_populations),
            )
        )
        statement = select(EpidemiologyObservation.id).where(*filters)
        return self.session.scalar(statement.with_only_columns(literal(True)).limit(1)) is True

    def epidemiology_trend(
        self,
        disease_entity_id: str,
        measure: str | None,
        geography: str | None,
        unit: str | None,
        population_scope: str | None,
        age_group: str | None,
        sex: str | None,
        limit: int,
        *,
        patient_population_id: str | None = None,
        anchor_observation_id: str | None = None,
    ) -> EpidemiologyTrendResult | None:
        disease = self.session.scalar(
            select(Entity).where(
                Entity.tenant_id == self.tenant_id,
                Entity.id == disease_entity_id,
                Entity.entity_type == EntityType.DISEASE,
            )
        )
        if disease is None:
            return None
        anchor = None
        if anchor_observation_id:
            anchor = self.session.scalar(
                select(EpidemiologyObservation).where(
                    EpidemiologyObservation.tenant_id == self.tenant_id,
                    EpidemiologyObservation.id == anchor_observation_id,
                    EpidemiologyObservation.disease_entity_id == disease_entity_id,
                )
            )
            if anchor is None:
                return None
            filters = self._epidemiology_filters(
                disease_entity_id,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
            for column, value in (
                (EpidemiologyObservation.patient_population_id, anchor.patient_population_id),
                (EpidemiologyObservation.measure, anchor.measure),
                (EpidemiologyObservation.geography, anchor.geography),
                (EpidemiologyObservation.unit, anchor.unit),
                (EpidemiologyObservation.population_scope, anchor.population_scope),
                (EpidemiologyObservation.age_group, anchor.age_group),
                (EpidemiologyObservation.sex, anchor.sex),
                (EpidemiologyObservation.publisher_entity_id, anchor.publisher_entity_id),
                (EpidemiologyObservation.methodology, anchor.methodology),
            ):
                filters.append(column.is_(None) if value is None else column == value)
        else:
            filters = self._epidemiology_filters(
                disease_entity_id,
                patient_population_id,
                None,
                measure,
                geography,
                unit,
                population_scope,
                age_group,
                sex,
                None,
                None,
            )
        total = int(self.session.scalar(select(func.count()).select_from(EpidemiologyObservation).where(*filters)) or 0)
        items = self._epidemiology_search_items(
            filters,
            limit,
            0,
            sort_by="period_end",
            sort_direction="asc",
        )
        return EpidemiologyTrendResult(
            disease=EpidemiologyLinkedEntityRead(
                id=disease.id,
                name=disease.name,
                entity_type=disease.entity_type,
            ),
            anchor_observation_id=anchor.id if anchor else None,
            items=items,
            total=total,
            truncated=total > len(items),
            as_of=datetime.now(UTC),
            warnings=["趋势仅比较相同指标、单位和人群口径；不同来源或方法学估计不可直接合并。"],
        )

    def _epidemiology_search_items(
        self,
        filters: list[ColumnElement[bool]],
        limit: int,
        offset: int,
        *,
        sort_by: EpidemiologySortField = "period_end",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
    ) -> list[EpidemiologyObservationSearchItemRead]:
        effective_sort = validate_sort_clauses(
            sort,
            EPIDEMIOLOGY_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        disease_name = (
            select(func.lower(Entity.name))
            .where(
                Entity.tenant_id == self.tenant_id,
                Entity.id == EpidemiologyObservation.disease_entity_id,
            )
            .correlate(EpidemiologyObservation)
            .scalar_subquery()
        )
        publisher_name = (
            select(func.lower(Entity.name))
            .where(
                Entity.tenant_id == self.tenant_id,
                Entity.id == EpidemiologyObservation.publisher_entity_id,
            )
            .correlate(EpidemiologyObservation)
            .scalar_subquery()
        )
        sort_expressions: dict[EpidemiologySortField, Any] = {
            "period_end": EpidemiologyObservation.period_end,
            "period_start": EpidemiologyObservation.period_start,
            "disease": disease_name,
            "measure": func.lower(EpidemiologyObservation.measure),
            "value": EpidemiologyObservation.value,
            "geography": func.lower(EpidemiologyObservation.geography),
            "unit": func.lower(EpidemiologyObservation.unit),
            "publisher": publisher_name,
            "sample_size": EpidemiologyObservation.sample_size,
        }
        ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
        rows = self.session.scalars(
            select(EpidemiologyObservation)
            .where(*filters)
            .order_by(*ordered_sort, EpidemiologyObservation.observation_identifier, EpidemiologyObservation.id)
            .limit(limit)
            .offset(offset)
        ).all()
        population_ids = {row.patient_population_id for row in rows if row.patient_population_id}
        populations = (
            self.session.scalars(
                select(PatientPopulation).where(
                    PatientPopulation.tenant_id == self.tenant_id,
                    PatientPopulation.id.in_(population_ids),
                    PatientPopulation.review_status == ReviewStatus.VERIFIED,
                )
            ).all()
            if population_ids
            else []
        )
        population_links = (
            self.session.scalars(
                select(PatientPopulationEntityLink).where(
                    PatientPopulationEntityLink.tenant_id == self.tenant_id,
                    PatientPopulationEntityLink.patient_population_id.in_(population_ids),
                )
            ).all()
            if population_ids
            else []
        )
        entity_ids = {
            entity_id for row in rows for entity_id in (row.disease_entity_id, row.publisher_entity_id) if entity_id
        }
        entity_ids.update(link.entity_id for link in population_links)
        entities = (
            self.session.scalars(
                select(Entity)
                .where(Entity.tenant_id == self.tenant_id, Entity.id.in_(entity_ids))
                .order_by(Entity.entity_type, Entity.name, Entity.id)
            ).all()
            if entity_ids
            else []
        )
        linked_by_id = {
            entity.id: EpidemiologyLinkedEntityRead(
                id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
            )
            for entity in entities
        }
        population_reads: dict[str, PatientPopulationRead] = {}
        for population in populations:
            links = [link for link in population_links if link.patient_population_id == population.id]
            population_reads[population.id] = PatientPopulationRead(
                id=population.id,
                population_key=population.population_key,
                name=population.name,
                description=population.description,
                attributes=population.attributes,
                disease_entities=[
                    linked_by_id[link.entity_id]
                    for link in links
                    if link.relationship == "disease"
                    and link.entity_id in linked_by_id
                    and linked_by_id[link.entity_id].entity_type == EntityType.DISEASE
                ],
                target_entities=[
                    linked_by_id[link.entity_id]
                    for link in links
                    if link.relationship == "target"
                    and link.entity_id in linked_by_id
                    and linked_by_id[link.entity_id].entity_type == EntityType.TARGET
                ],
            )
        return [
            EpidemiologyObservationSearchItemRead(
                **EpidemiologyObservationRead.model_validate(row).model_dump(),
                disease_entity=linked_by_id[row.disease_entity_id],
                publisher_entity=linked_by_id.get(row.publisher_entity_id or ""),
                patient_population=population_reads.get(row.patient_population_id or ""),
            )
            for row in rows
        ]

    def search_news_events(
        self,
        query: str | None,
        event_type: str | None,
        publisher: str | None,
        language: str | None,
        venue: str | None,
        published_from: datetime | None,
        published_to: datetime | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        research_content_only: bool = False,
        sort_by: NewsSortField = "published_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[NewsSortField]] | None = None,
    ) -> NewsEventSearchResult:
        effective_sort = validate_sort_clauses(
            sort,
            NEWS_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        filters = self._news_event_filters(
            entity_id,
            query,
            event_type,
            publisher,
            language,
            venue,
            published_from,
            published_to,
        )
        if research_content_only:
            filters.append(NewsEvent.event_type.in_(RESEARCH_PUBLICATION_EVENT_TYPES))
        items = self._news_event_search_items(
            filters,
            limit,
            offset,
            sort=effective_sort,
        )
        facet_source = (
            select(
                NewsEvent.id.label("event_id"),
                NewsEvent.event_type.label("event_type"),
                NewsEvent.language.label("language"),
                NewsEvent.venue.label("venue"),
                NewsEvent.publisher_entity_id.label("publisher_entity_id"),
                NewsEvent.published_at.label("published_at"),
            )
            .where(*filters)
            .subquery()
        )
        facets = {name: self._scalar_facet_counts(facet_source, name) for name in ("event_type", "language", "venue")}
        facets["publisher"] = self._linked_entity_facets(facet_source, "publisher_entity_id", "event_id")
        news_total = int(self.session.scalar(select(func.count()).select_from(facet_source)) or 0)
        year_column = func.extract("year", facet_source.c.published_at)
        year_rows = self.session.execute(
            select(year_column.label("published_year"), func.count())
            .select_from(facet_source)
            .group_by("published_year")
        ).all()
        published_year = sorted(
            (
                NewsLandscapeBucketRead(
                    key="__missing__" if year is None else str(int(year)),
                    label="未披露" if year is None else str(int(year)),
                    count=int(count),
                    share=(int(count) / news_total) if news_total else 0.0,
                )
                for year, count in year_rows
            ),
            key=lambda item: (item.key == "__missing__", item.key),
            reverse=True,
        )
        landscape = NewsLandscapeRead(
            total_events=news_total,
            event_type=self._landscape_scalar_buckets(facet_source, "event_type", news_total, NewsLandscapeBucketRead),
            venue=self._landscape_scalar_buckets(facet_source, "venue", news_total, NewsLandscapeBucketRead),
            published_year=published_year,
        )
        return NewsEventSearchResult(
            query_schema_version="pharma.news.search.v2",
            applied_filters=self._applied_filters(
                ("entity_id", "eq", entity_id),
                ("q", "contains", query.strip() if query else None),
                ("event_type", "eq", event_type),
                ("publisher", "contains", publisher),
                ("language", "eq", language),
                ("venue", "contains", venue),
                ("published_from", "gte", published_from.isoformat() if published_from else None),
                ("published_to", "lte", published_to.isoformat() if published_to else None),
                ("content_scope", "eq", "research" if research_content_only else None),
            ),
            items=items,
            total=news_total,
            limit=limit,
            offset=offset,
            sort_by=effective_sort[0].field,
            sort_direction=effective_sort[0].direction,
            sort=_sort_criteria_read(effective_sort),
            facets=facets,
            landscape=landscape,
            as_of=datetime.now(UTC),
            warnings=["未观察到事件不代表事件未发生；结果受来源授权、抓取时效、实体治理和发布时间完整性限制。"],
        )

    def news_event_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        event_type: str | None,
        publisher: str | None,
        language: str | None,
        venue: str | None,
        published_from: datetime | None,
        published_to: datetime | None,
        limit: int,
        offset: int = 0,
        *,
        sort_by: NewsSortField = "published_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[NewsSortField]] | None = None,
    ) -> list[NewsEventSearchItemRead]:
        return self._news_event_search_items(
            self._news_event_filters(
                entity_id,
                query,
                event_type,
                publisher,
                language,
                venue,
                published_from,
                published_to,
            ),
            limit,
            offset,
            sort=validate_sort_clauses(
                sort,
                NEWS_SORT_FIELDS,
                default_field=sort_by,
                default_direction=sort_direction,
            ),
        )

    def news_saved_search_matches_entity(self, entity_id: str, query: NewsSavedSearchQuery) -> bool:
        def start(value: Any) -> datetime | None:
            return datetime.combine(value, time.min, tzinfo=UTC) if value else None

        def end(value: Any) -> datetime | None:
            return datetime.combine(value, time.max, tzinfo=UTC) if value else None

        filters = self._news_event_filters(
            entity_id,
            query.q,
            query.event_type,
            query.publisher,
            query.language,
            query.venue,
            start(query.published_from),
            end(query.published_to),
        )
        if query.entity_id:
            # The saved canonical-entity condition constrains in addition to the changed
            # entity relation, so replay keeps the exact saved semantics.
            filters.append(
                or_(
                    NewsEvent.publisher_entity_id == query.entity_id,
                    cast(NewsEvent.related_entity_ids, String).contains(f'"{query.entity_id}"', autoescape=True),
                )
            )
        if query.content_scope == "research":
            filters.append(NewsEvent.event_type.in_(RESEARCH_PUBLICATION_EVENT_TYPES))
        statement = select(NewsEvent.id).where(*filters)
        return self.session.scalar(statement.with_only_columns(literal(True)).limit(1)) is True

    def news_event_detail(self, event_id: str) -> NewsEventSearchItemRead | None:
        items = self._news_event_search_items(
            [
                NewsEvent.tenant_id == self.tenant_id,
                NewsEvent.id == event_id,
                self._published_optional_entity(NewsEvent.publisher_entity_id),
            ],
            1,
            0,
        )
        return items[0] if items else None

    def _news_event_search_items(
        self,
        filters: list[ColumnElement[bool]],
        limit: int,
        offset: int,
        *,
        sort_by: NewsSortField = "published_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[NewsSortField]] | None = None,
    ) -> list[NewsEventSearchItemRead]:
        effective_sort = validate_sort_clauses(
            sort,
            NEWS_SORT_FIELDS,
            default_field=sort_by,
            default_direction=sort_direction,
        )
        publisher_name = (
            select(func.lower(Entity.name))
            .where(Entity.tenant_id == self.tenant_id, Entity.id == NewsEvent.publisher_entity_id)
            .correlate(NewsEvent)
            .scalar_subquery()
        )
        sort_expressions: dict[NewsSortField, Any] = {
            "published_at": NewsEvent.published_at,
            "title": func.lower(NewsEvent.title),
            "event_type": func.lower(NewsEvent.event_type),
            "publisher": publisher_name,
            "venue": func.lower(NewsEvent.venue),
        }
        ordered_sort = _ordered_sort_expressions(effective_sort, sort_expressions)
        rows = self.session.scalars(
            select(NewsEvent)
            .where(*filters)
            .order_by(*ordered_sort, NewsEvent.event_identifier, NewsEvent.id)
            .limit(limit)
            .offset(offset)
        ).all()
        entity_ids = {
            entity_id
            for row in rows
            for entity_id in ([row.publisher_entity_id] if row.publisher_entity_id else []) + row.related_entity_ids
        }
        entities = (
            self.session.scalars(
                select(Entity)
                .where(Entity.tenant_id == self.tenant_id, Entity.id.in_(entity_ids))
                .order_by(Entity.entity_type, Entity.name, Entity.id)
            ).all()
            if entity_ids
            else []
        )
        linked_by_id = {
            entity.id: NewsEventLinkedEntityRead(id=entity.id, name=entity.name, entity_type=entity.entity_type)
            for entity in entities
        }
        return [
            NewsEventSearchItemRead(
                **NewsEventRead.model_validate(row).model_dump(),
                publisher_entity=linked_by_id.get(row.publisher_entity_id or ""),
                related_entities=[
                    linked_by_id[entity_id] for entity_id in row.related_entity_ids if entity_id in linked_by_id
                ],
            )
            for row in rows
        ]

    def _linked_entity_facets(self, source: Any, entity_id_name: str, observation_id_name: str) -> dict[str, int]:
        entity = aliased(Entity)
        entity_id = source.c[entity_id_name]
        observation_id = source.c[observation_id_name]
        counts = self.session.execute(
            select(entity.name, func.count(func.distinct(observation_id)))
            .select_from(source)
            .join(entity, and_(entity.tenant_id == self.tenant_id, entity.id == entity_id))
            .group_by(entity.name)
            .order_by(func.count(func.distinct(observation_id)).desc(), entity.name)
        ).all()
        return {name: count for name, count in counts if name}

    def _target_asset_ids(self, target_entity_id: str) -> Any:
        target_edge = aliased(Relationship)
        relationship_assets = select(target_edge.subject_id.label("asset_entity_id")).where(
            target_edge.tenant_id == self.tenant_id,
            target_edge.predicate == "has_target",
            target_edge.object_id == target_entity_id,
        )
        legacy_program_assets = select(DevelopmentProgram.drug_entity_id.label("asset_entity_id")).where(
            DevelopmentProgram.tenant_id == self.tenant_id,
            DevelopmentProgram.target_entity_id == target_entity_id,
        )
        normalized_program_assets = (
            select(DevelopmentProgram.drug_entity_id.label("asset_entity_id"))
            .join(
                DevelopmentProgramTarget,
                and_(
                    DevelopmentProgramTarget.tenant_id == self.tenant_id,
                    DevelopmentProgramTarget.program_id == DevelopmentProgram.id,
                    DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
                ),
            )
            .where(
                DevelopmentProgram.tenant_id == self.tenant_id,
                DevelopmentProgramTarget.target_entity_id == target_entity_id,
            )
        )
        return union_all(relationship_assets, legacy_program_assets, normalized_program_assets)

    def _relationship_filters(self, entity_id: str) -> list[ColumnElement[bool]]:
        filters = [
            Relationship.tenant_id == self.tenant_id,
            Relationship.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
            or_(Relationship.subject_id == entity_id, Relationship.object_id == entity_id),
        ]
        if not self.include_unpublished:
            filters.extend(
                [
                    self._published_entity_exists(Relationship.subject_id),
                    self._published_entity_exists(Relationship.object_id),
                ]
            )
        return filters

    def _evidence_filters(self, entity_id: str) -> list[ColumnElement[bool]]:
        filters = [
            EvidenceClaim.tenant_id == self.tenant_id,
            EvidenceClaim.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
            or_(EvidenceClaim.subject_id == entity_id, EvidenceClaim.object_id == entity_id),
        ]
        if not self.include_unpublished:
            filters.extend(
                [
                    self._published_entity_exists(EvidenceClaim.subject_id),
                    self._published_optional_entity(EvidenceClaim.object_id),
                ]
            )
        return filters

    def _activity_filters(self, entity_id: str) -> list[ColumnElement[bool]]:
        filters = [
            ActivityMeasurement.tenant_id == self.tenant_id,
            or_(
                ActivityMeasurement.compound_entity_id == entity_id,
                ActivityMeasurement.target_entity_id == entity_id,
            ),
        ]
        if not self.include_unpublished:
            filters.extend(
                [
                    self._published_entity_exists(ActivityMeasurement.compound_entity_id),
                    self._published_entity_exists(ActivityMeasurement.target_entity_id),
                ]
            )
        return filters

    def _program_filters(self, entity_id: str) -> list[ColumnElement[bool]]:
        filters = [
            DevelopmentProgram.tenant_id == self.tenant_id,
            self._unique_program_record(),
            or_(
                DevelopmentProgram.drug_entity_id.in_(self._entity_identity_ids(entity_id, EntityType.DRUG)),
                DevelopmentProgram.target_entity_id.in_(self._entity_identity_ids(entity_id, EntityType.TARGET)),
                self._program_target_exists(entity_id),
                DevelopmentProgram.disease_entity_id.in_(self._entity_identity_ids(entity_id, EntityType.DISEASE)),
                DevelopmentProgram.organization_entity_id.in_(
                    self._entity_identity_ids(entity_id, EntityType.ORGANIZATION)
                ),
                self._program_organization_exists(entity_id),
            ),
        ]
        if not self.include_unpublished:
            filters.extend(
                [
                    self._published_identity_exists(
                        DevelopmentProgram.drug_entity_id,
                        EntityType.DRUG,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.target_entity_id,
                        EntityType.TARGET,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.disease_entity_id,
                        EntityType.DISEASE,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                    self._published_optional_identity_entity(
                        DevelopmentProgram.organization_entity_id,
                        EntityType.ORGANIZATION,
                        correlate_from=DevelopmentProgram.__table__,
                    ),
                ]
            )
        return filters

    def _structure_filters(self, entity_id: str | None, inchi_key: str | None) -> list[ColumnElement[bool]]:
        filters = [CompoundStructure.tenant_id == self.tenant_id]
        if not self.include_unpublished:
            filters.append(self._published_entity_exists(CompoundStructure.entity_id))
        if entity_id:
            filters.append(CompoundStructure.entity_id == entity_id)
        if inchi_key:
            filters.append(CompoundStructure.standard_inchi_key == inchi_key.upper())
        return filters

    def _target_evidence_filters(
        self,
        entity_id: str,
        *,
        evidence_type: str | None = None,
        direction: str | None = None,
        disease_entity_id: str | None = None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [
            TargetEvidenceObservation.tenant_id == self.tenant_id,
            or_(
                TargetEvidenceObservation.target_entity_id == entity_id,
                TargetEvidenceObservation.disease_entity_id == entity_id,
            ),
        ]
        if not self.include_unpublished:
            filters.extend(
                [
                    self._published_entity_exists(TargetEvidenceObservation.target_entity_id),
                    self._published_optional_entity(TargetEvidenceObservation.disease_entity_id),
                ]
            )
        if evidence_type is not None:
            filters.append(TargetEvidenceObservation.evidence_type == evidence_type)
        if direction is not None:
            filters.append(TargetEvidenceObservation.direction == direction)
        if disease_entity_id is not None:
            filters.append(TargetEvidenceObservation.disease_entity_id == disease_entity_id)
        return filters

    def _clinical_trial_filters(
        self,
        entity_id: str | None,
        query: str | None,
        *,
        registry: str | None = None,
        overall_status: str | None = None,
        phase: str | None = None,
        study_type: str | None = None,
        acronym: str | None = None,
        initiation_type: str | None = None,
        therapy_line: str | None = None,
        has_results: bool | None = None,
        results_posted_from: datetime | None = None,
        results_posted_to: datetime | None = None,
        result_evaluation: str | None = None,
        investigational_drug: str | None = None,
        combination_drug: str | None = None,
        investigational_target: str | None = None,
        combination_target: str | None = None,
        investigational_drug_entity_ids: list[str] | None = None,
        combination_drug_entity_ids: list[str] | None = None,
        investigational_target_entity_ids: list[str] | None = None,
        combination_target_entity_ids: list[str] | None = None,
        linked_drug_modality: list[str] | None = None,
        linked_drug_innovation_type: list[str] | None = None,
        linked_drug_category: list[str] | None = None,
        linked_drug_program_tag: list[str] | None = None,
        linked_drug_global_phase: str | None = None,
        linked_drug_organization_country_region: str | None = None,
        role_entity_id: str | None = None,
        role_entity_ids: list[str] | None = None,
        role_entity_role: str | None = None,
        has_key_result: bool | None = None,
        publication_id: str | None = None,
        conference: str | None = None,
        disclosed_from: datetime | None = None,
        disclosed_to: datetime | None = None,
    ) -> list[ColumnElement[bool]]:
        filters = [
            ClinicalTrialProfile.tenant_id == self.tenant_id,
            self._published_entity_exists(ClinicalTrialProfile.entity_id),
        ]
        if entity_id:
            linked_trial_ids = select(Relationship.subject_id).where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.predicate == "trial_links_entity",
                Relationship.object_id == entity_id,
            )
            role_linked_trial_ids = select(ClinicalTrialEntityRole.trial_id).where(
                ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                ClinicalTrialEntityRole.entity_id == entity_id,
            )
            entity_type = self.session.scalar(
                select(Entity.entity_type).where(
                    Entity.tenant_id == self.tenant_id,
                    Entity.id == entity_id,
                )
            )
            entity_matches: list[ColumnElement[bool]] = [
                ClinicalTrialProfile.entity_id == entity_id,
                ClinicalTrialProfile.entity_id.in_(linked_trial_ids),
                ClinicalTrialProfile.id.in_(role_linked_trial_ids),
            ]
            if entity_type == EntityType.TARGET:
                entity_matches.append(self._clinical_trial_target_program_exists(entity_id))
            filters.append(or_(*entity_matches))
        if query and (normalized_query := query.strip().casefold()):
            linked_entity_match = (
                select(Relationship.id)
                .join(
                    Entity,
                    and_(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id == Relationship.object_id,
                    ),
                )
                .where(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.predicate == "trial_links_entity",
                    Relationship.subject_id == ClinicalTrialProfile.entity_id,
                    Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                    func.lower(Entity.name).contains(normalized_query, autoescape=True),
                )
                .exists()
            )
            filters.append(
                or_(
                    func.lower(ClinicalTrialProfile.official_title).contains(normalized_query, autoescape=True),
                    func.lower(ClinicalTrialProfile.acronym).contains(normalized_query, autoescape=True),
                    func.lower(ClinicalTrialProfile.registry_id).contains(normalized_query, autoescape=True),
                    func.lower(cast(ClinicalTrialProfile.conditions, String)).contains(
                        normalized_query, autoescape=True
                    ),
                    func.lower(cast(ClinicalTrialProfile.interventions, String)).contains(
                        normalized_query, autoescape=True
                    ),
                    func.lower(cast(ClinicalTrialProfile.sponsors, String)).contains(normalized_query, autoescape=True),
                    linked_entity_match,
                )
            )
        if registry:
            filters.append(ClinicalTrialProfile.registry_name == registry)
        if overall_status:
            filters.append(ClinicalTrialProfile.overall_status == overall_status)
        if phase:
            filters.append(cast(ClinicalTrialProfile.phases, String).contains(f'"{phase}"', autoescape=True))
        if study_type:
            filters.append(ClinicalTrialProfile.study_type == study_type)
        if acronym and (normalized_acronym := acronym.strip().casefold()):
            filters.append(func.lower(ClinicalTrialProfile.acronym).contains(normalized_acronym, autoescape=True))
        if initiation_type:
            filters.append(ClinicalTrialProfile.initiation_type == initiation_type)
        if therapy_line:
            filters.append(self._json_array_value_exists(ClinicalTrialProfile.therapy_lines, therapy_line))
        if has_results is not None:
            filters.append(ClinicalTrialProfile.has_results.is_(has_results))
        if result_evaluation:
            filters.append(ClinicalTrialProfile.result_evaluation == result_evaluation)
        if results_posted_from:
            filters.append(ClinicalTrialProfile.results_first_posted >= results_posted_from)
        if results_posted_to:
            filters.append(ClinicalTrialProfile.results_first_posted <= results_posted_to)
        for role, name in (
            ("investigational_drug", investigational_drug),
            ("combination_drug", combination_drug),
            ("investigational_target", investigational_target),
            ("combination_target", combination_target),
        ):
            if name and (normalized_name := name.strip().casefold()):
                filters.append(self._clinical_trial_role_name_exists(role, normalized_name))
        for role, entity_ids in (
            ("investigational_drug", investigational_drug_entity_ids),
            ("combination_drug", combination_drug_entity_ids),
            ("investigational_target", investigational_target_entity_ids),
            ("combination_target", combination_target_entity_ids),
        ):
            if entity_ids:
                filters.append(self._clinical_trial_role_entities_exist(entity_ids, role))
        if any(
            (
                linked_drug_modality,
                linked_drug_innovation_type,
                linked_drug_category,
                linked_drug_program_tag,
                linked_drug_global_phase,
                linked_drug_organization_country_region,
            )
        ):
            filters.append(
                self._clinical_trial_linked_drug_program_exists(
                    modalities=linked_drug_modality,
                    innovation_types=linked_drug_innovation_type,
                    drug_categories=linked_drug_category,
                    program_tags=linked_drug_program_tag,
                    global_phase=linked_drug_global_phase,
                    organization_country_region=linked_drug_organization_country_region,
                )
            )
        if role_entity_id and role_entity_ids:
            raise ValueError("role_entity_id cannot be combined with role_entity_ids")
        if role_entity_role and not role_entity_id and not role_entity_ids:
            raise ValueError("role_entity_role requires role_entity_id or role_entity_ids")
        if role_entity_id:
            filters.append(self._clinical_trial_role_entity_exists(role_entity_id, role_entity_role))
        if role_entity_ids:
            filters.append(self._clinical_trial_role_entities_exist(role_entity_ids, role_entity_role))
        disclosure_conditions: list[ColumnElement[bool]] = []
        if publication_id and (normalized_publication_id := publication_id.strip().casefold()):
            disclosure_conditions.append(
                func.lower(ClinicalTrialResultDisclosure.external_id) == normalized_publication_id
            )
        if conference and (normalized_conference := conference.strip().casefold()):
            disclosure_conditions.append(
                func.lower(ClinicalTrialResultDisclosure.conference_name).contains(
                    normalized_conference,
                    autoescape=True,
                )
            )
        if disclosed_from:
            disclosure_conditions.append(ClinicalTrialResultDisclosure.disclosed_at >= disclosed_from)
        if disclosed_to:
            disclosure_conditions.append(ClinicalTrialResultDisclosure.disclosed_at <= disclosed_to)
        if disclosure_conditions:
            filters.append(self._clinical_trial_disclosure_exists(*disclosure_conditions))
        if has_key_result is not None:
            key_result_exists = self._clinical_trial_disclosure_exists(
                ClinicalTrialResultDisclosure.is_key_result.is_(True)
            )
            filters.append(key_result_exists if has_key_result else ~key_result_exists)
        return filters

    def _clinical_trial_role_name_exists(self, role: str, normalized_name: str) -> ColumnElement[bool]:
        return (
            select(ClinicalTrialEntityRole.id)
            .join(
                Entity,
                and_(
                    Entity.tenant_id == self.tenant_id,
                    Entity.id == ClinicalTrialEntityRole.entity_id,
                ),
            )
            .where(
                ClinicalTrialEntityRole.tenant_id == self.tenant_id,
                ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
                ClinicalTrialEntityRole.role == role,
                Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                func.lower(Entity.name).contains(normalized_name, autoescape=True),
            )
            .exists()
        )

    def _clinical_trial_linked_drug_program_exists(
        self,
        *,
        modalities: list[str] | None,
        innovation_types: list[str] | None,
        drug_categories: list[str] | None,
        program_tags: list[str] | None,
        global_phase: str | None,
        organization_country_region: str | None,
    ) -> ColumnElement[bool]:
        program_conditions: list[ColumnElement[bool]] = [
            DevelopmentProgram.tenant_id == self.tenant_id,
            ClinicalTrialEntityRole.tenant_id == self.tenant_id,
            ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
            ClinicalTrialEntityRole.role.in_(("investigational_drug", "combination_drug")),
            ClinicalTrialEntityRole.entity_id == DevelopmentProgram.drug_entity_id,
        ]
        if not self.include_unpublished:
            program_conditions.append(self._published_entity_exists(DevelopmentProgram.drug_entity_id))
        public_modality = _public_program_modality_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        public_drug_category = _public_program_drug_category_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        if modalities:
            program_conditions.append(public_modality.in_(modalities))
        if innovation_types:
            program_conditions.append(DevelopmentProgram.innovation_type.in_(innovation_types))
        if drug_categories:
            program_conditions.append(public_drug_category.in_(drug_categories))
        if program_tags:
            visible_program_tags = public_program_tags(program_tags)
            program_conditions.append(
                or_(
                    *(
                        self._json_array_value_exists(DevelopmentProgram.program_tags, tag)
                        for tag in visible_program_tags
                    )
                )
                if visible_program_tags
                else literal(False)
            )
        if global_phase:
            program_conditions.append(DevelopmentProgram.global_phase == global_phase)
        if organization_country_region:
            program_conditions.append(
                select(DevelopmentProgramOrganization.id)
                .where(
                    DevelopmentProgramOrganization.tenant_id == self.tenant_id,
                    DevelopmentProgramOrganization.program_id == DevelopmentProgram.id,
                    DevelopmentProgramOrganization.organization_set_version
                    == DevelopmentProgram.organization_set_version,
                    DevelopmentProgramOrganization.country_region == organization_country_region,
                    self._published_entity_exists(DevelopmentProgramOrganization.organization_entity_id),
                )
                .exists()
            )
        return (
            select(DevelopmentProgram.id)
            .join(
                ClinicalTrialEntityRole,
                ClinicalTrialEntityRole.entity_id == DevelopmentProgram.drug_entity_id,
            )
            .where(*program_conditions)
            .exists()
        )

    def _clinical_trial_role_entity_exists(self, entity_id: str, role: str | None) -> ColumnElement[bool]:
        conditions: list[ColumnElement[bool]] = [
            ClinicalTrialEntityRole.tenant_id == self.tenant_id,
            ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
            ClinicalTrialEntityRole.entity_id == entity_id,
        ]
        if not self.include_unpublished:
            conditions.append(self._published_entity_exists(ClinicalTrialEntityRole.entity_id))
        if role:
            conditions.append(ClinicalTrialEntityRole.role == role)
        return select(ClinicalTrialEntityRole.id).where(*conditions).exists()

    def _clinical_trial_role_entities_exist(self, entity_ids: list[str], role: str | None) -> ColumnElement[bool]:
        conditions: list[ColumnElement[bool]] = [
            ClinicalTrialEntityRole.tenant_id == self.tenant_id,
            ClinicalTrialEntityRole.trial_id == ClinicalTrialProfile.id,
            ClinicalTrialEntityRole.entity_id.in_(entity_ids),
        ]
        if not self.include_unpublished:
            conditions.append(self._published_entity_exists(ClinicalTrialEntityRole.entity_id))
        if role:
            conditions.append(ClinicalTrialEntityRole.role == role)
        return select(ClinicalTrialEntityRole.id).where(*conditions).exists()

    def _clinical_trial_disclosure_exists(
        self,
        *conditions: ColumnElement[bool],
    ) -> ColumnElement[bool]:
        return (
            select(ClinicalTrialResultDisclosure.id)
            .where(
                ClinicalTrialResultDisclosure.tenant_id == self.tenant_id,
                ClinicalTrialResultDisclosure.trial_id == ClinicalTrialProfile.id,
                *conditions,
            )
            .exists()
        )

    def _patent_filters(
        self,
        entity_id: str | None,
        query: str | None,
        *,
        applicant: str | None = None,
        legal_status: str | None = None,
        priority_from: datetime | None = None,
        priority_to: datetime | None = None,
        expiration_from: datetime | None = None,
        expiration_to: datetime | None = None,
    ) -> list[ColumnElement[bool]]:
        filters = [
            PatentFamily.tenant_id == self.tenant_id,
            self._published_entity_exists(PatentFamily.entity_id),
        ]
        if entity_id:
            linked_patent_ids = select(Relationship.subject_id).where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.predicate == "patent_links_entity",
                Relationship.object_id == entity_id,
            )
            filters.append(
                or_(
                    PatentFamily.entity_id == entity_id,
                    PatentFamily.entity_id.in_(linked_patent_ids),
                    cast(PatentFamily.linked_entity_ids, String).contains(f'"{entity_id}"', autoescape=True),
                )
            )
        if query and (normalized_query := query.strip().casefold()):
            linked_entity_match = (
                select(Relationship.id)
                .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == Relationship.object_id))
                .where(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.predicate == "patent_links_entity",
                    Relationship.subject_id == PatentFamily.entity_id,
                    Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                    func.lower(Entity.name).contains(normalized_query, autoescape=True),
                )
                .exists()
            )
            filters.append(
                or_(
                    func.lower(PatentFamily.title).contains(normalized_query, autoescape=True),
                    func.lower(PatentFamily.family_identifier).contains(normalized_query, autoescape=True),
                    func.lower(cast(PatentFamily.applicants, String)).contains(normalized_query, autoescape=True),
                    func.lower(cast(PatentFamily.inventors, String)).contains(normalized_query, autoescape=True),
                    func.lower(cast(PatentFamily.publications, String)).contains(normalized_query, autoescape=True),
                    linked_entity_match,
                )
            )
        if applicant:
            filters.append(cast(PatentFamily.applicants, String).contains(f'"{applicant}"', autoescape=True))
        if legal_status:
            filters.append(PatentFamily.legal_status == legal_status)
        if priority_from:
            filters.append(PatentFamily.priority_date >= priority_from)
        if priority_to:
            filters.append(PatentFamily.priority_date <= priority_to)
        if expiration_from:
            filters.append(PatentFamily.expiration_date >= expiration_from)
        if expiration_to:
            filters.append(PatentFamily.expiration_date <= expiration_to)
        return filters

    def _deal_party_facets(self, source: Any) -> dict[str, int]:
        relationship_parties = (
            select(source.c.deal_id.label("deal_id"), Entity.name.label("party_name"))
            .select_from(source)
            .join(
                Relationship,
                and_(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.subject_id == source.c.deal_entity_id,
                    Relationship.predicate == "deal_party",
                ),
            )
            .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == Relationship.object_id))
        )
        structured_parties = (
            select(source.c.deal_id.label("deal_id"), Entity.name.label("party_name"))
            .select_from(source)
            .join(
                DealPartyAssociation,
                and_(
                    DealPartyAssociation.tenant_id == self.tenant_id,
                    DealPartyAssociation.deal_id == source.c.deal_id,
                ),
            )
            .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == DealPartyAssociation.party_entity_id))
        )
        party_rows = relationship_parties.union(structured_parties).subquery()
        counts = self.session.execute(
            select(party_rows.c.party_name, func.count(func.distinct(party_rows.c.deal_id)))
            .group_by(party_rows.c.party_name)
            .order_by(func.count(func.distinct(party_rows.c.deal_id)).desc(), party_rows.c.party_name)
        ).all()
        return {str(name): int(count) for name, count in counts if name}

    def _deal_asset_links(self, source: Any) -> Any:
        structured_assets = (
            select(source.c.deal_id.label("deal_id"), DealAssetAssociation.asset_entity_id.label("asset_entity_id"))
            .select_from(source)
            .join(
                DealAssetAssociation,
                and_(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == source.c.deal_id,
                ),
            )
        )
        relationship_assets = (
            select(source.c.deal_id.label("deal_id"), Relationship.object_id.label("asset_entity_id"))
            .select_from(source)
            .join(
                Relationship,
                and_(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.subject_id == source.c.deal_entity_id,
                    Relationship.predicate == "deal_asset",
                ),
            )
        )
        return structured_assets.union(relationship_assets).subquery()

    def _deal_asset_facets(self, source: Any) -> dict[str, int]:
        asset_links = self._deal_asset_links(source)
        counts = self.session.execute(
            select(Entity.name, func.count(func.distinct(asset_links.c.deal_id)))
            .select_from(asset_links)
            .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == asset_links.c.asset_entity_id))
            .group_by(Entity.name)
            .order_by(func.count(func.distinct(asset_links.c.deal_id)).desc(), Entity.name)
        ).all()
        return {str(name): int(count) for name, count in counts if name}

    def _deal_program_entity_facets(self, source: Any, kind: Literal["target", "disease"]) -> dict[str, int]:
        asset_links = self._deal_asset_links(source)
        if kind == "disease":
            program_entities = union_all(
                select(
                    DevelopmentProgram.drug_entity_id.label("asset_entity_id"),
                    DevelopmentProgram.disease_entity_id.label("entity_id"),
                ).where(
                    DevelopmentProgram.tenant_id == self.tenant_id,
                    DevelopmentProgram.disease_entity_id.is_not(None),
                )
            )
        else:
            relationship_targets = select(
                Relationship.subject_id.label("asset_entity_id"),
                Relationship.object_id.label("entity_id"),
            ).where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.predicate == "has_target",
            )
            legacy_targets = select(
                DevelopmentProgram.drug_entity_id.label("asset_entity_id"),
                DevelopmentProgram.target_entity_id.label("entity_id"),
            ).where(
                DevelopmentProgram.tenant_id == self.tenant_id,
                DevelopmentProgram.target_entity_id.is_not(None),
            )
            normalized_targets = (
                select(
                    DevelopmentProgram.drug_entity_id.label("asset_entity_id"),
                    DevelopmentProgramTarget.target_entity_id.label("entity_id"),
                )
                .join(
                    DevelopmentProgramTarget,
                    and_(
                        DevelopmentProgramTarget.tenant_id == self.tenant_id,
                        DevelopmentProgramTarget.program_id == DevelopmentProgram.id,
                        DevelopmentProgramTarget.target_set_version == DevelopmentProgram.target_set_version,
                    ),
                )
                .where(DevelopmentProgram.tenant_id == self.tenant_id)
            )
            program_entities = union_all(relationship_targets, legacy_targets, normalized_targets)
        entity_links = program_entities.subquery()
        counts = self.session.execute(
            select(Entity.name, func.count(func.distinct(asset_links.c.deal_id)))
            .select_from(asset_links)
            .join(entity_links, entity_links.c.asset_entity_id == asset_links.c.asset_entity_id)
            .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == entity_links.c.entity_id))
            .group_by(Entity.name)
            .order_by(func.count(func.distinct(asset_links.c.deal_id)).desc(), Entity.name)
        ).all()
        return {str(name): int(count) for name, count in counts if name}

    def _deal_program_attribute_facets(
        self,
        source: Any,
        field: Literal["modality", "program_tags"],
    ) -> dict[str, int]:
        asset_links = self._deal_asset_links(source)
        public_modality = _public_program_modality_sql(
            DevelopmentProgram.modality,
            DevelopmentProgram.drug_category,
        )
        program_rows = (
            select(
                asset_links.c.deal_id.label("deal_id"),
                public_modality.label("modality"),
                DevelopmentProgram.program_tags.label("program_tags"),
            )
            .select_from(asset_links)
            .join(
                DevelopmentProgram,
                and_(
                    DevelopmentProgram.tenant_id == self.tenant_id,
                    DevelopmentProgram.drug_entity_id == asset_links.c.asset_entity_id,
                ),
            )
            .subquery()
        )
        if field == "program_tags":
            return self._json_array_facets(
                program_rows,
                "program_tags",
                "deal_id",
                public_program_tags_only=True,
            )
        counts = self.session.execute(
            select(program_rows.c.modality, func.count(func.distinct(program_rows.c.deal_id)))
            .where(program_rows.c.modality.is_not(None))
            .group_by(program_rows.c.modality)
            .order_by(func.count(func.distinct(program_rows.c.deal_id)).desc(), program_rows.c.modality)
        ).all()
        return {str(modality): int(count) for modality, count in counts if modality}

    def _deal_party_role_facets(self, source: Any) -> dict[str, int]:
        counts = self.session.execute(
            select(DealPartyAssociation.role, func.count(func.distinct(source.c.deal_id)))
            .select_from(source)
            .join(
                DealPartyAssociation,
                and_(
                    DealPartyAssociation.tenant_id == self.tenant_id,
                    DealPartyAssociation.deal_id == source.c.deal_id,
                ),
            )
            .group_by(DealPartyAssociation.role)
            .order_by(func.count(func.distinct(source.c.deal_id)).desc(), DealPartyAssociation.role)
        ).all()
        return {str(role): int(count) for role, count in counts if role}

    def _deal_party_attribute_facets(
        self,
        source: Any,
        field: Literal["country_region", "organization_type"],
    ) -> dict[str, int]:
        column = getattr(DealPartyAssociation, field)
        counts = self.session.execute(
            select(column, func.count(func.distinct(source.c.deal_id)))
            .select_from(source)
            .join(
                DealPartyAssociation,
                and_(
                    DealPartyAssociation.tenant_id == self.tenant_id,
                    DealPartyAssociation.deal_id == source.c.deal_id,
                ),
            )
            .where(column.is_not(None))
            .group_by(column)
            .order_by(func.count(func.distinct(source.c.deal_id)).desc(), column)
        ).all()
        return {str(value): int(count) for value, count in counts if value}

    def _current_program_phase_projection(self) -> Any:
        phase_rank = case(
            *[
                (DevelopmentProgram.phase == DevelopmentPhase(phase), rank)
                for phase, rank in _DEVELOPMENT_PHASE_RANK.items()
            ],
            else_=-2,
        )
        ranked = (
            select(
                DevelopmentProgram.drug_entity_id.label("drug_entity_id"),
                DevelopmentProgram.phase.label("phase"),
                DevelopmentProgram.status_date.label("status_date"),
                func.row_number()
                .over(
                    partition_by=DevelopmentProgram.drug_entity_id,
                    order_by=(
                        phase_rank.desc(),
                        DevelopmentProgram.status_date.desc().nullslast(),
                        DevelopmentProgram.id,
                    ),
                )
                .label("phase_rank_row"),
            )
            .where(DevelopmentProgram.tenant_id == self.tenant_id)
            .subquery()
        )
        return (
            select(
                ranked.c.drug_entity_id,
                ranked.c.phase,
                ranked.c.status_date,
            )
            .where(ranked.c.phase_rank_row == 1)
            .subquery()
        )

    def _deal_asset_phase_facets(self, source: Any) -> dict[str, int]:
        counts = self.session.execute(
            select(
                DealAssetAssociation.development_phase_at_transaction,
                func.count(func.distinct(source.c.deal_id)),
            )
            .select_from(source)
            .join(
                DealAssetAssociation,
                and_(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == source.c.deal_id,
                ),
            )
            .where(DealAssetAssociation.development_phase_at_transaction.is_not(None))
            .group_by(DealAssetAssociation.development_phase_at_transaction)
            .order_by(
                func.count(func.distinct(source.c.deal_id)).desc(),
                DealAssetAssociation.development_phase_at_transaction,
            )
        ).all()
        return {str(phase): int(count) for phase, count in counts if phase}

    def _deal_current_phase_facets(self, source: Any) -> dict[str, int]:
        current_programs = self._current_program_phase_projection()
        counts = self.session.execute(
            select(current_programs.c.phase, func.count(func.distinct(source.c.deal_id)))
            .select_from(source)
            .join(
                DealAssetAssociation,
                and_(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == source.c.deal_id,
                ),
            )
            .join(
                current_programs,
                current_programs.c.drug_entity_id == DealAssetAssociation.asset_entity_id,
            )
            .group_by(current_programs.c.phase)
            .order_by(func.count(func.distinct(source.c.deal_id)).desc(), current_programs.c.phase)
        ).all()
        return {phase.value if hasattr(phase, "value") else str(phase): int(count) for phase, count in counts if phase}

    def _deal_right_facets(self, source: Any, field: Literal["right_type", "territory"]) -> dict[str, int]:
        column = getattr(DealRight, field)
        counts = self.session.execute(
            select(column, func.count(func.distinct(source.c.deal_id)))
            .select_from(source)
            .join(
                DealRight,
                and_(DealRight.tenant_id == self.tenant_id, DealRight.deal_id == source.c.deal_id),
            )
            .group_by(column)
            .order_by(func.count(func.distinct(source.c.deal_id)).desc(), column)
        ).all()
        return {str(value): int(count) for value, count in counts if value}

    def _deal_filters(
        self,
        entity_id: str | None,
        query: str | None = None,
        deal_type: str | None = None,
        territory: str | None = None,
        party: str | None = None,
        *,
        status: str | None = None,
        direction: str | None = None,
        direction_reference_jurisdiction: str | None = None,
        asset_entity_id: str | None = None,
        target_entity_id: str | None = None,
        disease_entity_id: str | None = None,
        asset_modality: list[str] | None = None,
        asset_program_tag: list[str] | None = None,
        party_entity_id: str | None = None,
        party_role: str | None = None,
        party_country_region: str | None = None,
        party_organization_type: str | None = None,
        development_phase_at_transaction: str | None = None,
        current_development_phase: str | None = None,
        right_type: str | None = None,
        rights_territory: str | None = None,
        currency: str | None = None,
        announced_from: datetime | None = None,
        announced_to: datetime | None = None,
        terminated_from: datetime | None = None,
        terminated_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        upfront_amount_min: float | None = None,
        upfront_amount_max: float | None = None,
        total_potential_amount_min: float | None = None,
        total_potential_amount_max: float | None = None,
    ) -> list[ColumnElement[bool]]:
        filters = [
            DealProfile.tenant_id == self.tenant_id,
            self._published_entity_exists(DealProfile.entity_id),
        ]
        if not self.include_unpublished:
            unpublished_asset = (
                select(literal(1))
                .select_from(DealAssetAssociation)
                .join(Entity, Entity.id == DealAssetAssociation.asset_entity_id)
                .where(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == DealProfile.id,
                    Entity.review_status != ReviewStatus.VERIFIED,
                )
                .correlate(DealProfile)
                .exists()
            )
            unpublished_party = (
                select(literal(1))
                .select_from(DealPartyAssociation)
                .join(Entity, Entity.id == DealPartyAssociation.party_entity_id)
                .where(
                    DealPartyAssociation.tenant_id == self.tenant_id,
                    DealPartyAssociation.deal_id == DealProfile.id,
                    Entity.review_status != ReviewStatus.VERIFIED,
                )
                .correlate(DealProfile)
                .exists()
            )
            unpublished_right = (
                select(literal(1))
                .select_from(DealRight)
                .join(Entity, Entity.id == DealRight.holder_entity_id)
                .where(
                    DealRight.tenant_id == self.tenant_id,
                    DealRight.deal_id == DealProfile.id,
                    Entity.review_status != ReviewStatus.VERIFIED,
                )
                .correlate(DealProfile)
                .exists()
            )
            filters.extend([~unpublished_asset, ~unpublished_party, ~unpublished_right])
        if entity_id:
            target_asset_ids = self._target_asset_ids(entity_id)
            disease_asset_ids = select(DevelopmentProgram.drug_entity_id).where(
                DevelopmentProgram.tenant_id == self.tenant_id,
                DevelopmentProgram.disease_entity_id == entity_id,
            )
            linked_deal_ids = select(Relationship.subject_id).where(
                Relationship.tenant_id == self.tenant_id,
                or_(
                    and_(
                        Relationship.predicate.in_(["deal_asset", "deal_party"]),
                        Relationship.object_id == entity_id,
                    ),
                    and_(
                        Relationship.predicate == "deal_asset",
                        or_(
                            Relationship.object_id.in_(target_asset_ids),
                            Relationship.object_id.in_(disease_asset_ids),
                        ),
                    ),
                ),
            )
            normalized_party_deal_ids = (
                select(DealProfile.entity_id)
                .join(
                    DealPartyAssociation,
                    and_(
                        DealPartyAssociation.tenant_id == self.tenant_id,
                        DealPartyAssociation.deal_id == DealProfile.id,
                        DealPartyAssociation.party_entity_id == entity_id,
                    ),
                )
                .where(DealProfile.tenant_id == self.tenant_id)
            )
            normalized_asset_deal_ids = (
                select(DealProfile.entity_id)
                .join(
                    DealAssetAssociation,
                    and_(
                        DealAssetAssociation.tenant_id == self.tenant_id,
                        DealAssetAssociation.deal_id == DealProfile.id,
                        or_(
                            DealAssetAssociation.asset_entity_id == entity_id,
                            DealAssetAssociation.asset_entity_id.in_(target_asset_ids),
                            DealAssetAssociation.asset_entity_id.in_(disease_asset_ids),
                        ),
                    ),
                )
                .where(DealProfile.tenant_id == self.tenant_id)
            )
            filters.append(
                or_(
                    DealProfile.entity_id == entity_id,
                    DealProfile.entity_id.in_(linked_deal_ids),
                    DealProfile.entity_id.in_(normalized_party_deal_ids),
                    DealProfile.entity_id.in_(normalized_asset_deal_ids),
                    cast(DealProfile.asset_entity_ids, String).contains(f'"{entity_id}"', autoescape=True),
                )
            )
        if query:
            normalized_query = query.strip().casefold()
            linked_entity_match = (
                select(Relationship.id)
                .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == Relationship.object_id))
                .where(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.subject_id == DealProfile.entity_id,
                    Relationship.predicate.in_(["deal_party", "deal_asset"]),
                    Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                    func.lower(Entity.name).contains(normalized_query, autoescape=True),
                )
                .exists()
            )
            normalized_party_name_match = (
                select(DealPartyAssociation.id)
                .join(
                    Entity,
                    and_(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id == DealPartyAssociation.party_entity_id,
                        Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                    ),
                )
                .where(
                    DealPartyAssociation.tenant_id == self.tenant_id,
                    DealPartyAssociation.deal_id == DealProfile.id,
                    func.lower(Entity.name).contains(normalized_query, autoescape=True),
                )
                .exists()
            )
            normalized_asset_name_match = (
                select(DealAssetAssociation.id)
                .join(
                    Entity,
                    and_(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id == DealAssetAssociation.asset_entity_id,
                        Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                    ),
                )
                .where(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == DealProfile.id,
                    func.lower(Entity.name).contains(normalized_query, autoescape=True),
                )
                .exists()
            )
            deal_name_match = (
                select(Entity.id)
                .where(
                    Entity.tenant_id == self.tenant_id,
                    Entity.id == DealProfile.entity_id,
                    Entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                    func.lower(Entity.name).contains(normalized_query, autoescape=True),
                )
                .exists()
            )
            filters.append(
                or_(
                    func.lower(DealProfile.deal_type).contains(normalized_query, autoescape=True),
                    func.lower(DealProfile.territory).contains(normalized_query, autoescape=True),
                    func.lower(DealProfile.currency).contains(normalized_query, autoescape=True),
                    func.lower(cast(DealProfile.parties, String)).contains(normalized_query, autoescape=True),
                    deal_name_match,
                    linked_entity_match,
                    normalized_party_name_match,
                    normalized_asset_name_match,
                )
            )
        if deal_type:
            filters.append(DealProfile.deal_type == deal_type)
        if status:
            filters.append(DealProfile.status == status)
        if direction:
            filters.append(DealProfile.direction == direction)
        if direction_reference_jurisdiction:
            filters.append(DealProfile.direction_reference_jurisdiction == direction_reference_jurisdiction)
        if territory:
            filters.append(DealProfile.territory == territory)
        normalized_target_asset_ids = self._target_asset_ids(target_entity_id) if target_entity_id else None
        normalized_disease_asset_ids = (
            select(DevelopmentProgram.drug_entity_id).where(
                DevelopmentProgram.tenant_id == self.tenant_id,
                DevelopmentProgram.disease_entity_id == disease_entity_id,
            )
            if disease_entity_id
            else None
        )
        normalized_asset_constraints: list[ColumnElement[bool]] = []
        if asset_entity_id:
            normalized_asset_constraints.append(DealAssetAssociation.asset_entity_id == asset_entity_id)
        if normalized_target_asset_ids is not None:
            normalized_asset_constraints.append(DealAssetAssociation.asset_entity_id.in_(normalized_target_asset_ids))
        if normalized_disease_asset_ids is not None:
            normalized_asset_constraints.append(DealAssetAssociation.asset_entity_id.in_(normalized_disease_asset_ids))
        if asset_entity_id:
            structured_asset_match = select(DealAssetAssociation.id).where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                DealAssetAssociation.asset_entity_id == asset_entity_id,
            )
            relationship_asset_match = select(Relationship.id).where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.subject_id == DealProfile.entity_id,
                Relationship.predicate == "deal_asset",
                Relationship.object_id == asset_entity_id,
            )
            filters.append(
                or_(
                    structured_asset_match.exists(),
                    relationship_asset_match.exists(),
                    cast(DealProfile.asset_entity_ids, String).contains(f'"{asset_entity_id}"', autoescape=True),
                )
            )
        if target_entity_id:
            assert normalized_target_asset_ids is not None
            structured_target_match = select(DealAssetAssociation.id).where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                *normalized_asset_constraints,
            )
            relationship_target_match = select(Relationship.id).where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.subject_id == DealProfile.entity_id,
                Relationship.predicate == "deal_asset",
                Relationship.object_id.in_(normalized_target_asset_ids),
            )
            filters.append(
                structured_target_match.exists()
                if asset_entity_id or disease_entity_id
                else or_(structured_target_match.exists(), relationship_target_match.exists())
            )
        if disease_entity_id:
            assert normalized_disease_asset_ids is not None
            structured_disease_match = select(DealAssetAssociation.id).where(
                DealAssetAssociation.tenant_id == self.tenant_id,
                DealAssetAssociation.deal_id == DealProfile.id,
                *normalized_asset_constraints,
            )
            relationship_disease_match = select(Relationship.id).where(
                Relationship.tenant_id == self.tenant_id,
                Relationship.subject_id == DealProfile.entity_id,
                Relationship.predicate == "deal_asset",
                Relationship.object_id.in_(normalized_disease_asset_ids),
            )
            filters.append(
                structured_disease_match.exists()
                if asset_entity_id or target_entity_id
                else or_(structured_disease_match.exists(), relationship_disease_match.exists())
            )
        if asset_modality or asset_program_tag:
            program_filters: list[ColumnElement[bool]] = []
            if asset_modality:
                program_filters.append(
                    _public_program_modality_sql(
                        DevelopmentProgram.modality,
                        DevelopmentProgram.drug_category,
                    ).in_(asset_modality)
                )
            if asset_program_tag:
                visible_program_tags = public_program_tags(asset_program_tag)
                program_filters.append(
                    or_(
                        *(
                            self._json_array_value_exists(DevelopmentProgram.program_tags, program_tag)
                            for program_tag in visible_program_tags
                        )
                    )
                    if visible_program_tags
                    else literal(False)
                )
            structured_program_match = (
                select(DevelopmentProgram.id)
                .join(
                    DealAssetAssociation,
                    and_(
                        DealAssetAssociation.tenant_id == self.tenant_id,
                        DealAssetAssociation.asset_entity_id == DevelopmentProgram.drug_entity_id,
                    ),
                )
                .where(
                    DevelopmentProgram.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == DealProfile.id,
                    *normalized_asset_constraints,
                    *program_filters,
                )
            )
            relationship_program_match = (
                select(DevelopmentProgram.id)
                .join(
                    Relationship,
                    and_(
                        Relationship.tenant_id == self.tenant_id,
                        Relationship.predicate == "deal_asset",
                        Relationship.object_id == DevelopmentProgram.drug_entity_id,
                    ),
                )
                .where(
                    DevelopmentProgram.tenant_id == self.tenant_id,
                    Relationship.subject_id == DealProfile.entity_id,
                    *program_filters,
                )
            )
            filters.append(
                structured_program_match.exists()
                if normalized_asset_constraints
                else or_(structured_program_match.exists(), relationship_program_match.exists())
            )
        if party:
            normalized_party = party.strip().casefold()
            party_match = (
                select(Relationship.id)
                .join(Entity, and_(Entity.tenant_id == self.tenant_id, Entity.id == Relationship.object_id))
                .where(
                    Relationship.tenant_id == self.tenant_id,
                    Relationship.subject_id == DealProfile.entity_id,
                    Relationship.predicate == "deal_party",
                    func.lower(Entity.name) == normalized_party,
                )
                .exists()
            )
            normalized_party_match = (
                select(DealPartyAssociation.id)
                .join(
                    Entity,
                    and_(
                        Entity.tenant_id == self.tenant_id,
                        Entity.id == DealPartyAssociation.party_entity_id,
                    ),
                )
                .where(
                    DealPartyAssociation.tenant_id == self.tenant_id,
                    DealPartyAssociation.deal_id == DealProfile.id,
                    func.lower(Entity.name) == normalized_party,
                )
                .exists()
            )
            filters.append(
                or_(
                    party_match,
                    normalized_party_match,
                    func.lower(cast(DealProfile.parties, String)).contains(normalized_party, autoescape=True),
                )
            )
        if party_entity_id or party_role or party_country_region or party_organization_type:
            role_match = select(DealPartyAssociation.id).where(
                DealPartyAssociation.tenant_id == self.tenant_id,
                DealPartyAssociation.deal_id == DealProfile.id,
            )
            if party_entity_id:
                role_match = role_match.where(DealPartyAssociation.party_entity_id == party_entity_id)
            if party_role:
                role_match = role_match.where(DealPartyAssociation.role == party_role)
            if party_country_region:
                role_match = role_match.where(DealPartyAssociation.country_region == party_country_region)
            if party_organization_type:
                role_match = role_match.where(DealPartyAssociation.organization_type == party_organization_type)
            filters.append(role_match.exists())
        if development_phase_at_transaction:
            filters.append(
                select(DealAssetAssociation.id)
                .where(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == DealProfile.id,
                    *normalized_asset_constraints,
                    DealAssetAssociation.development_phase_at_transaction == development_phase_at_transaction,
                )
                .exists()
            )
        if current_development_phase:
            current_programs = self._current_program_phase_projection()
            filters.append(
                select(DealAssetAssociation.id)
                .join(
                    current_programs,
                    current_programs.c.drug_entity_id == DealAssetAssociation.asset_entity_id,
                )
                .where(
                    DealAssetAssociation.tenant_id == self.tenant_id,
                    DealAssetAssociation.deal_id == DealProfile.id,
                    *normalized_asset_constraints,
                    current_programs.c.phase == DevelopmentPhase(current_development_phase),
                )
                .exists()
            )
        if right_type or rights_territory:
            rights_match = select(DealRight.id).where(
                DealRight.tenant_id == self.tenant_id,
                DealRight.deal_id == DealProfile.id,
            )
            if right_type:
                rights_match = rights_match.where(DealRight.right_type == right_type)
            if rights_territory:
                rights_match = rights_match.where(DealRight.territory == rights_territory)
            filters.append(rights_match.exists())
        if currency:
            filters.append(DealProfile.currency == currency)
        if announced_from:
            filters.append(DealProfile.announced_at >= announced_from)
        if announced_to:
            filters.append(DealProfile.announced_at <= announced_to)
        if terminated_from:
            filters.append(DealProfile.terminated_at >= terminated_from)
        if terminated_to:
            filters.append(DealProfile.terminated_at <= terminated_to)
        if source_updated_from:
            filters.append(DealProfile.source_updated_at >= source_updated_from)
        if source_updated_to:
            filters.append(DealProfile.source_updated_at <= source_updated_to)
        if upfront_amount_min is not None:
            filters.append(DealProfile.upfront_amount >= upfront_amount_min)
        if upfront_amount_max is not None:
            filters.append(DealProfile.upfront_amount <= upfront_amount_max)
        if total_potential_amount_min is not None:
            filters.append(DealProfile.total_potential_amount >= total_potential_amount_min)
        if total_potential_amount_max is not None:
            filters.append(DealProfile.total_potential_amount <= total_potential_amount_max)
        return filters

    def _regulatory_filters(
        self,
        entity_id: str | None,
        query: str | None,
        agency: str | None,
        *,
        jurisdiction: str | None = None,
        event_type: str | None = None,
        status: str | None = None,
        designation_type: str | None = None,
        label_change_type: str | None = None,
        has_boxed_warning: bool | None = None,
        safety_signal_type: str | None = None,
        safety_severity: str | None = None,
        safety_status: str | None = None,
        decision_from: datetime | None = None,
        decision_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
    ) -> list[ColumnElement[bool]]:
        subject_guard = aliased(Entity)
        filters = [
            RegulatoryEvent.tenant_id == self.tenant_id,
            select(subject_guard.id)
            .where(
                subject_guard.tenant_id == self.tenant_id,
                subject_guard.id == RegulatoryEvent.subject_entity_id,
                subject_guard.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
            )
            .exists(),
        ]
        if not self.include_unpublished:
            filters.extend(
                [
                    self._published_optional_entity(RegulatoryEvent.indication_entity_id),
                    self._published_optional_entity(RegulatoryEvent.organization_entity_id),
                ]
            )
        if entity_id:
            filters.append(
                or_(
                    RegulatoryEvent.subject_entity_id == entity_id,
                    RegulatoryEvent.indication_entity_id == entity_id,
                    RegulatoryEvent.organization_entity_id == entity_id,
                    RegulatoryEvent.subject_entity_id.in_(self._target_asset_ids(entity_id)),
                )
            )
        if agency:
            filters.append(RegulatoryEvent.agency == agency)
        if jurisdiction:
            filters.append(RegulatoryEvent.jurisdiction == jurisdiction)
        if event_type:
            filters.append(RegulatoryEvent.event_type == event_type)
        if status:
            filters.append(RegulatoryEvent.status == status)
        if designation_type:
            filters.append(RegulatoryEvent.designation_type == designation_type)
        if label_change_type:
            filters.append(RegulatoryEvent.label_change_type == label_change_type)
        if has_boxed_warning is not None:
            filters.append(RegulatoryEvent.has_boxed_warning == has_boxed_warning)
        if safety_signal_type:
            filters.append(RegulatoryEvent.safety_signal_type == safety_signal_type)
        if safety_severity:
            filters.append(RegulatoryEvent.safety_severity == safety_severity)
        if safety_status:
            filters.append(RegulatoryEvent.safety_status == safety_status)
        if decision_from:
            filters.append(RegulatoryEvent.decision_date >= decision_from)
        if decision_to:
            filters.append(RegulatoryEvent.decision_date <= decision_to)
        if source_updated_from:
            filters.append(RegulatoryEvent.source_updated_at >= source_updated_from)
        if source_updated_to:
            filters.append(RegulatoryEvent.source_updated_at <= source_updated_to)
        if query:
            pattern = query.strip()
            subject = aliased(Entity)
            indication = aliased(Entity)
            organization = aliased(Entity)
            filters.append(
                or_(
                    RegulatoryEvent.title.icontains(pattern, autoescape=True),
                    RegulatoryEvent.event_identifier.icontains(pattern, autoescape=True),
                    RegulatoryEvent.application_number.icontains(pattern, autoescape=True),
                    RegulatoryEvent.event_type.icontains(pattern, autoescape=True),
                    RegulatoryEvent.status.icontains(pattern, autoescape=True),
                    RegulatoryEvent.jurisdiction.icontains(pattern, autoescape=True),
                    RegulatoryEvent.agency.icontains(pattern, autoescape=True),
                    RegulatoryEvent.designation_type.icontains(pattern, autoescape=True),
                    RegulatoryEvent.label_change_type.icontains(pattern, autoescape=True),
                    RegulatoryEvent.label_version.icontains(pattern, autoescape=True),
                    RegulatoryEvent.approved_population.icontains(pattern, autoescape=True),
                    RegulatoryEvent.line_of_therapy.icontains(pattern, autoescape=True),
                    RegulatoryEvent.biomarker.icontains(pattern, autoescape=True),
                    RegulatoryEvent.route_of_administration.icontains(pattern, autoescape=True),
                    RegulatoryEvent.dosage_form.icontains(pattern, autoescape=True),
                    RegulatoryEvent.safety_signal_type.icontains(pattern, autoescape=True),
                    RegulatoryEvent.safety_term.icontains(pattern, autoescape=True),
                    RegulatoryEvent.safety_severity.icontains(pattern, autoescape=True),
                    RegulatoryEvent.safety_status.icontains(pattern, autoescape=True),
                    RegulatoryEvent.affected_population.icontains(pattern, autoescape=True),
                    select(subject.id)
                    .where(
                        subject.tenant_id == self.tenant_id,
                        subject.id == RegulatoryEvent.subject_entity_id,
                        subject.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                        subject.name.icontains(pattern, autoescape=True),
                    )
                    .exists(),
                    select(indication.id)
                    .where(
                        indication.tenant_id == self.tenant_id,
                        indication.id == RegulatoryEvent.indication_entity_id,
                        indication.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                        indication.name.icontains(pattern, autoescape=True),
                    )
                    .exists(),
                    select(organization.id)
                    .where(
                        organization.tenant_id == self.tenant_id,
                        organization.id == RegulatoryEvent.organization_entity_id,
                        organization.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                        organization.name.icontains(pattern, autoescape=True),
                    )
                    .exists(),
                )
            )
        return filters

    def _epidemiology_filters(
        self,
        disease_entity_id: str | None,
        patient_population_id: str | None,
        query: str | None,
        measure: str | None,
        geography: str | None,
        unit: str | None,
        population_scope: str | None,
        age_group: str | None,
        sex: str | None,
        period_start_from: datetime | None,
        period_end_to: datetime | None,
    ) -> list[ColumnElement[bool]]:
        disease_guard = aliased(Entity)
        population_guard = aliased(PatientPopulation)
        filters = [
            EpidemiologyObservation.tenant_id == self.tenant_id,
            select(disease_guard.id)
            .where(
                disease_guard.tenant_id == self.tenant_id,
                disease_guard.id == EpidemiologyObservation.disease_entity_id,
                disease_guard.entity_type == EntityType.DISEASE,
                disease_guard.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
            )
            .exists(),
            or_(
                EpidemiologyObservation.patient_population_id.is_(None),
                select(population_guard.id)
                .where(
                    population_guard.tenant_id == self.tenant_id,
                    population_guard.id == EpidemiologyObservation.patient_population_id,
                    population_guard.review_status == ReviewStatus.VERIFIED,
                )
                .exists(),
            ),
        ]
        if not self.include_unpublished:
            filters.append(self._published_optional_entity(EpidemiologyObservation.publisher_entity_id))
        if disease_entity_id:
            filters.append(EpidemiologyObservation.disease_entity_id == disease_entity_id)
        if patient_population_id:
            filters.append(EpidemiologyObservation.patient_population_id == patient_population_id)
        if measure:
            filters.append(EpidemiologyObservation.measure == measure)
        if geography:
            filters.append(EpidemiologyObservation.geography == geography)
        if unit:
            filters.append(EpidemiologyObservation.unit == unit)
        if population_scope:
            filters.append(EpidemiologyObservation.population_scope == population_scope)
        if age_group:
            filters.append(EpidemiologyObservation.age_group == age_group)
        if sex:
            filters.append(EpidemiologyObservation.sex == sex)
        if period_start_from:
            filters.append(EpidemiologyObservation.period_end >= period_start_from)
        if period_end_to:
            filters.append(EpidemiologyObservation.period_start <= period_end_to)
        if query:
            pattern = query.strip()
            disease = aliased(Entity)
            publisher = aliased(Entity)
            patient_population = aliased(PatientPopulation)
            filters.append(
                or_(
                    EpidemiologyObservation.observation_identifier.icontains(pattern, autoescape=True),
                    EpidemiologyObservation.measure.icontains(pattern, autoescape=True),
                    EpidemiologyObservation.geography.icontains(pattern, autoescape=True),
                    EpidemiologyObservation.population_scope.icontains(pattern, autoescape=True),
                    EpidemiologyObservation.methodology.icontains(pattern, autoescape=True),
                    select(disease.id)
                    .where(
                        disease.tenant_id == self.tenant_id,
                        disease.id == EpidemiologyObservation.disease_entity_id,
                        disease.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                        disease.name.icontains(pattern, autoescape=True),
                    )
                    .exists(),
                    select(publisher.id)
                    .where(
                        publisher.tenant_id == self.tenant_id,
                        publisher.id == EpidemiologyObservation.publisher_entity_id,
                        publisher.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                        publisher.name.icontains(pattern, autoescape=True),
                    )
                    .exists(),
                    select(patient_population.id)
                    .where(
                        patient_population.tenant_id == self.tenant_id,
                        patient_population.id == EpidemiologyObservation.patient_population_id,
                        patient_population.review_status == ReviewStatus.VERIFIED,
                        or_(
                            patient_population.name.icontains(pattern, autoescape=True),
                            patient_population.population_key.icontains(pattern, autoescape=True),
                        ),
                    )
                    .exists(),
                )
            )
        return filters

    def _news_event_filters(
        self,
        entity_id: str | None,
        query: str | None,
        event_type: str | None,
        publisher: str | None,
        language: str | None,
        venue: str | None,
        published_from: datetime | None,
        published_to: datetime | None,
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = [NewsEvent.tenant_id == self.tenant_id]
        if not self.include_unpublished:
            filters.append(self._published_optional_entity(NewsEvent.publisher_entity_id))
        if entity_id:
            filters.append(
                or_(
                    NewsEvent.publisher_entity_id == entity_id,
                    cast(NewsEvent.related_entity_ids, String).contains(f'"{entity_id}"', autoescape=True),
                )
            )
        if event_type:
            filters.append(NewsEvent.event_type == event_type)
        if language:
            filters.append(NewsEvent.language == language)
        if venue:
            filters.append(NewsEvent.venue == venue)
        if published_from:
            filters.append(NewsEvent.published_at >= published_from)
        if published_to:
            filters.append(NewsEvent.published_at <= published_to)
        if publisher:
            publisher_pattern = publisher.strip()
            publisher_entity = aliased(Entity)
            filters.append(
                select(publisher_entity.id)
                .where(
                    publisher_entity.tenant_id == self.tenant_id,
                    publisher_entity.id == NewsEvent.publisher_entity_id,
                    publisher_entity.review_status == ReviewStatus.VERIFIED if not self.include_unpublished else true(),
                    publisher_entity.name.icontains(publisher_pattern, autoescape=True),
                )
                .exists()
            )
        if query:
            pattern = query.strip()
            publisher_entity = aliased(Entity)
            filters.append(
                or_(
                    NewsEvent.event_identifier.icontains(pattern, autoescape=True),
                    NewsEvent.title.icontains(pattern, autoescape=True),
                    NewsEvent.summary.icontains(pattern, autoescape=True),
                    NewsEvent.venue.icontains(pattern, autoescape=True),
                    select(publisher_entity.id)
                    .where(
                        publisher_entity.tenant_id == self.tenant_id,
                        publisher_entity.id == NewsEvent.publisher_entity_id,
                        publisher_entity.review_status == ReviewStatus.VERIFIED
                        if not self.include_unpublished
                        else true(),
                        publisher_entity.name.icontains(pattern, autoescape=True),
                    )
                    .exists(),
                )
            )
        return filters

    def _count(self, model: type[Any], filters: list[ColumnElement[bool]]) -> int:
        return int(self.session.scalar(select(func.count()).select_from(model).where(*filters)) or 0)


def _sar_comparability_reasons(activity: ActivityMeasurement, assay: Assay) -> list[str]:
    reasons: list[str] = []
    if activity.standard_type is None:
        reasons.append("standard_type_missing")
    if activity.pchembl_value is None:
        reasons.append("pchembl_missing")
    if activity.standard_relation != MeasurementRelation.EQUAL:
        reasons.append("censored_or_approximate_relation")
    if assay.assay_type is None:
        reasons.append("assay_type_missing")
    if assay.assay_format is None:
        reasons.append("assay_format_missing")
    return reasons
