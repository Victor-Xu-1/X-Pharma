from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .identity import (
    EntityRead,
)


class RecentEntityVisitRead(BaseModel):
    entity: EntityRead
    visited_at: datetime


WorkspaceTablePreferenceKey = Literal[
    "clinical-trials",
    "deals",
    "entity-search",
    "epidemiology",
    "news-events",
    "patent-families",
    "pipeline",
    "regulatory-events",
]


WorkspaceTableDensity = Literal["comfortable", "compact"]


_WORKSPACE_COLUMN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")


class WorkspaceTablePreferenceUpdate(BaseModel):
    schema_version: Literal[1] = 1
    expected_version: int = Field(ge=0)
    column_visibility: dict[str, bool] = Field(default_factory=dict, max_length=64)
    column_order: list[str] = Field(default_factory=list, max_length=64)
    density: WorkspaceTableDensity = "comfortable"

    @field_validator("column_visibility")
    @classmethod
    def validate_column_visibility(cls, value: dict[str, bool]) -> dict[str, bool]:
        if any(_WORKSPACE_COLUMN_ID_PATTERN.fullmatch(column_id) is None for column_id in value):
            raise ValueError("Column visibility contains an invalid column ID")
        return value

    @field_validator("column_order")
    @classmethod
    def validate_column_order(cls, value: list[str]) -> list[str]:
        if any(_WORKSPACE_COLUMN_ID_PATTERN.fullmatch(column_id) is None for column_id in value):
            raise ValueError("Column order contains an invalid column ID")
        if len(value) != len(set(value)):
            raise ValueError("Column order IDs must be unique")
        return value


class WorkspaceTablePreferenceRead(BaseModel):
    preference_key: WorkspaceTablePreferenceKey
    schema_version: Literal[1] = 1
    column_visibility: dict[str, bool] = Field(default_factory=dict)
    column_order: list[str] = Field(default_factory=list)
    density: WorkspaceTableDensity = "comfortable"
    version: int = Field(ge=0)
    persisted: bool
    updated_at: datetime | None = None


WebVitalMetricName = Literal["CLS", "INP", "LCP", "TTFB"]


WebVitalRating = Literal["good", "needs-improvement", "poor"]


WebVitalNavigationType = Literal[
    "navigate",
    "reload",
    "back-forward",
    "back-forward-cache",
    "prerender",
    "restore",
    "soft-navigation",
]


WebVitalViewportClass = Literal["desktop", "tablet", "mobile"]


ResearchWebVitalRoute = Literal[
    "overview",
    "explorer",
    "chemistry",
    "pipeline",
    "trials",
    "patents",
    "deals",
    "regulatory",
    "epidemiology",
    "news",
    "target",
    "drug",
    "company",
    "disease",
    "entity",
    "evidence",
    "knowledge",
    "monitoring",
    "collections",
    "unknown",
]


_WEB_VITAL_THRESHOLDS: dict[str, tuple[float, float]] = {
    "CLS": (0.1, 0.25),
    "INP": (200, 500),
    "LCP": (2500, 4000),
    "TTFB": (800, 1800),
}


class WebVitalSampleCreate(BaseModel):
    metric_name: WebVitalMetricName
    value: float = Field(ge=0, le=120_000, allow_inf_nan=False)
    rating: WebVitalRating
    route: ResearchWebVitalRoute
    navigation_type: WebVitalNavigationType
    navigation_sequence: int = Field(ge=0, le=10_000)
    viewport_class: WebVitalViewportClass

    @model_validator(mode="after")
    def validate_metric_integrity(self) -> WebVitalSampleCreate:
        if self.metric_name == "CLS" and self.value > 10:
            raise ValueError("CLS value exceeds the accepted telemetry boundary")
        good_threshold, poor_threshold = _WEB_VITAL_THRESHOLDS[self.metric_name]
        expected_rating: WebVitalRating
        if self.value <= good_threshold:
            expected_rating = "good"
        elif self.value <= poor_threshold:
            expected_rating = "needs-improvement"
        else:
            expected_rating = "poor"
        if self.rating != expected_rating:
            raise ValueError("Web Vital rating does not match the measured value")
        return self


class WebVitalBatchCreate(BaseModel):
    schema_version: Literal[1] = 1
    samples: list[WebVitalSampleCreate] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_unique_navigation_metrics(self) -> WebVitalBatchCreate:
        identities = [(sample.navigation_sequence, sample.metric_name) for sample in self.samples]
        if len(identities) != len(set(identities)):
            raise ValueError("Web Vital navigation metrics must be unique within a batch")
        return self


class WebVitalBatchAccepted(BaseModel):
    schema_version: Literal[1] = 1
    accepted_count: int = Field(ge=1, le=8)
