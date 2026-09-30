from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pharma_intel.models import Base, Tenant


def pytest_configure() -> None:
    test_environment = {
        "APP_ENV": "test",
        "JWT_SECRET": "pytest-only-human-session-secret-not-for-runtime",  # noqa: S105
        "MALWARE_SCAN_ENABLED": "false",
        "PARSER_SERVICE_ENABLED": "false",
        "SEARCH_BACKEND": "database",
        "SEARCH_PROJECTION_ENABLED": "false",
        "SOURCE_ROOTS": "",
        "AI_GOVERNANCE_ENABLED": "false",
        "AI_BASE_URL": "",
        "AI_API_KEY": "",
        "AI_MODEL": "",
        "AI_ALLOWED_RESPONSE_MODELS_JSON": "[]",
        "AI_THINKING_MODE": "provider_default",
        "AI_INCLUDE_SCHEMA_IN_PROMPT": "false",
        "AI_RESPONSE_FORMAT_MODE": "json_schema",
    }
    os.environ.update(test_environment)


@pytest.fixture
def session() -> Generator[Session]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            yield db
    finally:
        engine.dispose()


@pytest.fixture
def tenant(session: Session) -> Tenant:
    item = Tenant(slug="test", name="Test Tenant")
    session.add(item)
    session.commit()
    return item
