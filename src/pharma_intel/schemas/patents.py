from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pharma_intel.models.enums import (
    EntityType,
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
    PATENT_SORT_FIELDS,
    PatentSortField,
    SortToken,
)


class PatentSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    applicant: str | None = Field(default=None, min_length=1, max_length=300)
    legal_status: str | None = Field(default=None, min_length=1, max_length=120)
    priority_from: date | None = None
    priority_to: date | None = None
    expiration_from: date | None = None
    expiration_to: date | None = None
    sort_by: Literal["priority_date", "family_identifier", "legal_status", "expiration_date"] = "priority_date"
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
    def validate_patent_query(self) -> PatentSavedSearchQuery:
        _synchronize_saved_sort(self, PATENT_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.entity_id,
            self.applicant,
            self.legal_status,
            self.priority_from,
            self.priority_to,
            self.expiration_from,
            self.expiration_to,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one patent search filter is required")
        for start, end, label in (
            (self.priority_from, self.priority_to, "priority"),
            (self.expiration_from, self.expiration_to, "expiration"),
        ):
            if start and end and start > end:
                raise ValueError(f"{label}_from must not be after {label}_to")
        return self


class PatentPublicationRead(BaseModel):
    publication_number: str
    application_number: str | None = None
    jurisdiction: str | None = None
    publication_date: datetime | None = None
    grant_date: datetime | None = None


class PatentLegalEventRead(BaseModel):
    event_type: str
    status: str | None = None
    occurred_at: datetime
    jurisdiction: str | None = None
    publication_number: str | None = None
    description: str | None = None
    source_document_id: str | None = None


class PatentClaimRead(BaseModel):
    claim_number: str
    claim_type: Literal["composition", "method", "use", "formulation", "sequence", "other"]
    summary: str
    scope: str | None = None
    source_document_id: str | None = None


class PatentFamilyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_id: str
    family_identifier: str
    title: str
    priority_date: datetime | None
    applicants: list[str]
    inventors: list[str]
    publications: list[PatentPublicationRead]
    legal_status: str | None
    legal_status_at: datetime | None
    legal_events: list[PatentLegalEventRead] = Field(default_factory=list)
    independent_claims: list[PatentClaimRead] = Field(default_factory=list)
    expiration_date: datetime | None
    linked_entity_ids: list[str]
    source_document_id: str | None


class PatentFamilyLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class PatentFamilySearchItemRead(PatentFamilyRead):
    linked_entities: list[PatentFamilyLinkedEntityRead]


class PatentLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class PatentLandscapeRead(BaseModel):
    """Full-hit-set patent statistics computed by the database for the applied query.

    Buckets always cover the complete authorized result set, never the current page;
    missing values are reported as explicit `__missing__` buckets instead of being
    silently dropped.
    """

    total_families: int = Field(ge=0)
    legal_status: list[PatentLandscapeBucketRead] = Field(default_factory=list)
    top_applicants: list[PatentLandscapeBucketRead] = Field(default_factory=list)
    priority_year: list[PatentLandscapeBucketRead] = Field(default_factory=list)


class PatentFamilySearchResult(QueryResultMetadata):
    items: list[PatentFamilySearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: PatentSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: PatentLandscapeRead
    as_of: datetime
    warnings: list[str]
