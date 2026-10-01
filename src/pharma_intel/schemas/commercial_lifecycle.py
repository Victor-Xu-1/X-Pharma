from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class DataExportCreate(BaseModel):
    dataset: Literal[
        "entities",
        "structures",
        "bioactivities",
        "competitive_programs",
        "clinical_trials",
        "patents",
        "deals",
        "regulatory_events",
        "fact_provenance",
    ]
    export_format: Literal["jsonl", "csv"] = "jsonl"
    filters: dict[str, Any] = Field(default_factory=dict)
    fields: list[str] = Field(default_factory=list, max_length=50)
    max_records: int = Field(default=1000, ge=1, le=5000)
    max_billable_units: Decimal = Field(gt=0, max_digits=28, decimal_places=8)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")


class DataExportRead(BaseModel):
    id: str
    dataset: str
    format: str
    fields: list[str]
    filters: dict[str, Any]
    max_records: int
    license_policy_version: str
    license_policy_sha256: str
    license_attribution: str
    record_count: int
    state: str
    approval_required: bool
    approved_by: str | None
    approved_at: datetime | None
    artifact_bytes: int
    artifact_sha256: str | None
    manifest_sha256: str | None
    manifest_signature: str | None
    manifest_key_id: str | None
    failure_code: str | None
    failure_message: str | None
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    expires_at: datetime | None


class DataExportChunkRead(BaseModel):
    items: list[dict[str, Any]]
    count: int
    next_cursor: str | None
    manifest: dict[str, Any]


class DataRetentionPolicyUpdate(BaseModel):
    retention_seconds: int = Field(ge=300, le=315_360_000)
    legal_basis: str = Field(min_length=3, max_length=500)
    geographic_scope: list[str] = Field(default_factory=list, max_length=50)
    active: bool = True


class DataRetentionPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_class: Literal["commercial_export_artifact", "source_asset_snapshot"]
    policy_version: int
    retention_seconds: int
    legal_basis: str
    geographic_scope: list[str]
    active: bool
    configured_by_user_id: str
    created_at: datetime
    updated_at: datetime


class LegalHoldCreate(BaseModel):
    scope_type: Literal["tenant", "billing_account", "data_export_job", "data_source", "source_asset"]
    scope_id: str | None = Field(default=None, max_length=36)
    matter_reference: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=3, max_length=2000)


class LegalHoldRelease(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class LegalHoldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scope_type: str
    scope_id: str | None
    matter_reference: str
    reason: str
    status: Literal["active", "released"]
    placed_by_user_id: str
    placed_at: datetime
    released_by_user_id: str | None
    released_at: datetime | None
    release_reason: str | None


class DataLifecyclePurgeRequest(BaseModel):
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
    reason: str = Field(min_length=3, max_length=2000)


class DataLifecycleEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_class: str
    target_type: str
    target_id: str
    action: Literal["purge", "blocked", "reauthorize"]
    outcome: Literal["succeeded", "blocked"]
    idempotency_key: str
    policy_id: str
    policy_version: int
    legal_hold_ids: list[str]
    actor_user_id: str
    reason: str
    details: dict[str, Any]
    created_at: datetime


class DataLifecyclePurgeRead(BaseModel):
    event: DataLifecycleEventRead
    replayed: bool


class SourceAssetImpactRead(BaseModel):
    id: str
    data_source_id: str
    logical_path: str
    file_name: str
    state: str
    missing_since: datetime | None
    retention_eligible: bool
    version_count: int
    raw_object_count: int
    extracted_object_count: int
    extraction_run_count: int
    staged_fact_count: int
    published_fact_count: int
    evidence_claim_count: int
    knowledge_citation_count: int
    retrieval_projection_count: int
    shared_document_count: int
    other_document_reference_count: int
    blockers: list[str]


class DeletedSourceAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    data_source_id: str
    logical_path: str
    file_name: str
    state: Literal["deleted"]
    updated_at: datetime
