from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from pharma_intel.sorting import (
    SORT_TOKEN_PATTERN,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

EntitySortField = Literal["relevance", "name", "entity_type", "updated_at"]


ENTITY_SORT_FIELDS: tuple[EntitySortField, ...] = ("relevance", "name", "entity_type", "updated_at")


SortToken = Annotated[str, Field(pattern=SORT_TOKEN_PATTERN.pattern)]


ProvenanceResourceType = Literal[
    "activity_measurement",
    "assay",
    "clinical_trial",
    "compound_structure",
    "deal",
    "development_program",
    "epidemiology_observation",
    "evidence_claim",
    "news_event",
    "patient_population",
    "patent_family",
    "regulatory_event",
    "target_profile",
    "target_evidence",
]


PipelineLandscapeStageScope = Literal["overall", "global", "china"]


PipelineTargetAggregation = Literal["all", "primary"]


PipelineResultGrain = Literal["program", "drug"]


PipelineSortField = Literal[
    "status_date",
    "drug_name",
    "target_name",
    "disease_name",
    "organization_name",
    "modality",
    "mechanism_of_action",
    "phase",
    "status_detail",
    "geography",
    "global_phase",
    "china_phase",
    "global_phase_started_at",
    "china_phase_started_at",
]


PIPELINE_SORT_FIELDS: tuple[PipelineSortField, ...] = (
    "status_date",
    "drug_name",
    "target_name",
    "disease_name",
    "organization_name",
    "modality",
    "mechanism_of_action",
    "phase",
    "status_detail",
    "geography",
    "global_phase",
    "china_phase",
    "global_phase_started_at",
    "china_phase_started_at",
)


ClinicalTrialSortField = Literal[
    "last_update_posted",
    "registry_id",
    "has_results",
    "result_evaluation",
    "overall_status",
    "enrollment",
    "study_type",
    "acronym",
    "initiation_type",
]


CLINICAL_TRIAL_SORT_FIELDS: tuple[ClinicalTrialSortField, ...] = (
    "last_update_posted",
    "registry_id",
    "has_results",
    "result_evaluation",
    "overall_status",
    "enrollment",
    "study_type",
    "acronym",
    "initiation_type",
)


TrialInitiationType = Literal["iit", "ist"]


TrialTherapyLine = Literal[
    "first_line",
    "second_line",
    "third_or_later",
    "prevention",
    "treatment_naive",
    "add_on",
    "adjuvant",
    "neoadjuvant",
    "maintenance",
    "consolidation",
    "induction",
    "conversion",
]


PatentSortField = Literal["priority_date", "family_identifier", "legal_status", "expiration_date"]


PATENT_SORT_FIELDS: tuple[PatentSortField, ...] = (
    "priority_date",
    "family_identifier",
    "legal_status",
    "expiration_date",
)


NewsSortField = Literal["published_at", "title", "event_type", "publisher", "venue"]


NEWS_SORT_FIELDS: tuple[NewsSortField, ...] = ("published_at", "title", "event_type", "publisher", "venue")


DealSortField = Literal[
    "announced_at",
    "name",
    "deal_type",
    "status",
    "direction",
    "territory",
    "upfront_amount",
    "total_potential_amount",
]


DEAL_SORT_FIELDS: tuple[DealSortField, ...] = (
    "announced_at",
    "name",
    "deal_type",
    "status",
    "direction",
    "territory",
    "upfront_amount",
    "total_potential_amount",
)


RegulatorySortField = Literal[
    "decision_date",
    "title",
    "agency",
    "jurisdiction",
    "event_type",
    "status",
    "subject",
    "source_updated_at",
]


REGULATORY_SORT_FIELDS: tuple[RegulatorySortField, ...] = (
    "decision_date",
    "title",
    "agency",
    "jurisdiction",
    "event_type",
    "status",
    "subject",
    "source_updated_at",
)


EpidemiologySortField = Literal[
    "period_end",
    "period_start",
    "disease",
    "measure",
    "value",
    "geography",
    "unit",
    "publisher",
    "sample_size",
]


EPIDEMIOLOGY_SORT_FIELDS: tuple[EpidemiologySortField, ...] = (
    "period_end",
    "period_start",
    "disease",
    "measure",
    "value",
    "geography",
    "unit",
    "publisher",
    "sample_size",
)


EntityDossierDomain = Literal[
    "relationships",
    "evidence",
    "activities",
    "programs",
    "clinical_trials",
    "patents",
    "deals",
    "regulatory_events",
    "news_events",
    "structures",
    "target_evidence",
]
