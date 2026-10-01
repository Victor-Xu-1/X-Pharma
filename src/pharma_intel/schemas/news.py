from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

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
    NEWS_SORT_FIELDS,
    NewsSortField,
    SortToken,
)


class NewsSavedSearchQuery(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    q: str | None = Field(default=None, min_length=1, max_length=500)
    entity_id: str | None = Field(default=None, min_length=36, max_length=36)
    event_type: (
        Literal[
            "news",
            "press_release",
            "corporate_announcement",
            "publication",
            "conference_abstract",
            "poster",
            "presentation",
            "other",
        ]
        | None
    ) = None
    publisher: str | None = Field(default=None, min_length=1, max_length=500)
    language: str | None = Field(default=None, min_length=1, max_length=32)
    venue: str | None = Field(default=None, min_length=1, max_length=240)
    published_from: date | None = None
    published_to: date | None = None
    content_scope: Literal["research"] | None = None
    display_mode: Literal["list", "timeline", "landscape"] = "list"
    analysis_view: Literal["chart", "table"] = "chart"
    sort_by: Literal["published_at", "title", "event_type", "publisher", "venue"] = "published_at"
    sort_direction: SortDirection = "desc"
    sort: list[SortToken] = Field(
        default_factory=list,
        max_length=MAX_SORT_CRITERIA,
        exclude_if=lambda value: not value,
    )

    @model_validator(mode="after")
    def validate_news_query(self) -> NewsSavedSearchQuery:
        _synchronize_saved_sort(self, NEWS_SORT_FIELDS)
        filter_fields = (
            self.q,
            self.entity_id,
            self.event_type,
            self.publisher,
            self.language,
            self.venue,
            self.published_from,
            self.published_to,
            self.content_scope,
        )
        if not any(value is not None for value in filter_fields):
            raise ValueError("At least one news search filter is required")
        if self.published_from and self.published_to and self.published_from > self.published_to:
            raise ValueError("published_from must not be after published_to")
        if self.display_mode == "timeline" and self.content_scope != "research":
            raise ValueError("timeline display requires research content_scope")
        if self.content_scope == "research" and self.event_type not in {
            None,
            "publication",
            "conference_abstract",
            "poster",
            "presentation",
        }:
            raise ValueError("research content_scope requires a research event_type")
        return self


class NewsEventLinkedEntityRead(BaseModel):
    id: str
    name: str
    entity_type: EntityType


class NewsEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    event_identifier: str
    event_type: str
    title: str
    summary: str | None
    published_at: datetime | None
    language: str | None
    publisher_entity_id: str | None
    related_entity_ids: list[str]
    canonical_url: str | None
    venue: str | None
    details: dict[str, Any]
    source_document_id: str | None


class NewsEventSearchItemRead(NewsEventRead):
    publisher_entity: NewsEventLinkedEntityRead | None
    related_entities: list[NewsEventLinkedEntityRead]


class NewsLandscapeBucketRead(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    label: str = Field(min_length=1, max_length=500)
    count: int = Field(ge=0)
    share: float = Field(ge=0, le=1)


class NewsLandscapeRead(BaseModel):
    """Full-hit-set news statistics; missing values are explicit buckets."""

    total_events: int = Field(ge=0)
    event_type: list[NewsLandscapeBucketRead] = Field(default_factory=list)
    venue: list[NewsLandscapeBucketRead] = Field(default_factory=list)
    published_year: list[NewsLandscapeBucketRead] = Field(default_factory=list)


class NewsEventSearchResult(QueryResultMetadata):
    items: list[NewsEventSearchItemRead]
    total: int
    limit: int
    offset: int
    sort_by: NewsSortField
    sort_direction: SortDirection
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
    facets: dict[str, dict[str, int]]
    landscape: NewsLandscapeRead
    as_of: datetime
    warnings: list[str]
