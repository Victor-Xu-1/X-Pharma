from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import Entity, EntityType, ReviewStatus, Tenant
from pharma_intel.public_research.service import PublicResearchBusy
from pharma_intel.schemas.public_research import PublicResearchResponse
from pharma_intel.security import Principal, require_principal


@pytest.fixture
def client(session: Session, tenant: Tenant) -> Generator[TestClient]:
    def db_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = db_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id, "user", "user", frozenset({"entities:read"})
    )
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_public_online_research_is_human_only_even_for_wildcard_keys(client: TestClient, tenant: Tenant) -> None:
    app.dependency_overrides[require_principal] = lambda: Principal(tenant.id, "key", "api_key", frozenset({"*"}))
    assert client.get("/api/v1/public-research/coverage").status_code == 403
    assert client.post("/api/v1/public-research/search", json={"q": "EGFR"}).status_code == 403


def test_public_coverage_is_authoritative_verified_and_tenant_scoped(
    client: TestClient, session: Session, tenant: Tenant
) -> None:
    other = Tenant(slug="other-public", name="Other")
    session.add(other)
    session.flush()
    session.add_all(
        [
            Entity(
                tenant_id=tenant.id,
                name="Drug",
                normalized_name="drug",
                entity_type=EntityType.DRUG,
                review_status=ReviewStatus.VERIFIED,
            ),
            Entity(tenant_id=tenant.id, name="Draft", normalized_name="draft", entity_type=EntityType.DRUG),
            Entity(
                tenant_id=other.id,
                name="Other",
                normalized_name="other",
                entity_type=EntityType.DRUG,
                review_status=ReviewStatus.VERIFIED,
            ),
        ]
    )
    session.commit()
    data = client.get("/api/v1/public-research/coverage").json()
    assert data["entity_counts"]["drug"] == 1 and data["entity_counts"]["patent"] == 0


@pytest.mark.parametrize("chunked", [False, True])
def test_public_research_request_is_bounded_before_json_parsing(client: TestClient, chunked: bool) -> None:
    payload = b'{"q":"' + b"a" * 5000 + b'"}'
    response = client.post(
        "/api/v1/public-research/search",
        content=iter([payload[:100], payload[100:]]) if chunked else payload,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413


def test_public_request_does_not_write_to_canonical_facts_and_busy_is_explicit(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = MagicMock()
    service.search.return_value = PublicResearchResponse(query="EGFR", observed_at=datetime.now(UTC), results=[])
    monkeypatch.setattr("pharma_intel.http.public_research.PublicResearchService", lambda: service)
    response = client.post("/api/v1/public-research/search", json={"q": "EGFR", "topic": "targets"})
    assert response.status_code == 200 and response.json()["persisted"] is False
    service.search.side_effect = PublicResearchBusy("occupied")
    response = client.post("/api/v1/public-research/search", json={"q": "EGFR"})
    assert response.status_code == 429 and response.headers["retry-after"] == "2"
