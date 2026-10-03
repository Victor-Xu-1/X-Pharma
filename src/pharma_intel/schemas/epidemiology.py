from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pharma_intel.models.enums import (
    EntityType,
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
    EPIDEMIOLOGY_SORT_FIELDS,
    EpidemiologySortField,
    SortToken,
)


class EpidemiologySavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    disease_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    measure: (
        Literal[
            "prevalence",
            "incidence",
            "mortality",
            "patient_count",
            "diagnosed_count",
            "treated_count",
            "survival_rate",
            "daly",
            "other",
        ]
        | None
    ) = None
    geography: str | None = Field(default=None, min_length=1, max_length=160)
    unit: str | None = Field(default=None, min_length=1, max_length=120)
    patient_population_id: str | None = Field(default=None, min_length=36, max_length=36)
    population_scope: str | None = Field(default=None, min_length=1, max_length=500)
    age_group: str | None = Field(default=None, min_length=1, max_length=120)
    sex: str | None = Field(default=None, min_length=1, max_length=80)
    period_start_from: date | None = None
    period_end_to: date | None = None
    sort_by: Literal[
        "period_end",
        "period_start",
        "disease",
        "measure",
        "value",
        "geography",
        "unit",
        "publisher",
        "sample_size",
    ] = "period_end"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )
    # Presentation state for monitoring replay; never counts as a fact filter.
    display_mode: Literal["list", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"

    @model_validator(mode="after")
    def validate_epidemiology_query(self) -> EpidemiologySavedSearchQuery:
        _synchronize_saved_sort(self, EPIDEMIOLOGY_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.disease_entity_id,
            self.measure,
            self.geography,
            self.unit,
            self.patient_population_id,
            self.population_scope,
            self.age_group,
            self.sex,
            self.period_start_from,
            self.period_end_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one epidemiology search filter is required")
        if self.period_start_from and self.period_end_to and self.period_start_from > self.period_end_to:
            raise ValueError("period_start_from must not be after period_end_to")
        return self


class EpidemiologyLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class PatientPopulationRead(BaseModel):
    id: str
    population_key: str
    name: str
    description: str | None
    attributes: dict[str, Any]
    disease_entities: list[EpidemiologyLinkedEntityRead]
    target_entities: list[EpidemiologyLinkedEntityRead]


class PatientPopulationOptionRead(BaseModel):
    id: str
    name: str
    count: int


class EpidemiologyObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    observation_identifier: str
    disease_entity_id: str
    patient_population_id: str | None
    measure: str
    value: float
    lower_bound: float | None
    upper_bound: float | None
    unit: str
    geography: str
    population_scope: str
    age_group: str | None
    sex: str | None
    period_start: datetime | None
    period_end: datetime | None
    sample_size: float | None
    methodology: str | None
    publisher_entity_id: str | None
    source_document_id: str | None


class EpidemiologyObservationSearchItemRead(EpidemiologyObservationRead):
    disease_entity: EpidemiologyLinkedEntityRead
    publisher_entity: EpidemiologyLinkedEntityRead | None
    patient_population: PatientPopulationRead | None


class EpidemiologyLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class EpidemiologyLandscapeRead(BaseModel):
    """Full-hit-set epidemiology statistics; missing values are explicit buckets."""

    total_observations: int = Field(ge=0)
    measure: list[EpidemiologyLandscapeBucketRead] = Field(default_factory=list)
    geography: list[EpidemiologyLandscapeBucketRead] = Field(default_factory=list)
    population_scope: list[EpidemiologyLandscapeBucketRead] = Field(default_factory=list)


class EpidemiologyObservationSearchResult(QueryResultMetadata):
    items: list[EpidemiologyObservationSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: EpidemiologySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: EpidemiologyLandscapeRead
    patient_populations: list[PatientPopulationOptionRead]
    as_of: datetime
    warnings: list[str]


class EpidemiologyTrendResult(BaseModel):
    disease: EpidemiologyLinkedEntityRead
    anchor_observation_id: str | None = None
    items: list[EpidemiologyObservationSearchItemRead]
    total: int
    truncated: bool
    as_of: datetime
    warnings: list[str]
