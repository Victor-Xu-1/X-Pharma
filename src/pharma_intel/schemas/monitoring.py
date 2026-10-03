from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.models.enums import (
    SavedSearchVisibility,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .chemistry import (
    ChemistrySavedSearchQuery,
)
from .deals import (
    DealSavedSearchQuery,
)
from .epidemiology import (
    EpidemiologySavedSearchQuery,
)
from .identity import (
    EntitySearchQuery,
)
from .news import (
    NewsSavedSearchQuery,
)
from .patents import (
    PatentSavedSearchQuery,
)
from .programs import (
    PipelineSavedSearchQuery,
)
from .regulatory import (
    RegulatorySavedSearchQuery,
)
from .trials import (
    ClinicalTrialSavedSearchQuery,
)

SavedSearchQueryType = Literal[
    "entity_search",
    "chemistry_search",
    "pipeline_search",
    "clinical_trial_search",
    "patent_search",
    "deal_search",
    "regulatory_search",
    "epidemiology_search",
    "news_search",
]


SavedSearchQuery = (
    EntitySearchQuery
    | ChemistrySavedSearchQuery
    | PipelineSavedSearchQuery
    | ClinicalTrialSavedSearchQuery
    | PatentSavedSearchQuery
    | DealSavedSearchQuery
    | RegulatorySavedSearchQuery
    | EpidemiologySavedSearchQuery
    | NewsSavedSearchQuery
)


_SAVED_SEARCH_QUERY_MODELS: dict[str, type[BaseModel]] = {
    "entity_search": EntitySearchQuery,
    "chemistry_search": ChemistrySavedSearchQuery,
    "pipeline_search": PipelineSavedSearchQuery,
    "clinical_trial_search": ClinicalTrialSavedSearchQuery,
    "patent_search": PatentSavedSearchQuery,
    "deal_search": DealSavedSearchQuery,
    "regulatory_search": RegulatorySavedSearchQuery,
    "epidemiology_search": EpidemiologySavedSearchQuery,
    "news_search": NewsSavedSearchQuery,
}


def _saved_search_query_model(query_type: Any) -> type[BaseModel]:
    model = _SAVED_SEARCH_QUERY_MODELS.get(str(query_type or "entity_search"))
    if model is None:
        raise ValueError("Unsupported saved search query type")
    return model


class SavedSearchCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    query_type: SavedSearchQueryType = "entity_search"
    query: SavedSearchQuery
    visibility: SavedSearchVisibility = SavedSearchVisibility.PRIVATE

    @model_validator(mode="before")
    @classmethod
    def parse_typed_query(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not isinstance(value.get("query"), dict):
            return value
        parsed = dict(value)
        model = _saved_search_query_model(value.get("query_type", "entity_search"))
        parsed["query"] = model.model_validate(value["query"])
        return parsed


class SavedSearchUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    query_type: SavedSearchQueryType | None = None
    query: SavedSearchQuery | None = None
    visibility: SavedSearchVisibility | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_typed_query(cls, value: Any) -> Any:
        if not isinstance(value, dict) or not isinstance(value.get("query"), dict):
            return value
        parsed = dict(value)
        model = _saved_search_query_model(value.get("query_type", "entity_search"))
        parsed["query"] = model.model_validate(value["query"])
        return parsed

    @model_validator(mode="after")
    def require_change(self) -> SavedSearchUpdate:
        if all(value is None for value in (self.name, self.description, self.query, self.visibility)):
            raise ValueError("At least one saved search field must change")
        if self.query_type is not None and self.query is None:
            raise ValueError("query_type can only be supplied with query")
        return self


class SavedSearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_user_id: str
    name: str
    description: str
    query_type: SavedSearchQueryType
    query_version: int
    query_json: SavedSearchQuery
    visibility: SavedSearchVisibility
    created_at: datetime
    updated_at: datetime

    @field_validator("query_json", mode="before")
    @classmethod
    def parse_query_json(cls, value: Any, info: Any) -> SavedSearchQuery:
        model = _saved_search_query_model(info.data.get("query_type"))
        return cast(SavedSearchQuery, model.model_validate(value))


class MonitoringTopicCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    saved_search_id: str = Field(min_length=36, max_length=36)


class MonitoringTopicUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    active: bool | None = None
    query_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_change(self) -> MonitoringTopicUpdate:
        if self.name is None and self.active is None and self.query_version is None:
            raise ValueError("At least one monitoring topic field must change")
        return self


class MonitoringTopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_user_id: str
    saved_search_id: str
    query_version: int
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime


class MonitoringAlertRead(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    entity_id: str
    entity_name: str
    event_type: str
    title: str
    summary: str
    payload_json: dict[str, Any]
    occurred_at: datetime
    read_at: datetime | None
