from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pharma_intel.models.enums import (
    QuarantineStatus,
    SourceAssetState,
    SourceVersionState,
    StageStatus,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class SourceAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_source_id: str
    logical_path: str
    source_uri: str
    file_name: str
    extension: str
    media_type: str | None
    processing_mode: str
    state: SourceAssetState
    current_version_id: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    missing_since: datetime | None


class SourceVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_asset_id: str
    version_number: int
    content_sha256: str
    size_bytes: int
    source_modified_at: datetime | None
    discovered_at: datetime
    state: SourceVersionState
    snapshot_status: StageStatus
    malware_scan_status: StageStatus
    parse_status: StageStatus
    retrieval_status: StageStatus
    governance_status: StageStatus
    malware_scanner: str | None
    malware_signature_version: str | None
    malware_scanned_at: datetime | None
    extracted_text_sha256: str | None
    parser_name: str | None
    parser_version: str | None
    metadata_json: dict[str, Any]
    error_code: str | None
    error_message: str | None
    quarantine_status: QuarantineStatus
    quarantine_version: int = Field(ge=0)
    quarantine_updated_at: datetime | None
    replayable_stages: list[Literal["malware_scan", "parse", "governance", "retrieval"]] = Field(default_factory=list)


class SourceAssetDetailRead(SourceAssetRead):
    versions: list[SourceVersionRead]


class SourceAssetPageRead(BaseModel):
    items: list[SourceAssetRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class SourceVersionPreviewRead(BaseModel):
    source_version_id: str
    text: str
    truncated: bool
    returned_chars: int
    extracted_text_sha256: str


class SourceVersionReplayRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_state: SourceVersionState
    expected_error_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{2,119}$")
    from_stage: Literal["malware_scan", "parse", "governance", "retrieval"] = "malware_scan"
    reason: str = Field(min_length=3, max_length=500)


class SourceVersionReplayAcceptedRead(BaseModel):
    workflow_id: str
    source_version_id: str
    from_stage: Literal["malware_scan", "parse", "governance", "retrieval"]
    status: Literal["accepted"]


class SourceVersionQuarantineDecisionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    expected_version: int = Field(ge=1)
    action: Literal["hold", "reject", "rescan"]
    reason: str = Field(min_length=3, max_length=500)


class SourceVersionQuarantineDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_version_id: str
    action: str
    expected_version: int
    resulting_version: int
    previous_status: QuarantineStatus
    resulting_status: QuarantineStatus
    reason: str
    actor_type: str
    actor_id: str
    workflow_id: str | None
    details: dict[str, Any]
    created_at: datetime


class SourceVersionQuarantineCaseRead(BaseModel):
    source_version_id: str
    source_asset_id: str
    file_name: str
    logical_path: str
    quarantine_status: QuarantineStatus
    quarantine_version: int = Field(ge=1)
    threat_name: str | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime
    decisions: list[SourceVersionQuarantineDecisionRead] = Field(default_factory=list)


class SourceVersionQuarantineDecisionAcceptedRead(BaseModel):
    decision_id: str
    source_version_id: str
    action: Literal["hold", "reject", "rescan"]
    quarantine_status: QuarantineStatus
    quarantine_version: int = Field(ge=1)
    workflow_id: str | None
    status: Literal["accepted"]
