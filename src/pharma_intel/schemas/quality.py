from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pharma_intel.models.enums import (
    UserRole,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class DataQualitySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trigger: Literal["scheduled", "manual"]
    definitions_version: str
    window_start: datetime
    window_end: datetime
    measured_at: datetime
    metrics: dict[str, dict[str, Any]]
    created_at: datetime


class DataQualityCoverageRead(BaseModel):
    source_id: str
    name: str
    source_type: str
    dataset_key: str
    owner: str
    state: str
    data_classification: str
    authorization_scopes: list[str]
    authorization_valid_until: datetime | None
    authorization_status: Literal["valid", "expiring", "expired", "missing_scope", "not_yet_valid"]
    asset_count: int
    active_asset_count: int
    parsed_asset_count: int
    parse_missing_count: int
    parse_coverage: float
    fact_count: int
    published_fact_count: int
    review_pending_fact_count: int
    conflict_fact_count: int
    rejected_fact_count: int
    published_fact_coverage: float
    conflict_rate: float
    window_start: datetime
    measured_at: datetime
    run_count: int
    successful_run_count: int
    failed_run_count: int
    ingestion_success_rate: float
    last_scanned_at: datetime | None
    last_success_at: datetime | None
    expected_freshness_seconds: int
    freshness_age_seconds: int | None
    freshness_status: Literal["fresh", "stale", "never_succeeded"]
    consecutive_failures: int
    failure_sla_age_seconds: int | None
    failure_sla_status: Literal["healthy", "at_risk", "breached"]
    last_error_present: bool


class DataQualityOwnerRead(BaseModel):
    id: str
    display_name: str
    role: UserRole


class DataQualityIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    metric_key: str
    scope_type: str
    scope_id: str | None
    status: Literal["open", "acknowledged", "ready_to_resolve", "resolved", "waived"]
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    description: str
    actual_value: float
    threshold_value: float
    comparison: Literal["gte", "lte"]
    owner_user_id: str | None
    owner_display_name: str | None = None
    sla_due_at: datetime
    detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    resolution_notes: str | None
    version: int
    last_snapshot_id: str
    created_at: datetime
    updated_at: datetime


class DataQualityIssueEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    action: str
    actor_type: str
    actor_id: str
    previous_status: str | None
    resulting_status: str
    details: dict[str, Any]
    occurred_at: datetime


class DataQualityIssueActionRequest(BaseModel):
    action: Literal["assign", "acknowledge", "resolve", "waive"]
    expected_version: int = Field(ge=1)
    owner_user_id: str | None = Field(default=None, max_length=36)
    notes: str | None = Field(default=None, max_length=4000)
