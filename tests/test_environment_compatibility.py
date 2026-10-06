from __future__ import annotations

import pytest

from pharma_intel.platform.environment_compatibility import dependency_mismatches, pinned_dependencies, version_state


@pytest.mark.parametrize(
    ("observed", "expected", "state"),
    [
        ("Python 3.12.3", ">=3.13,<3.14", "mismatch"),
        ("3.13.14", ">=3.13,<3.14", "present"),
        ("3.13.14", "<3.14,>=3.13", "present"),
        ("v24.21.0", "24.x", "present"),
        ("v1.35.0", "==1.35.0", "present"),
        ("v26.0.0", "24.x", "mismatch"),
        ("uv 0.11.28", "==0.11.28", "present"),
        (None, "==0.11.28", "missing"),
        ("3.13.14", None, "unverified"),
        ("3.13.14", ">=3.13", "unverified"),
    ],
)
def test_version_presence_does_not_override_project_compatibility(
    observed: str | None,
    expected: str | None,
    state: str,
) -> None:
    assert version_state(observed, expected) == state


def test_dependency_pins_match_actual_project_distributions_and_do_not_ignore_absence() -> None:
    required = pinned_dependencies(
        ["SQLAlchemy==2.0.42", "psycopg[binary,pool]==3.3.6", "pywin32==312; sys_platform == 'win32'"]
    )
    assert required == {"sqlalchemy": "2.0.42", "psycopg": "3.3.6"}
    assert dependency_mismatches(required, {"SQLAlchemy": "2.0.42", "psycopg": "3.3.5"}) == ["psycopg"]
    assert dependency_mismatches(required, {}) == ["psycopg", "sqlalchemy"]
    with pytest.raises(ValueError, match="explicit pinned"):
        pinned_dependencies(["SQLAlchemy>=2"])
