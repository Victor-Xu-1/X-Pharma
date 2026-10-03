from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from pharma_intel.models.enums import (
    EntityType,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .types import (
    ProvenanceResourceType,
)


class EvidenceSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    dataset_keys: list[str] = Field(default_factory=list, max_length=20)
    entity_types: list[EntityType] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


class EvidenceDatasetRead(BaseModel):
    dataset_key: str
    display_name: str
    attribution: str


class EvidenceChunk(BaseModel):
    content: str
    document_id: str
    document_name: str
    dataset_id: str
    similarity: float | None = Field(
        default=None,
        description="Retriever ranking score; it is not normalized and is not a probability.",
    )
    positions: list[Any] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceLicenseScope(BaseModel):
    dataset_key: str
    license_id: str
    policy_version: str
    attribution: str
    delivery_channel: Literal["web", "mcp"]
    allowed_fields: list[str]
    max_content_chars: int
    valid_from: datetime | None = None
    expires_at: datetime | None = None


class EvidenceSearchResponse(BaseModel):
    query: str
    chunks: list[EvidenceChunk]
    engine: str
    license_scopes: list[EvidenceLicenseScope]
    warnings: list[str] = Field(default_factory=list)


class AgentEvidenceSearchResult(EvidenceSearchResponse):
    limit: int
    page_depth: int
    next_cursor: str | None


class RecordProvenanceRead(BaseModel):
    id: str
    resource_type: ProvenanceResourceType
    resource_id: str
    dataset_key: str
    evidence_claim_id: str | None = None
    source_document_id: str | None = None
    source_version_id: str | None = None
    content_sha256: str | None = None
    document_name: str
    source_uri: str | None = None
    locator: str | None = None
    quote: str
    subject_entity_id: str | None = None
    review_status: str | None = None
    created_at: datetime
    license: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class RecordProvenanceResponse(BaseModel):
    resource_type: ProvenanceResourceType
    resource_id: str
    items: list[RecordProvenanceRead]
    license_scopes: list[EvidenceLicenseScope]
    warnings: list[str] = Field(default_factory=list)
