from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import KnowledgePage, KnowledgePageStatus, KnowledgePageVersion, Tenant
from pharma_intel.security import Principal, require_principal


def _published_page(session: Session, tenant_id: str, title: str, kind: str = "drug") -> None:
    page = KnowledgePage(
        tenant_id=tenant_id,
        page_key=f"audit-test/{title}",
        page_type=kind,
        title=title,
        status=KnowledgePageStatus.PUBLISHED,
    )
    session.add(page)
    session.flush()
    version = KnowledgePageVersion(
        tenant_id=tenant_id,
        knowledge_page_id=page.id,
        version_number=1,
        compiler_version="test",
        content_json={"facts": [], "sources": []},
        rendered_markdown=f"# {title}",
        content_sha256="1" * 64,
        source_snapshot_at=datetime.now(UTC),
    )
    session.add(version)
    session.flush()
    page.current_version_id = version.id


def test_public_knowledge_search_exposes_total_and_pages_without_cross_tenant_leaks(
    session: Session,
    tenant: Tenant,
) -> None:
    for index in range(503):
        _published_page(session, tenant.id, f"Drug {index:04}")
    other = Tenant(slug="other-knowledge", name="Other")
    session.add(other)
    session.flush()
    _published_page(session, other.id, "Drug hidden")
    session.add(KnowledgePage(tenant_id=tenant.id, page_key="draft", page_type="drug", title="Drug draft"))
    session.commit()

    def override_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "knowledge-reader",
        "user",
        frozenset({"knowledge:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/knowledge/pages/search", params={"limit": 50, "offset": 500})
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 503
            assert data["offset"] == 500
            assert data["limit"] == 50
            assert [page["title"] for page in data["items"]] == ["Drug 0500", "Drug 0501", "Drug 0502"]
            assert data["facets"]["page_type"] == {"drug": 503}
            legacy = client.get("/api/v1/knowledge/pages", params={"limit": 1}).json()
            assert isinstance(legacy, list) and legacy[0]["title"] == "Drug 0000"
    finally:
        app.dependency_overrides.clear()


def test_public_knowledge_search_treats_search_wildcards_literally_and_enforces_scope(
    session: Session,
    tenant: Tenant,
) -> None:
    _published_page(session, tenant.id, "100% targeted therapy", "target")
    _published_page(session, tenant.id, "Drug example")
    session.commit()

    def override_session() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "knowledge-reader",
        "user",
        frozenset({"knowledge:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/knowledge/pages/search", params={"q": "%", "page_type": "target"})
            assert response.status_code == 200
            assert response.json()["total"] == 1
            assert response.json()["items"][0]["title"] == "100% targeted therapy"
            filtered = client.get("/api/v1/knowledge/pages/search", params={"page_type": "target"}).json()
            assert filtered["total"] == 1 and filtered["facets"]["page_type"] == {"drug": 1, "target": 1}
            assert client.get("/api/v1/knowledge/pages/search", params={"offset": -1}).status_code == 422
            app.dependency_overrides[require_principal] = lambda: Principal(tenant.id, "viewer", "user", frozenset())
            assert client.get("/api/v1/knowledge/pages/search").status_code == 403
    finally:
        app.dependency_overrides.clear()
