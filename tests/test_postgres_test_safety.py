from __future__ import annotations

import pytest

from tests.support.postgres_safety import (
    UnsafeTestDatabaseError,
    require_disposable_postgres_url,
    require_same_database,
)


def test_disposable_database_guard_accepts_local_test_database() -> None:
    value = "postgresql+psycopg://tester:secret@127.0.0.1:5432/chemistry_test"

    assert require_disposable_postgres_url(value, "TEST_DATABASE_URL") == value


@pytest.mark.parametrize(
    "value",
    [
        "postgresql+psycopg://operator:secret@127.0.0.1:5432/pharma",
        "sqlite:///integration_test.db",
    ],
)
def test_disposable_database_guard_rejects_primary_or_non_postgres_database(value: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        require_disposable_postgres_url(value, "TEST_DATABASE_URL")


def test_remote_database_requires_exact_non_secret_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    value = "postgresql+psycopg://tester:secret@db.example.test:5432/pharma_integration"

    with pytest.raises(UnsafeTestDatabaseError, match="TEST_REMOTE_DATABASE_CONFIRMATION"):
        require_disposable_postgres_url(value, "TEST_DATABASE_URL")

    monkeypatch.setenv("TEST_REMOTE_DATABASE_CONFIRMATION", "db.example.test/pharma_integration")
    assert require_disposable_postgres_url(value, "TEST_DATABASE_URL") == value


def test_admin_and_runtime_urls_must_target_the_same_database() -> None:
    admin = "postgresql+psycopg://admin:secret@127.0.0.1:5432/chemistry_test"
    runtime = "postgresql+psycopg://runtime:secret@127.0.0.1:5432/other_test"

    with pytest.raises(UnsafeTestDatabaseError, match="same database"):
        require_same_database(admin, runtime, "ADMIN_URL", "RUNTIME_URL")
