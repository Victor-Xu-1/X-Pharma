from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal, cast

SortDirection = Literal["asc", "desc"]
MAX_SORT_CRITERIA = 5
SORT_TOKEN_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}:(?:asc|desc)$")


class SortValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SortClause[SortField: str]:
    field: SortField
    direction: SortDirection

    @property
    def token(self) -> str:
        return f"{self.field}:{self.direction}"


def parse_sort_tokens[SortField: str](
    tokens: Sequence[str] | None,
    allowed_fields: Collection[SortField],
) -> tuple[SortClause[SortField], ...]:
    if not tokens:
        return ()
    if len(tokens) > MAX_SORT_CRITERIA:
        raise SortValidationError(f"At most {MAX_SORT_CRITERIA} sort criteria are allowed")

    allowed = set(allowed_fields)
    clauses: list[SortClause[SortField]] = []
    seen: set[str] = set()
    for token in tokens:
        if not SORT_TOKEN_PATTERN.fullmatch(token):
            raise SortValidationError("Sort criteria must use field:asc or field:desc")
        raw_field, raw_direction = token.split(":", 1)
        if raw_field not in allowed:
            raise SortValidationError(f"Unsupported sort field: {raw_field}")
        if raw_field in seen:
            raise SortValidationError(f"Sort fields must be unique: {raw_field}")
        seen.add(raw_field)
        clauses.append(
            SortClause(
                field=cast(SortField, raw_field),
                direction=cast(SortDirection, raw_direction),
            )
        )
    return tuple(clauses)


def resolve_sort_clauses[SortField: str](
    tokens: Sequence[str] | None,
    allowed_fields: Collection[SortField],
    *,
    default_field: SortField,
    default_direction: SortDirection,
    legacy_field: SortField | None = None,
    legacy_direction: SortDirection | None = None,
) -> tuple[SortClause[SortField], ...]:
    clauses = parse_sort_tokens(tokens, allowed_fields)
    if clauses:
        primary = clauses[0]
        if legacy_field is not None and legacy_field != primary.field:
            raise SortValidationError("sort_by must match the first sort criterion")
        if legacy_direction is not None and legacy_direction != primary.direction:
            raise SortValidationError("sort_direction must match the first sort criterion")
        return clauses
    return (
        SortClause(
            field=legacy_field or default_field,
            direction=legacy_direction or default_direction,
        ),
    )


def validate_sort_clauses[SortField: str](
    clauses: Sequence[SortClause[SortField]] | None,
    allowed_fields: Collection[SortField],
    *,
    default_field: SortField,
    default_direction: SortDirection,
) -> tuple[SortClause[SortField], ...]:
    if not clauses:
        return (SortClause(default_field, default_direction),)
    return parse_sort_tokens([clause.token for clause in clauses], allowed_fields)


def sort_tokens(clauses: Sequence[SortClause[str]]) -> list[str]:
    return [clause.token for clause in clauses]
