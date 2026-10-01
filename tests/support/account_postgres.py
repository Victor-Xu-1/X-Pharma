from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from pharma_intel.config import get_settings
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.fixture
def account_engine(monkeypatch: pytest.MonkeyPatch) -> Generator[Engine]:
    value = os.getenv("TEST_ACCOUNT_REGISTRATION_DATABASE_URL")
    if not value:
        pytest.skip("TEST_ACCOUNT_REGISTRATION_DATABASE_URL is not configured")
    url = require_disposable_postgres_url(value, "TEST_ACCOUNT_REGISTRATION_DATABASE_URL")
    monkeypatch.setenv("HUMAN_AUTH_MODE", "local")
    monkeypatch.setenv("HUMAN_SELF_REGISTRATION_ENABLED", "true")
    get_settings.cache_clear()
    engine = create_engine(url, pool_size=12, max_overflow=12)
    with engine.connect() as connection:
        role = connection.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        assert not role.rolsuper and not role.rolbypassrls
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()
