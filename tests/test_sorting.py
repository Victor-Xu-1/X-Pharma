from __future__ import annotations

import pytest

from pharma_intel.sorting import (
    SortClause,
    SortValidationError,
    parse_sort_tokens,
    resolve_sort_clauses,
)

ALLOWED = ("name", "updated_at", "status")


def test_parse_sort_tokens_preserves_priority_and_direction() -> None:
    clauses = parse_sort_tokens(["status:desc", "name:asc", "updated_at:desc"], ALLOWED)

    assert clauses == (
        SortClause("status", "desc"),
        SortClause("name", "asc"),
        SortClause("updated_at", "desc"),
    )


@pytest.mark.parametrize(
    ("tokens", "message"),
    [
        (["name"], "field:asc"),
        (["name:ascending"], "field:asc"),
        (["unknown:asc"], "Unsupported sort field"),
        (["name:asc", "name:desc"], "must be unique"),
        (["name:asc", "status:asc", "updated_at:asc", "a:asc", "b:asc", "c:asc"], "At most 5"),
    ],
)
def test_parse_sort_tokens_fails_closed(tokens: list[str], message: str) -> None:
    with pytest.raises(SortValidationError, match=message):
        parse_sort_tokens(tokens, ALLOWED)


def test_resolve_sort_clauses_keeps_legacy_defaults_and_rejects_conflicts() -> None:
    assert resolve_sort_clauses(
        None,
        ALLOWED,
        default_field="updated_at",
        default_direction="desc",
    ) == (SortClause("updated_at", "desc"),)

    assert resolve_sort_clauses(
        ["name:asc", "status:desc"],
        ALLOWED,
        default_field="updated_at",
        default_direction="desc",
        legacy_field="name",
        legacy_direction="asc",
    ) == (SortClause("name", "asc"), SortClause("status", "desc"))

    with pytest.raises(SortValidationError, match="sort_by must match"):
        resolve_sort_clauses(
            ["name:asc"],
            ALLOWED,
            default_field="updated_at",
            default_direction="desc",
            legacy_field="status",
        )
