from __future__ import annotations

import os
import re
import secrets

from sqlalchemy.engine import URL, make_url


class UnsafeTestDatabaseError(RuntimeError):
    pass


_DISPOSABLE_DATABASE_PATTERN = re.compile(r"(?:^|[-_])(ci|integration|migration|test|testing)(?:$|[-_])")
_LOCAL_DATABASE_HOSTS = frozenset({None, "", "127.0.0.1", "::1", "localhost", "postgres"})


def require_disposable_postgres_url(value: str, variable: str) -> str:
    try:
        parsed = make_url(value)
    except Exception as exc:
        raise UnsafeTestDatabaseError(f"{variable} is not a valid database URL") from exc
    if parsed.get_backend_name() != "postgresql":
        raise UnsafeTestDatabaseError(f"{variable} must use PostgreSQL")
    database = parsed.database or ""
    if not _DISPOSABLE_DATABASE_PATTERN.search(database.casefold()):
        raise UnsafeTestDatabaseError(
            f"{variable} database name is not explicitly disposable; use a name containing test, integration, ci, "
            "or migration"
        )
    host = parsed.host
    if host not in _LOCAL_DATABASE_HOSTS:
        expected_confirmation = f"{host}/{database}"
        provided_confirmation = os.getenv("TEST_REMOTE_DATABASE_CONFIRMATION", "")
        if not secrets.compare_digest(provided_confirmation, expected_confirmation):
            raise UnsafeTestDatabaseError(
                f"{variable} points to a remote host; set TEST_REMOTE_DATABASE_CONFIRMATION to "
                f"{expected_confirmation!r} for this disposable database"
            )
    return value


def require_same_database(first: str, second: str, first_variable: str, second_variable: str) -> None:
    first_url = _database_identity(make_url(first))
    second_url = _database_identity(make_url(second))
    if first_url != second_url:
        raise UnsafeTestDatabaseError(f"{first_variable} and {second_variable} must target the same database")


def _database_identity(url: URL) -> tuple[str | None, int | None, str | None]:
    return url.host, url.port, url.database
