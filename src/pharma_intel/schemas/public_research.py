from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

PublicResearchTopic = Literal[
    "overview",
    "drugs",
    "targets",
    "trials",
    "organizations",
    "conditions",
    "patents",
    "compound_patents",
    "literature",
    "disclosures",
]


class PublicResearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    topic: PublicResearchTopic = "overview"
    q: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("q", mode="before")
    @classmethod
    def safe_query(cls, value: object) -> object:
        if isinstance(value, str) and any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Public research query must not contain control characters")
        return value


class PublicResearchRecord(BaseModel):
    record_id: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=1200)
    url: str = Field(min_length=1, max_length=2000)
    published_on: str | None = Field(default=None, max_length=40)
    fields: dict[str, str] = Field(default_factory=dict, max_length=12)

    @field_validator("url")
    @classmethod
    def safe_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port:
            raise ValueError("Public result URL must be an uncredentialed HTTPS URL")
        return value

    @field_validator("fields")
    @classmethod
    def bounded_fields(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 80 or len(item) > 600 for key, item in value.items()):
            raise ValueError("Public metadata field exceeds safety limit")
        return value


class PublicResearchSourceResult(BaseModel):
    topic: PublicResearchTopic
    provider: str
    status: Literal["available", "empty", "unavailable"]
    records: list[PublicResearchRecord] = Field(default_factory=list, max_length=20)
    total: int | None = Field(default=None, ge=0)
    source_query_url: str
    scope_note: str
    license_notice: str
    warnings: list[str] = Field(default_factory=list, max_length=10)
    error_code: Literal["upstream_unavailable", "invalid_response"] | None = None


class PublicResearchResponse(BaseModel):
    query: str
    observed_at: datetime
    results: list[PublicResearchSourceResult] = Field(max_length=5)
    persisted: Literal[False] = False


class PublicResearchCoverage(BaseModel):
    observed_at: datetime
    entity_counts: dict[str, int]
    public_source_names: list[str]
    scope_note: str
