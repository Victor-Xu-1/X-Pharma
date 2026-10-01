from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.models.enums import (
    EntityType,
    TrialEntityRole,
    TrialResultDisclosureType,
    TrialResultEvaluation,
)
from pharma_intel.sorting import (
    MAX_SORT_CRITERIA,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .query import (
    QueryResultMetadata,
    SortCriterionRead,
    _synchronize_saved_sort,
)
from .types import (
    CLINICAL_TRIAL_SORT_FIELDS,
    ClinicalTrialSortField,
    SortToken,
    TrialInitiationType,
    TrialTherapyLine,
)


class ClinicalTrialSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    registry: str | None = Field(default=None, min_length=1, max_length=80)
    status: str | None = Field(default=None, min_length=1, max_length=100)
    phase: str | None = Field(default=None, min_length=1, max_length=80)
    study_type: str | None = Field(default=None, min_length=1, max_length=80)
    acronym: str | None = Field(default=None, min_length=1, max_length=240)
    initiation_type: Literal["iit", "ist"] | None = None
    therapy_line: (
        Literal[
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
        | None
    ) = None
    has_results: bool | None = None
    result_evaluation: TrialResultEvaluation | None = None
    results_posted_from: date | None = None
    results_posted_to: date | None = None
    investigational_drug: str | None = Field(default=None, min_length=1, max_length=500)
    combination_drug: str | None = Field(default=None, min_length=1, max_length=500)
    investigational_target: str | None = Field(default=None, min_length=1, max_length=500)
    combination_target: str | None = Field(default=None, min_length=1, max_length=500)
    investigational_drug_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    combination_drug_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    investigational_target_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    combination_target_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    linked_drug_modality: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_innovation_type: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_category: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None, min_length=1, max_length=20
    )
    linked_drug_global_phase: str | None = Field(default=None, min_length=1, max_length=40)
    linked_drug_organization_country_region: str | None = Field(default=None, min_length=1, max_length=120)
    role_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    role_entity_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    role_entity_role: TrialEntityRole | None = None
    has_key_result: bool | None = None
    publication_id: str | None = Field(default=None, min_length=1, max_length=240)
    conference: str | None = Field(default=None, min_length=1, max_length=500)
    disclosed_from: date | None = None
    disclosed_to: date | None = None
    sort_by: Literal[
        "last_update_posted",
        "registry_id",
        "has_results",
        "result_evaluation",
        "overall_status",
        "enrollment",
        "study_type",
        "acronym",
        "initiation_type",
    ] = "last_update_posted"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    # Presentation state travels with the saved contract so monitoring replay restores
    # the exact list/landscape and chart/table view; it never changes the fact query.
    display_mode: Literal["list", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"

    @model_validator(mode="after")
    def validate_clinical_trial_query(self) -> ClinicalTrialSavedSearchQuery:
        _synchronize_saved_sort(self, CLINICAL_TRIAL_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.registry,
            self.status,
            self.phase,
            self.study_type,
            self.acronym,
            self.initiation_type,
            self.therapy_line,
            self.has_results,
            self.result_evaluation,
            self.results_posted_from,
            self.results_posted_to,
            self.investigational_drug,
            self.combination_drug,
            self.investigational_target,
            self.combination_target,
            self.investigational_drug_entity_ids,
            self.combination_drug_entity_ids,
            self.investigational_target_entity_ids,
            self.combination_target_entity_ids,
            self.linked_drug_modality,
            self.linked_drug_innovation_type,
            self.linked_drug_category,
            self.linked_drug_program_tag,
            self.linked_drug_global_phase,
            self.linked_drug_organization_country_region,
            self.role_entity_id,
            self.role_entity_ids,
            self.has_key_result,
            self.publication_id,
            self.conference,
            self.disclosed_from,
            self.disclosed_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one clinical trial search filter is required")
        if self.role_entity_id is not None and self.role_entity_ids is not None:
            raise ValueError("role_entity_id cannot be combined with role_entity_ids")
        if self.role_entity_role is not None and self.role_entity_id is None and self.role_entity_ids is None:
            raise ValueError("role_entity_role requires role_entity_id or role_entity_ids")
        for start, end, label in (
            (self.results_posted_from, self.results_posted_to, "results_posted"),
            (self.disclosed_from, self.disclosed_to, "disclosed"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        return self

    @field_validator(
        "investigational_drug_entity_ids",
        "combination_drug_entity_ids",
        "investigational_target_entity_ids",
        "combination_target_entity_ids",
        "role_entity_ids",
    )
    @classmethod
    def validate_role_entity_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if any(len(entity_id) != 36 for entity_id in value):
            raise ValueError("Clinical trial role entity IDs must be UUID strings")
        if len(value) != len(set(value)):
            raise ValueError("Clinical trial role entity IDs must be unique")
        return sorted(value)

    @field_validator(
        "linked_drug_modality",
        "linked_drug_innovation_type",
        "linked_drug_category",
        "linked_drug_program_tag",
        mode="before",
    )
    @classmethod
    def normalize_linked_drug_values(cls, value: list[str] | str | None) -> list[str] | None:
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        normalized = sorted({item.strip() for item in values if item.strip()})
        return normalized or None


class ClinicalTrialInterventionRead(BaseModel):
    name: str
    type: str | None = None
    description: str | None = None
    arm_labels: list[str] = Field(default_factory=list)
    other_names: list[str] = Field(default_factory=list)


class ClinicalTrialSponsorRead(BaseModel):
    name: str
    sponsor_class: str | None = None


class ClinicalTrialLocationRead(BaseModel):
    facility: str | None = None
    city: str | None = None
    state: str | None = None
    country: str
    status: str | None = None


class ClinicalTrialDesignRead(BaseModel):
    allocation: str | None = None
    intervention_model: str | None = None
    intervention_model_description: str | None = None
    primary_purpose: str | None = None
    observational_model: str | None = None
    time_perspective: str | None = None
    masking: str | None = None
    masking_description: str | None = None
    who_masked: list[str] = Field(default_factory=list)


class ClinicalTrialEligibilityRead(BaseModel):
    minimum_age: str | None = None
    maximum_age: str | None = None
    sex: str | None = None
    gender_based: bool | None = None
    healthy_volunteers: bool | None = None
    sampling_method: str | None = None
    criteria: str | None = None


class ClinicalTrialArmRead(BaseModel):
    label: str
    type: str | None = None
    description: str | None = None
    intervention_names: list[str] = Field(default_factory=list)


class ClinicalTrialOutcomeResultRead(BaseModel):
    group_label: str
    value: str
    unit: str | None = None
    participants: int | None = None
    dispersion: str | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None


class ClinicalTrialStatisticalAnalysisRead(BaseModel):
    method: str | None = None
    p_value: str | None = None
    parameter_type: str | None = None
    parameter_value: float | None = None
    confidence_interval_percent: float | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    notes: str | None = None


class ClinicalTrialOutcomeRead(BaseModel):
    outcome_type: str | None = None
    measure: str
    description: str | None = None
    time_frame: str | None = None
    results: list[ClinicalTrialOutcomeResultRead] = Field(default_factory=list)
    statistical_analyses: list[ClinicalTrialStatisticalAnalysisRead] = Field(default_factory=list)


class ClinicalTrialStatusHistoryRead(BaseModel):
    status: str
    effective_at: datetime
    effective_at_precision: Literal["day", "month", "year"] | None = None
    reason: str | None = None
    source_document_id: str | None = None


class ClinicalTrialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_id: str
    registry_name: str
    registry_id: str
    official_title: str
    acronym: str | None
    initiation_type: TrialInitiationType | None
    therapy_lines: list[TrialTherapyLine]
    overall_status: str | None
    phases: list[str]
    study_type: str | None
    enrollment: int | None
    start_date: datetime | None
    start_date_precision: Literal["day", "month", "year"] | None
    completion_date: datetime | None
    completion_date_precision: Literal["day", "month", "year"] | None
    interventions: list[ClinicalTrialInterventionRead]
    conditions: list[str]
    sponsors: list[ClinicalTrialSponsorRead]
    outcomes: list[ClinicalTrialOutcomeRead]
    locations: list[ClinicalTrialLocationRead]
    study_design: ClinicalTrialDesignRead
    eligibility: ClinicalTrialEligibilityRead
    arms: list[ClinicalTrialArmRead]
    status_history: list[ClinicalTrialStatusHistoryRead]
    has_results: bool
    result_evaluation: TrialResultEvaluation | None
    results_first_posted: datetime | None
    last_update_posted: datetime | None
    source_document_id: str | None


class ClinicalTrialLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class ClinicalTrialEntityRoleRead(BaseModel):
    entity_id: str
    name: str
    entity_type: EntityType
    role: TrialEntityRole


class ClinicalTrialResultDisclosureRead(BaseModel):
    id: str
    disclosure_key: str
    version: int
    disclosure_type: TrialResultDisclosureType
    external_id: str | None
    title: str
    disclosed_at: datetime
    conference_name: str | None
    is_key_result: bool
    result_evaluation: TrialResultEvaluation | None
    source_locator: str | None
    source_quote: str | None
    source_document_id: str | None


class ClinicalTrialSearchItemRead(ClinicalTrialRead):
    linked_entities: list[ClinicalTrialLinkedEntityRead]
    entity_roles: list[ClinicalTrialEntityRoleRead] = Field(default_factory=list)
    key_result_count: int = 0
    latest_result_disclosure: ClinicalTrialResultDisclosureRead | None = None


class ClinicalTrialDetailRead(ClinicalTrialSearchItemRead):
    result_disclosures: list[ClinicalTrialResultDisclosureRead] = Field(default_factory=list)


class ClinicalTrialLandscapeMatrixRowRead(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    total: int = Field(ge=0)
    values: dict[str, int] = Field(default_factory=dict)


class ClinicalTrialLandscapeRead(BaseModel):
    total_trials: int = Field(ge=0)
    publication_year_phase: list[ClinicalTrialLandscapeMatrixRowRead] = Field(default_factory=list)
    phase_evaluation: list[ClinicalTrialLandscapeMatrixRowRead] = Field(default_factory=list)


class ClinicalTrialSearchResult(QueryResultMetadata):
    items: list[ClinicalTrialSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: ClinicalTrialSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: ClinicalTrialLandscapeRead
    as_of: datetime
    warnings: list[str]
