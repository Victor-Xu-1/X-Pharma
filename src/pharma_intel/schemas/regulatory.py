from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pharma_intel.models.enums import (
    EntityType,
    RegulatoryDesignationType,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
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
    REGULATORY_SORT_FIELDS,
    RegulatorySortField,
    SortToken,
)


class RegulatorySavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    agency: str | None = Field(default=None, min_length=1, max_length=80)
    jurisdiction: str | None = Field(default=None, min_length=1, max_length=120)
    event_type: str | None = Field(default=None, min_length=1, max_length=40)
    status: str | None = Field(default=None, min_length=1, max_length=120)
    designation_type: RegulatoryDesignationType | None = None
    label_change_type: RegulatoryLabelChangeType | None = None
    has_boxed_warning: bool | None = None
    safety_signal_type: RegulatorySafetySignalType | None = None
    safety_severity: RegulatorySafetySeverity | None = None
    safety_status: RegulatorySafetyStatus | None = None
    decision_from: date | None = None
    decision_to: date | None = None
    source_updated_from: date | None = None
    source_updated_to: date | None = None
    sort_by: Literal[
        "decision_date",
        "title",
        "agency",
        "jurisdiction",
        "event_type",
        "status",
        "subject",
        "source_updated_at",
    ] = "decision_date"
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
    def validate_regulatory_query(self) -> RegulatorySavedSearchQuery:
        _synchronize_saved_sort(self, REGULATORY_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.agency,
            self.jurisdiction,
            self.event_type,
            self.status,
            self.designation_type,
            self.label_change_type,
            self.has_boxed_warning,
            self.safety_signal_type,
            self.safety_severity,
            self.safety_status,
            self.decision_from,
            self.decision_to,
            self.source_updated_from,
            self.source_updated_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one regulatory search filter is required")
        for start, end, label in (
            (self.decision_from, self.decision_to, "decision"),
            (self.source_updated_from, self.source_updated_to, "source_updated"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        return self


class RegulatoryEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject_entity_id: str
    agency: str
    jurisdiction: str
    event_identifier: str
    application_number: str | None
    event_type: str
    status: str | None
    title: str
    decision_date: datetime | None
    designation_type: RegulatoryDesignationType | None
    label_change_type: RegulatoryLabelChangeType | None
    label_version: str | None
    label_effective_at: datetime | None
    approved_population: str | None
    line_of_therapy: str | None
    biomarker: str | None
    route_of_administration: str | None
    dosage_form: str | None
    has_boxed_warning: bool | None
    safety_signal_type: RegulatorySafetySignalType | None
    safety_term: str | None
    safety_severity: RegulatorySafetySeverity | None
    safety_status: RegulatorySafetyStatus | None
    safety_identified_at: datetime | None
    safety_confirmed_at: datetime | None
    safety_resolved_at: datetime | None
    affected_population: str | None
    risk_actions: list[str]
    source_updated_at: datetime | None
    indication_entity_id: str | None
    organization_entity_id: str | None
    details: dict[str, Any]
    source_document_id: str | None


class RegulatoryEventLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class RegulatoryEventSearchItemRead(RegulatoryEventRead):
    subject_entity: RegulatoryEventLinkedEntityRead
    indication_entity: RegulatoryEventLinkedEntityRead | None
    organization_entity: RegulatoryEventLinkedEntityRead | None


class RegulatoryLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class RegulatoryLandscapeRead(BaseModel):
    """Full-hit-set regulatory statistics for the applied query; missing values are
    explicit `__missing__` buckets and counts never come from the current page."""

    total_events: int = Field(ge=0)
    event_type: list[RegulatoryLandscapeBucketRead] = Field(default_factory=list)
    agency: list[RegulatoryLandscapeBucketRead] = Field(default_factory=list)
    decision_year: list[RegulatoryLandscapeBucketRead] = Field(default_factory=list)


class RegulatoryEventSearchResult(QueryResultMetadata):
    items: list[RegulatoryEventSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: RegulatorySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: RegulatoryLandscapeRead
    as_of: datetime
    warnings: list[str]
