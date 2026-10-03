from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.models.enums import (
    DevelopmentPhase,
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
    PIPELINE_SORT_FIELDS,
    PipelineLandscapeStageScope,
    PipelineResultGrain,
    PipelineSortField,
    PipelineTargetAggregation,
    SortToken,
)


class PipelineSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    modality: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    innovation_type: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    therapeutic_area: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    drug_category: list[Annotated[str, Field(min_length=1, max_length=120)]] | None = Field(
        default=None,
        max_length=20,
    )
    program_status: Literal["active", "inactive", "unknown"] | None = None
    organization_role: Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"] | None = (
        None
    )
    organization_type: str | None = Field(default=None, min_length=1, max_length=120)
    organization_country_region: str | None = Field(default=None, min_length=1, max_length=120)
    phase: DevelopmentPhase | None = None
    geography: str | None = Field(default=None, min_length=1, max_length=120)
    status_date_from: date | None = None
    status_date_to: date | None = None
    drug_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    target_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    target_combination_key: str | None = Field(default=None, min_length=36, max_length=760)
    disease_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    organization_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    global_phase: DevelopmentPhase | None = None
    china_phase: DevelopmentPhase | None = None
    global_phase_started_from: date | None = None
    global_phase_started_to: date | None = None
    china_phase_started_from: date | None = None
    china_phase_started_to: date | None = None
    development_rights_region: str | None = Field(default=None, min_length=1, max_length=240)
    commercialization_rights_region: str | None = Field(default=None, min_length=1, max_length=240)
    program_tag: list[Annotated[str, Field(min_length=1, max_length=240)]] | None = Field(
        default=None,
        max_length=20,
    )
    milestone_type: str | None = Field(default=None, min_length=1, max_length=120)
    milestone_from: date | None = None
    milestone_to: date | None = None
    has_clinical_results: bool | None = None
    clinical_result_evaluation: TrialResultEvaluation | None = None
    has_deal: bool | None = None
    deal_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    deal_total_potential_amount_min: float | None = Field(default=None, ge=0)
    deal_total_potential_amount_max: float | None = Field(default=None, ge=0)
    sort_by: Literal[
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
    ] = "status_date"
    sort_direction: Literal["asc", "desc"] = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    display_mode: Literal["list", "landscape"] = "list"
    analysis_dimension: Literal[
        "all",
        "global_phase",
        "china_phase",
        "targets",
        "target_combinations",
        "diseases",
        "organizations",
        "modality",
        "geography",
    ] = "all"
    analysis_view: Literal["chart", "table"] = "chart"
    analysis_limit: Literal[5, 8, 20, 50, 100, 200] = 8
    analysis_stage_scope: Literal["overall", "global", "china"] = "overall"
    target_aggregation: Literal["all", "primary"] = "all"

    @field_validator("modality", "innovation_type", "therapeutic_area", "drug_category", "program_tag", mode="before")
    @classmethod
    def normalize_repeated_pipeline_filters(cls, value: Any) -> Any:
        # Legacy saved queries and single-value URL parameters stored these as plain
        # strings; normalize to single-element lists so replay keeps the same semantics.
        # Empty collections normalize to None so they can never satisfy the
        # at-least-one-filter rule while applying no actual condition.
        if value is None:
            return None
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            return values
        normalized: list[Any] = []
        for item in values:
            candidate = item.strip() if isinstance(item, str) else item
            if candidate not in normalized:
                normalized.append(candidate)
        return normalized or None

    @model_validator(mode="after")
    def validate_pipeline_query(self) -> PipelineSavedSearchQuery:
        _synchronize_saved_sort(self, PIPELINE_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.modality,
            self.innovation_type,
            self.therapeutic_area,
            self.drug_category,
            self.program_status,
            self.organization_role,
            self.organization_type,
            self.organization_country_region,
            self.phase,
            self.geography,
            self.status_date_from,
            self.status_date_to,
            self.drug_entity_id,
            self.target_entity_id,
            self.target_combination_key,
            self.disease_entity_id,
            self.organization_entity_id,
            self.global_phase,
            self.china_phase,
            self.global_phase_started_from,
            self.global_phase_started_to,
            self.china_phase_started_from,
            self.china_phase_started_to,
            self.development_rights_region,
            self.commercialization_rights_region,
            self.program_tag,
            self.milestone_type,
            self.milestone_from,
            self.milestone_to,
            self.has_clinical_results,
            self.clinical_result_evaluation,
            self.has_deal,
            self.deal_currency,
            self.deal_total_potential_amount_min,
            self.deal_total_potential_amount_max,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one pipeline search filter is required")
        for start, end, label in (
            (self.status_date_from, self.status_date_to, "status_date"),
            (self.global_phase_started_from, self.global_phase_started_to, "global_phase_started"),
            (self.china_phase_started_from, self.china_phase_started_to, "china_phase_started"),
            (self.milestone_from, self.milestone_to, "milestone"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        if self.has_clinical_results is False and self.clinical_result_evaluation is not None:
            raise ValueError("clinical_result_evaluation cannot be combined with has_clinical_results=false")
        if self.has_deal is False and any(
            value is not None
            for value in (
                self.deal_currency,
                self.deal_total_potential_amount_min,
                self.deal_total_potential_amount_max,
            )
        ):
            raise ValueError("deal detail filters cannot be combined with has_deal=false")
        if (
            self.deal_total_potential_amount_min is not None or self.deal_total_potential_amount_max is not None
        ) and self.deal_currency is None:
            raise ValueError("deal_currency is required for disclosed amount filters")
        if (
            self.deal_total_potential_amount_min is not None
            and self.deal_total_potential_amount_max is not None
            and self.deal_total_potential_amount_min > self.deal_total_potential_amount_max
        ):
            raise ValueError("deal_total_potential_amount_min must not exceed maximum")
        return self


class ProgramStatusHistoryRead(BaseModel):
    phase: str
    status: str | None = None
    effective_at: datetime
    geography: str | None = None
    reason: str | None = None
    source_document_id: str | None = None


class ProgramMilestoneRead(BaseModel):
    milestone_type: str
    title: str
    occurred_at: datetime
    geography: str | None = None
    description: str | None = None
    source_document_id: str | None = None


class ProgramTargetRead(BaseModel):
    entity_id: str
    name: str
    role: Literal["primary", "combination"]
    position: int = Field(ge=0, lt=20)


class ProgramOrganizationRead(BaseModel):
    entity_id: str
    name: str
    role: Literal["originator", "collaborator", "licensee", "licensor", "manufacturer", "other"]
    country_region: str | None = None
    organization_type: str | None = None
    position: int = Field(ge=0, lt=20)


class ProgramIndicationRead(BaseModel):
    program_id: str
    disease_entity_id: str | None = None
    disease_name: str | None = None
    phase: str
    global_phase: str | None = None
    china_phase: str | None = None
    global_phase_started_at: datetime | None = None
    china_phase_started_at: datetime | None = None
    program_status: Literal["active", "inactive", "unknown"] | None = None
    status_date: datetime | None = None
    geography: str | None = None


class CompetitiveProgramRead(BaseModel):
    id: str
    drug_entity_id: str
    drug_name: str
    target_entity_id: str | None
    target_name: str | None
    targets: list[ProgramTargetRead] = Field(default_factory=list, max_length=20)
    target_combination_key: str | None = Field(default=None, max_length=760)
    disease_entity_id: str | None
    disease_name: str | None
    organization_entity_id: str | None
    organization_name: str | None
    organizations: list[ProgramOrganizationRead] = Field(default_factory=list, max_length=20)
    modality: str | None
    innovation_type: str | None = None
    therapeutic_area: str | None = None
    drug_category: str | None = None
    mechanism_of_action: str | None
    phase: str
    status_detail: str | None
    program_status: Literal["active", "inactive", "unknown"] | None = None
    status_date: datetime | None
    geography: str | None
    global_phase: str | None = None
    china_phase: str | None = None
    global_phase_started_at: datetime | None = None
    china_phase_started_at: datetime | None = None
    development_rights_regions: list[str] = Field(default_factory=list)
    commercialization_rights_regions: list[str] = Field(default_factory=list)
    program_tags: list[str] = Field(default_factory=list)
    status_history: list[ProgramStatusHistoryRead] = Field(default_factory=list)
    milestones: list[ProgramMilestoneRead] = Field(default_factory=list)
    clinical_trial_count: int = Field(default=0, ge=0)
    has_clinical_results: bool = False
    clinical_result_evaluations: list[TrialResultEvaluation] = Field(default_factory=list)
    deal_count: int = Field(default=0, ge=0)
    deal_currencies: list[str] = Field(default_factory=list)
    source_document_id: str | None
    project_count: int = Field(default=1, ge=1)
    indications: list[ProgramIndicationRead] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    mechanisms_of_action: list[str] = Field(default_factory=list)
    innovation_types: list[str] = Field(default_factory=list)
    therapeutic_areas: list[str] = Field(default_factory=list)
    drug_categories: list[str] = Field(default_factory=list)
    program_status_counts: dict[str, int] = Field(default_factory=dict)


class PipelineLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=760)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)
    entity_id: str | None = None
    phase_counts: dict[str, int] = Field(default_factory=dict)


class PipelineLandscapeRead(BaseModel):
    total_programs: int = Field(ge=0)
    distinct_drugs: int = Field(ge=0)
    distinct_targets: int = Field(ge=0)
    distinct_diseases: int = Field(ge=0)
    distinct_organizations: int = Field(ge=0)
    limit: int = Field(ge=5, le=200)
    stage_scope: PipelineLandscapeStageScope
    target_aggregation: PipelineTargetAggregation
    overall_phase: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    global_phase: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    china_phase: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    targets: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    diseases: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    target_combinations: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    modality: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    geography: list[PipelineLandscapeBucketRead] = Field(default_factory=list)
    organizations: list[PipelineLandscapeBucketRead] = Field(default_factory=list)


class PipelineSearchResult(QueryResultMetadata):
    items: list[CompetitiveProgramRead]
    total: int
    limit: int
    offset: int
    sort_by: PipelineSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    landscape: PipelineLandscapeRead
    result_grain: PipelineResultGrain = "program"
    project_total: int = Field(default=0, ge=0)
    as_of: datetime
    warnings: list[str] = Field(default_factory=list)
