from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from pharma_intel.models.enums import (
    KnowledgePageStatus,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class KnowledgePageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    page_key: str
    page_type: str
    title: str
    subject_entity_id: str | None
    status: KnowledgePageStatus
    current_version_id: str | None
    updated_at: datetime


class KnowledgePageDetail(KnowledgePageSummary):
    version_number: int
    compiler_version: str
    content_json: dict[str, Any]
    rendered_markdown: str
    content_sha256: str
    source_snapshot_at: datetime


class PublicKnowledgePageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    page_type: str
    title: str
    updated_at: datetime


class PublicKnowledgePageSearchResult(BaseModel):
    query_schema_version: Literal["pharma.knowledge.search.v1"] = "pharma.knowledge.search.v1"
    items: list[PublicKnowledgePageSummary]
    total: int
    limit: int
    offset: int
    sort_by: Literal["title", "updated_at"]
    sort_direction: SortDirection
    facets: dict[str, dict[str, int]]
    as_of: datetime


class PublicKnowledgePageDetail(PublicKnowledgePageSummary):
    version_number: int
    rendered_markdown: str
    source_snapshot_at: datetime


class KnowledgePredicateCoverageRead(BaseModel):
    predicate: str
    fact_count: int
    cited_fact_count: int


class KnowledgePageCoverageRead(BaseModel):
    page_id: str
    version_id: str
    version_number: int
    fact_count: int
    cited_fact_count: int
    uncited_fact_count: int
    source_count: int
    linked_entity_count: int
    predicates: list[KnowledgePredicateCoverageRead]
    source_snapshot_at: datetime


class PublicKnowledgePageCoverageRead(BaseModel):
    version_number: int
    fact_count: int
    cited_fact_count: int
    uncited_fact_count: int
    source_count: int
    linked_entity_count: int
    predicates: list[KnowledgePredicateCoverageRead]
    source_snapshot_at: datetime


class KnowledgeVersionSummaryRead(BaseModel):
    version_id: str
    version_number: int
    compiler_version: str
    content_sha256: str
    source_snapshot_at: datetime
    created_at: datetime
    created_by_run_id: str | None
    is_current: bool
    previous_version_number: int | None
    fact_count: int
    source_count: int
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int


class PublicKnowledgeVersionSummaryRead(BaseModel):
    version_number: int
    source_snapshot_at: datetime
    is_current: bool
    previous_version_number: int | None
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int


class KnowledgeFactChangeRead(BaseModel):
    change_key: str
    fact_id: str | None
    predicate: str
    object_entity_name: str | None
    value: Any
    confidence: float | None
    citation_number: int | None
    source_document_id: str | None
    source_title: str | None
    source_locator: str | None


class KnowledgeSourceChangeRead(BaseModel):
    source_document_id: str
    title: str
    source_uri: str | None
    locator: str | None


class PublicKnowledgeFactChangeRead(BaseModel):
    change_key: str
    predicate: str
    object_entity_name: str | None
    value: Any
    source_title: str | None
    source_locator: str | None


class PublicKnowledgeSourceChangeRead(BaseModel):
    title: str
    locator: str | None


class KnowledgeVersionDiffRead(BaseModel):
    page_id: str
    from_version_number: int | None
    to_version_number: int
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int
    added_facts: list[KnowledgeFactChangeRead]
    removed_facts: list[KnowledgeFactChangeRead]
    added_sources: list[KnowledgeSourceChangeRead]
    removed_sources: list[KnowledgeSourceChangeRead]
    truncated: bool


class PublicKnowledgeVersionDiffRead(BaseModel):
    from_version_number: int | None
    to_version_number: int
    added_fact_count: int
    removed_fact_count: int
    added_source_count: int
    removed_source_count: int
    added_facts: list[PublicKnowledgeFactChangeRead]
    removed_facts: list[PublicKnowledgeFactChangeRead]
    added_sources: list[PublicKnowledgeSourceChangeRead]
    removed_sources: list[PublicKnowledgeSourceChangeRead]
    truncated: bool
