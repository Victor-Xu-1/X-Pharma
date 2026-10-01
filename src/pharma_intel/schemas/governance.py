from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pharma_intel.models.enums import (
    GovernanceStatus,
    RunState,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class PublicationBatchPreviewRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    operation: Literal["publish", "withdraw"]
    staged_fact_ids: list[str] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)
    reason: str | None = Field(default=None, max_length=4000)


class PublicationBatchCommitRequest(BaseModel):
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublicationBatchItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    staged_fact_id: str
    position: int
    expected_status: str
    outcome: str
    blockers: list[dict[str, Any]]
    snapshot: dict[str, Any]
    created_at: datetime


class PublicationBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    idempotency_key: str
    operation: Literal["publish", "withdraw"]
    status: Literal["previewed", "committed", "failed"]
    preview_sha256: str
    expected_count: int
    blocked_count: int
    reason: str | None
    requested_by_user_id: str
    committed_by_user_id: str | None
    committed_at: datetime | None
    result: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    items: list[PublicationBatchItemRead] = Field(default_factory=list)


class StagedFactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    fact_kind: str
    raw_payload: dict[str, Any]
    payload: dict[str, Any]
    normalization_version: str | None
    source_document_id: str | None
    source_locator: str | None
    source_quote: str
    confidence: float
    status: GovernanceStatus
    quality_findings: list[dict[str, Any]]
    conflict_with_ids: list[str]
    created_at: datetime


class GovernanceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_version_id: str
    source_asset_id: str
    source_logical_path: str
    source_file_name: str
    source_content_sha256: str
    schema_name: str
    schema_version: str
    model_provider: str
    model_name: str
    prompt_sha256: str
    policy_sha256: str
    input_sha256: str
    policy_current: bool
    status: RunState
    validation_errors: list[dict[str, Any]]
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost: Decimal | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class GovernanceRunPageRead(BaseModel):
    items: list[GovernanceRunRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    current_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    notes: str | None = Field(default=None, max_length=4000)
