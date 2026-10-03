from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from pharma_intel.sorting import (
    MAX_SORT_CRITERIA,
    parse_sort_tokens,
)
from pharma_intel.sorting import (
    SortDirection as SortDirection,
)


class SortCriterionRead(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    direction: SortDirection


def _synchronize_saved_sort(model: Any, allowed_fields: tuple[str, ...]) -> None:
    clauses = parse_sort_tokens(model.sort, allowed_fields)
    if not clauses:
        return
    primary = clauses[0]
    fields_set = model.model_fields_set
    if "sort_by" in fields_set and model.sort_by != primary.field:
        raise ValueError("sort_by must match the first sort criterion")
    if "sort_direction" in fields_set and model.sort_direction != primary.direction:
        raise ValueError("sort_direction must match the first sort criterion")
    model.sort_by = primary.field
    model.sort_direction = primary.direction


class AppliedFilterRead(BaseModel):
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    operator: Literal["contains", "eq", "in", "gte", "lte"]
    value: str | bool | int | float | list[str]


class QueryResultMetadata(BaseModel):
    query_schema_version: str = Field(pattern=r"^pharma\.[a-z][a-z0-9_.-]+\.v[1-9][0-9]*$")
    applied_filters: list[AppliedFilterRead] = Field(default_factory=list)


class AgentPageResult[PageItem](BaseModel):
    items: list[PageItem]
    limit: int
    page_depth: int
    next_cursor: str | None
    sort: list[SortCriterionRead] = Field(default_factory=list, max_length=MAX_SORT_CRITERIA)
