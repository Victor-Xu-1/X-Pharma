from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from pharma_intel.models.enums import (
    DevelopmentPhase,
    ReviewStatus,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .chemistry import (
    BioactivityRead,
    CompoundStructureRead,
)
from .deals import (
    CompanyTimelineResult,
    DealSearchItemRead,
)
from .epidemiology import (
    EpidemiologyObservationSearchResult,
)
from .identity import (
    EntityRead,
)
from .news import (
    NewsEventSearchItemRead,
)
from .patents import (
    PatentFamilyRead,
)
from .programs import (
    CompetitiveProgramRead,
)
from .query import (
    QueryResultMetadata,
)
from .regulatory import (
    RegulatoryEventSearchItemRead,
)
from .targets import (
    TargetEvidenceRead,
)
from .trials import (
    ClinicalTrialSearchItemRead,
)
from .types import (
    EntityDossierDomain,
)


class CompanyDossierSummaryRead(BaseModel):
    program_count: int = Field(ge=0)
    drug_count: int = Field(ge=0)
    target_count: int = Field(ge=0)
    indication_count: int = Field(ge=0)
    deal_count: int = Field(ge=0)
    timeline_event_count: int = Field(ge=0)
    modalities: list[str] = Field(default_factory=list)
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    highest_phase: DevelopmentPhase | None = None
    latest_activity_at: datetime | None = None


class DiseaseDossierSummaryRead(BaseModel):
    program_count: int = Field(ge=0)
    drug_count: int = Field(ge=0)
    target_count: int = Field(ge=0)
    organization_count: int = Field(ge=0)
    clinical_trial_count: int = Field(ge=0)
    patent_count: int = Field(ge=0)
    epidemiology_observation_count: int = Field(ge=0)
    patient_population_count: int = Field(ge=0)
    modalities: list[str] = Field(default_factory=list)
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    highest_phase: DevelopmentPhase | None = None
    measures: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    latest_activity_at: datetime | None = None


class EntityRelationshipRead(BaseModel):
    id: str
    predicate: str
    direction: Literal["outgoing", "incoming"]
    related_entity: EntityRead
    attributes: dict[str, Any]
    review_status: ReviewStatus
    valid_from: datetime | None
    valid_to: datetime | None


class EntityDossierCoverageRead(BaseModel):
    domain: EntityDossierDomain
    total: int = Field(ge=0)
    returned: int = Field(ge=0)
    status: Literal["available", "not_observed", "truncated"]
    note: str


class EntityDossierResponse(BaseModel):
    entity: EntityRead
    relationships: list[EntityRelationshipRead]
    activities: list[BioactivityRead]
    programs: list[CompetitiveProgramRead]
    clinical_trials: list[ClinicalTrialSearchItemRead]
    patents: list[PatentFamilyRead]
    deals: list[DealSearchItemRead]
    regulatory_events: list[RegulatoryEventSearchItemRead]
    news_events: list[NewsEventSearchItemRead]
    structures: list[CompoundStructureRead]
    target_evidence: list[TargetEvidenceRead]
    coverage: list[EntityDossierCoverageRead]
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class CompanyDossierResponse(EntityDossierResponse):
    summary: CompanyDossierSummaryRead
    timeline: CompanyTimelineResult


class DiseaseDossierResponse(EntityDossierResponse):
    summary: DiseaseDossierSummaryRead
    epidemiology: EpidemiologyObservationSearchResult


class DrugDossierSummaryRead(BaseModel):
    program_count: int = Field(ge=0)
    target_count: int = Field(ge=0)
    indication_count: int = Field(ge=0)
    organization_count: int = Field(ge=0)
    modalities: list[str]
    highest_phase: DevelopmentPhase | None = None
    highest_global_phase: DevelopmentPhase | None = None
    highest_china_phase: DevelopmentPhase | None = None
    latest_status_date: datetime | None = None


class DrugDossierResponse(EntityDossierResponse):
    deals: list[DealSearchItemRead]
    summary: DrugDossierSummaryRead


class DrugProgramSearchResult(QueryResultMetadata):
    """A paged, human-readable view of one drug's complete development set."""

    items: list[CompetitiveProgramRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)


class DrugComparisonProfileRead(BaseModel):
    """Complete, server-computed development profile for one compared drug."""

    entity: EntityRead
    summary: DrugDossierSummaryRead
    target_names: list[str]
    indication_names: list[str]
    organization_names: list[str]
    program_status_counts: dict[str, int]
    as_of: datetime


class DrugComparisonResult(BaseModel):
    """Bounded batch response used by the human drug comparison workspace."""

    query_schema_version: Literal["pharma.drug.comparison.v1"] = "pharma.drug.comparison.v1"
    items: list[DrugComparisonProfileRead]
    as_of: datetime


class TargetProfileResponse(BaseModel):
    profile_id: str | None = None
    entity: EntityRead
    gene_symbol: str | None = None
    uniprot_accession: str | None = None
    organism: str | None = None
    target_class: str | None = None
    sequence: str | None = None
    function_summary: str | None = None
    activity_count: int
    program_count: int
    target_evidence_count: int = 0
    source_document_id: str | None = None
    as_of: datetime


class TargetDossierSummaryRead(BaseModel):
    """Server-computed target landscape counts over the complete authorized result set.

    Counts are never derived from the truncated record collections returned alongside
    them. Free-text source statuses are classified by an explicit versioned vocabulary
    and anything outside it is reported as unclassified instead of being silently
    bucketed.
    """

    program_count: int = Field(ge=0)
    phase_distribution: dict[str, int] = Field(default_factory=dict)
    highest_phase: DevelopmentPhase | None = None
    clinical_trial_count: int = Field(ge=0)
    recruiting_trial_count: int = Field(ge=0)
    unclassified_trial_status_count: int = Field(ge=0)
    patent_count: int = Field(ge=0)
    active_patent_count: int = Field(ge=0)
    unclassified_patent_status_count: int = Field(ge=0)
    regulatory_event_count: int = Field(ge=0)
    approval_event_count: int = Field(ge=0)
    status_vocabulary_version: str


class TargetDossierResponse(EntityDossierResponse):
    profile: TargetProfileResponse
    summary: TargetDossierSummaryRead
