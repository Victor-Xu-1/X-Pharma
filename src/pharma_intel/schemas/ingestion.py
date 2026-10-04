from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pharma_intel.models.enums import (
    RunState,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class IngestionCapabilitiesRead(BaseModel):
    automatic_scheduling_enabled: bool
    durable_workflows_enabled: bool
    isolated_parser_enabled: bool
    malware_scanning_enabled: bool
    ai_governance_enabled: bool
    deterministic_governance_enabled: bool
    ai_model_configured: bool
    ai_model: str | None
    ai_auto_publish_threshold: float
    allowed_folder_roots: list[str]
    parseable_extensions: list[str]
    asset_only_extensions: list[str]


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_source_id: str
    workflow_id: str
    temporal_workflow_id: str | None
    temporal_run_id: str | None
    state: RunState
    effective_state: RunState
    started_at: datetime | None
    completed_at: datetime | None
    heartbeat_at: datetime | None
    counters: dict[str, int]
    result: dict[str, Any]
    error_summary: str | None
    cancel_requested_at: datetime | None
    cancelable: bool
    progress_percent: int = Field(ge=0, le=100)
    total_versions: int = Field(ge=0)
    completed_versions: int = Field(ge=0)
    stages: list[IngestionRunStageRead]
    created_at: datetime


class IngestionRunStageRead(BaseModel):
    stage: Literal["discovery", "snapshot", "malware_scan", "parse", "retrieval", "governance"]
    status: Literal["not_started", "running", "succeeded", "failed", "skipped", "canceled"]
    completed_items: int = Field(ge=0)
    failed_items: int = Field(ge=0)
    total_items: int = Field(ge=0)


class IngestionRunReplayRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_state: Literal[RunState.FAILED, RunState.PARTIAL, RunState.CANCELED]
    reason: str = Field(min_length=3, max_length=500)


class IngestionRunCancelRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_state: Literal[RunState.RUNNING]
    reason: str = Field(min_length=3, max_length=500)


class IngestionRunCancelAcceptedRead(BaseModel):
    run_id: str
    workflow_id: str
    temporal_workflow_id: str
    temporal_run_id: str
    status: Literal["cancel_requested"]


class IngestionScanAcceptedRead(BaseModel):
    workflow_id: str
    ingestion_run_id: str
    status: Literal["accepted"]
    replayed_from_run_id: str | None = None


class IngestionFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ingestion_run_id: str
    source_path: str
    stage: str
    code: str
    message: str
    retryable: bool
    occurred_at: datetime
