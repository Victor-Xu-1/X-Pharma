from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pharma_intel.models.enums import (
    SavedSearchVisibility,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)

from .identity import (
    EntityRead,
)


class ComparisonSetCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    visibility: SavedSearchVisibility = SavedSearchVisibility.PRIVATE


class ComparisonSetUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    visibility: SavedSearchVisibility | None = None

    @model_validator(mode="after")
    def require_change(self) -> ComparisonSetUpdate:
        if self.name is None and self.description is None and self.visibility is None:
            raise ValueError("At least one comparison set field must change")
        return self


class ComparisonSetMemberCreate(BaseModel):
    entity_id: str = Field(min_length=36, max_length=36)
    expected_version: int = Field(ge=1)


class ComparisonSetMembersAdd(BaseModel):
    entity_ids: list[str] = Field(min_length=1, max_length=20)
    expected_version: int = Field(ge=1)

    @field_validator("entity_ids")
    @classmethod
    def validate_entity_ids(cls, value: list[str]) -> list[str]:
        if any(len(entity_id) != 36 for entity_id in value):
            raise ValueError("Comparison set entity IDs must be UUID strings")
        if len(value) != len(set(value)):
            raise ValueError("Comparison set entity IDs must be unique")
        return value


class ComparisonSetMemberRemove(BaseModel):
    expected_version: int = Field(ge=1)


class ComparisonSetSummaryRead(BaseModel):
    id: str
    owner_user_id: str
    name: str
    description: str
    visibility: SavedSearchVisibility
    version: int
    member_count: int
    editable: bool
    created_at: datetime
    updated_at: datetime


class ComparisonSetMemberRead(BaseModel):
    id: str
    position: int
    added_by_user_id: str
    created_at: datetime
    entity: EntityRead


class ComparisonSetDetailRead(ComparisonSetSummaryRead):
    members: list[ComparisonSetMemberRead]


class ComparisonSetVersionRead(BaseModel):
    id: str
    version: int
    snapshot_json: dict[str, Any]
    changed_by_user_id: str
    created_at: datetime


class WorkspaceExportPolicyUpsert(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    policy_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$")
    enabled: bool
    allowed_formats: list[Literal["csv", "json", "xlsx"]] = Field(min_length=1, max_length=3)
    allowed_fields: list[str] = Field(min_length=1, max_length=500)
    max_records_per_export: int = Field(ge=1, le=100)
    attribution: str = Field(min_length=1, max_length=500)

    @field_validator("allowed_formats", "allowed_fields")
    @classmethod
    def unique_values(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Workspace export policy lists must not contain duplicates")
        return sorted(value)


class WorkspaceExportPolicyRead(BaseModel):
    id: str
    policy_version: str
    enabled: bool
    allowed_formats: list[str]
    allowed_fields: list[str]
    max_records_per_export: int
    attribution: str
    configured_by_user_id: str
    policy_sha256: str
    created_at: datetime
    updated_at: datetime


class WorkspaceExportCreate(BaseModel):
    expected_version: int = Field(ge=1)
    export_format: Literal["csv", "json", "xlsx"]
    fields: list[str] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

    @field_validator("fields")
    @classmethod
    def unique_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Workspace export fields must not contain duplicates")
        return value


WorkspaceDomainExportDataset = Literal[
    "entities",
    "pipelines",
    "trials",
    "patents",
    "deals",
    "regulatory",
    "epidemiology",
    "news",
]


class WorkspaceDomainExportCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    dataset: WorkspaceDomainExportDataset
    query: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict, max_length=50)
    export_format: Literal["csv", "json", "xlsx"]
    fields: list[str] = Field(min_length=1, max_length=100)
    max_records: int = Field(ge=1, le=100)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")

    @field_validator("fields")
    @classmethod
    def unique_domain_fields(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Workspace domain export fields must not contain duplicates")
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", field) for field in value):
            raise ValueError("Workspace domain export fields are invalid")
        return value

    @field_validator("query")
    @classmethod
    def validate_query_shape(
        cls,
        value: dict[str, str | int | float | bool | list[str]],
    ) -> dict[str, str | int | float | bool | list[str]]:
        reserved = {"limit", "offset", "view", "display"}
        if set(value) & reserved:
            raise ValueError("Workspace domain export query contains reserved pagination or presentation fields")
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", field) for field in value):
            raise ValueError("Workspace domain export query fields are invalid")
        if any(len(item) > 10 or len(item) != len(set(item)) for item in value.values() if isinstance(item, list)):
            raise ValueError("Workspace domain export query list values are invalid")
        return value
