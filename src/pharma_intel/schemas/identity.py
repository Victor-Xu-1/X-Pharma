from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.identity import normalize_name
from pharma_intel.models.enums import (
    EntityType,
    ReviewStatus,
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
    ENTITY_SORT_FIELDS,
    EntitySortField,
    SortToken,
)


class EntityCreate(BaseModel):
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list, max_length=100)
    external_ids: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityIdentifierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    namespace: str
    value: str
    normalized_value: str
    trusted_namespace: bool
    review_status: ReviewStatus
    source_document_id: str | None


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: EntityType
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None
    external_ids: dict[str, str]
    attributes: dict[str, Any]
    review_status: ReviewStatus
    canonical_entity_id: str
    identity_identifiers: list[EntityIdentifierRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("aliases", mode="before")
    @classmethod
    def read_alias_names(cls, values: Any) -> list[str]:
        names: dict[str, str] = {}
        for item in values:
            alias = getattr(item, "alias", item)
            if not isinstance(alias, str):
                raise ValueError("Entity aliases must be text")
            normalized = normalize_name(alias)
            if normalized:
                names.setdefault(normalized, alias.strip())
        return [names[key] for key in sorted(names)]


class EntitySearchMatchRead(BaseModel):
    match_type: Literal["canonical_name", "alias", "external_id", "description", "semantic", "relationship"]
    match_relation: Literal["exact", "partial", "semantic", "related"]
    matched_value: str | None = None
    namespace: str | None = None
    via_entity_id: str | None = None
    predicate: str | None = None
    source_uri: str | None = None


class EntitySearchItemRead(EntityRead):
    aliases: list[str] = Field(default_factory=list, max_length=20)
    match: EntitySearchMatchRead | None = None


class EntityResolutionCaseRead(BaseModel):
    id: str
    source_entity_id: str
    source_entity_name: str
    candidate_entity_id: str
    candidate_entity_name: str
    entity_type: EntityType
    score: float
    risk_tier: Literal["low", "medium", "high"]
    reasons: list[dict[str, Any]]
    status: Literal["pending", "approved", "rejected", "reverted"]
    proposed_by: str
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime


class EntityResolutionDecisionRequest(BaseModel):
    action: Literal["approve", "reject", "revert"]
    expected_status: Literal["pending", "approved", "rejected", "reverted"]
    canonical_entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    notes: str | None = Field(default=None, max_length=4000)


class EntityReferenceImpactRead(BaseModel):
    domain: str
    table: str
    column: str
    source_count: int
    candidate_count: int


class EntityResolutionDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    action: str
    decided_by_user_id: str
    notes: str | None
    snapshot: dict[str, Any]
    created_at: datetime


class EntityResolutionImpactRead(BaseModel):
    case: EntityResolutionCaseRead
    source_reference_count: int
    candidate_reference_count: int
    source_trusted_identifier_count: int
    candidate_trusted_identifier_count: int
    recommended_canonical_entity_id: str
    recommendation_reasons: list[str]
    active_alias_entity_id: str | None
    active_canonical_entity_id: str | None
    rollback_available: bool
    references: list[EntityReferenceImpactRead]
    decisions: list[EntityResolutionDecisionRead]


class OntologyTermUpsert(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    ontology_name: str = Field(min_length=1, max_length=100)
    ontology_version: str = Field(min_length=1, max_length=100)
    term_id: str = Field(min_length=1, max_length=200)
    entity_type: EntityType
    preferred_label: str = Field(min_length=1, max_length=500)
    definition: str | None = None
    synonyms: list[str] = Field(default_factory=list, max_length=500)
    parent_term_ids: list[str] = Field(default_factory=list, max_length=100)
    source_uri: str | None = Field(default=None, max_length=2000)


class OntologyTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ontology_name: str
    ontology_version: str
    term_id: str
    entity_type: EntityType
    preferred_label: str
    definition: str | None
    synonyms: list[str]
    parent_term_ids: list[str]
    source_uri: str | None
    content_sha256: str
    active: bool
    created_at: datetime
    updated_at: datetime


class EntityOntologyMappingCreate(BaseModel):
    ontology_term_id: str = Field(min_length=36, max_length=36)
    mapping_type: Literal["exact", "broad", "narrow", "related"]
    confidence: float = Field(ge=0, le=1)
    source_document_id: str | None = Field(default=None, min_length=36, max_length=36)
    evidence: dict[str, Any] = Field(default_factory=dict)


class SearchResult(QueryResultMetadata):
    items: list[EntitySearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: EntitySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)
    engine: str = "database"
    took_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)


class EntitySearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    entity_type: EntityType | None = None
    entity_types: list[EntityType] = Field(default_factory=list, max_length=10)
    review_status: ReviewStatus | None = None
    include_related: bool = False
    # Presentation state is versioned with the saved query so replay returns the same research view.
    # Defaults are omitted from persisted JSON to keep legacy entity-search records compact.
    display_mode: Literal["list", "landscape"] = Field(default="list", exclude_if=lambda value: value == "list")
    analysis_view: Literal["chart", "table"] = Field(default="chart", exclude_if=lambda value: value == "chart")
    # Presentation-stable server sorting for replay; defaults keep legacy saved JSON valid.
    sort_by: EntitySortField = "relevance"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )

    @model_validator(mode="after")
    def require_filter(self) -> EntitySearchQuery:
        _synchronize_saved_sort(self, ENTITY_SORT_FIELDS)
        self.entity_types = list(dict.fromkeys(self.entity_types))
        if self.entity_type is not None and self.entity_types and self.entity_type not in self.entity_types:
            raise ValueError("entity_type must be included in entity_types when both are provided")
        if self.q is None and self.entity_type is None and not self.entity_types and self.review_status is None:
            raise ValueError("At least one entity search filter is required")
        return self


class AgentEntitySearchResult(QueryResultMetadata):
    items: list[EntitySearchItemRead]
    limit: int
    page_depth: int
    next_cursor: str | None
    sort_by: EntitySortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    engine: str = "database"
    facets: dict[str, dict[str, int]] = Field(default_factory=dict)


class EntitySuggestionResult(BaseModel):
    suggestions: list[str]
    engine: str
