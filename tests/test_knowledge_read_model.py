from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.knowledge.public import public_knowledge_markdown
from pharma_intel.models import KnowledgeLink, KnowledgePage, KnowledgePageStatus, KnowledgePageVersion, Tenant
from pharma_intel.security import Principal, require_principal


def _fact(
    fact_id: str,
    predicate: str,
    value: dict[str, str],
    citation: int,
) -> dict[str, object]:
    return {
        "id": fact_id,
        "predicate": predicate,
        "object_entity": None,
        "value": value,
        "confidence": 0.95,
        "citation": citation,
    }


def _source(number: int, document_id: str, title: str) -> dict[str, object]:
    return {
        "number": number,
        "document_id": document_id,
        "title": title,
        "source_uri": f"file:///research/{document_id}.pdf",
        "locator": f"page={number}",
    }


def _seed_versioned_page(session: Session, tenant: Tenant) -> KnowledgePage:
    page = KnowledgePage(
        tenant_id=tenant.id,
        page_key="entity/target/egfr",
        page_type="target",
        title="EGFR",
        status=KnowledgePageStatus.PUBLISHED,
    )
    session.add(page)
    session.flush()
    now = datetime.now(UTC)
    version_one = KnowledgePageVersion(
        tenant_id=tenant.id,
        knowledge_page_id=page.id,
        version_number=1,
        compiler_version="knowledge-v1",
        content_json={
            "facts": [_fact("fact-1", "has_target_class", {"name": "kinase"}, 1)],
            "sources": [_source(1, "document-1", "Foundational EGFR review")],
        },
        rendered_markdown="# EGFR\n\nTarget class: kinase.",
        content_sha256="1" * 64,
        source_snapshot_at=now - timedelta(days=1),
        created_by_run_id="ingestion-run-1",
        created_at=now - timedelta(days=1),
    )
    version_two = KnowledgePageVersion(
        tenant_id=tenant.id,
        knowledge_page_id=page.id,
        version_number=2,
        compiler_version="knowledge-v1",
        content_json={
            "facts": [
                _fact("fact-1", "has_target_class", {"name": "kinase"}, 1),
                _fact("fact-2", "has_competitor", {"name": "Drug B"}, 2),
            ],
            "sources": [
                _source(1, "document-1", "Foundational EGFR review"),
                _source(2, "document-2", "Competitive landscape update"),
            ],
        },
        rendered_markdown=(
            f'---\nid: "{page.id}"\nschema_version: "1.0"\n---\n# EGFR\n\nTarget class and competitor landscape.'
        ),
        content_sha256="2" * 64,
        source_snapshot_at=now,
        created_by_run_id="ingestion-run-2",
        created_at=now,
    )
    session.add_all([version_one, version_two])
    session.flush()
    page.current_version_id = version_two.id
    session.add(
        KnowledgeLink(
            tenant_id=tenant.id,
            page_version_id=version_two.id,
            relationship="has_competitor",
            target_key="entity/drug/drug-b",
            confidence=0.95,
        )
    )
    session.commit()
    return page


@pytest.mark.parametrize(
    ("markdown", "expected"),
    [
        ("---\nid: internal-id\n---\n# Public title", "# Public title"),
        ("---\r\nid: internal-id\r\n---\r\n# Public title", "# Public title"),
        ("---\nnot metadata\n---\n# Public title", "---\nnot metadata\n---\n# Public title"),
        ("---\nid: internal-id\n# Missing delimiter", "---\nid: internal-id\n# Missing delimiter"),
        ("# Public title", "# Public title"),
    ],
)
def test_public_knowledge_markdown_removes_only_complete_compiler_front_matter(
    markdown: str,
    expected: str,
) -> None:
    assert public_knowledge_markdown(markdown) == expected


def test_knowledge_coverage_history_and_traceable_diff_api(session: Session, tenant: Tenant) -> None:
    page = _seed_versioned_page(session, tenant)

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "test-key",
        "api_key",
        frozenset({"knowledge:read"}),
    )
    try:
        with TestClient(app) as client:
            detail = client.get(f"/api/v1/knowledge/pages/{page.id}")
            assert detail.status_code == 200
            assert detail.json() == {
                "id": page.id,
                "page_type": "target",
                "title": "EGFR",
                "updated_at": detail.json()["updated_at"],
                "version_number": 2,
                "rendered_markdown": "# EGFR\n\nTarget class and competitor landscape.",
                "source_snapshot_at": detail.json()["source_snapshot_at"],
            }

            coverage = client.get(f"/api/v1/knowledge/pages/{page.id}/coverage")
            assert coverage.status_code == 200
            assert coverage.json() == {
                "version_number": 2,
                "fact_count": 2,
                "cited_fact_count": 2,
                "uncited_fact_count": 0,
                "source_count": 2,
                "linked_entity_count": 1,
                "predicates": [
                    {"predicate": "has_competitor", "fact_count": 1, "cited_fact_count": 1},
                    {"predicate": "has_target_class", "fact_count": 1, "cited_fact_count": 1},
                ],
                "source_snapshot_at": coverage.json()["source_snapshot_at"],
            }

            history = client.get(f"/api/v1/knowledge/pages/{page.id}/versions", params={"limit": 10})
            assert history.status_code == 200
            versions = history.json()
            assert [item["version_number"] for item in versions] == [2, 1]
            assert {
                "version_id",
                "compiler_version",
                "content_sha256",
                "created_by_run_id",
                "created_at",
                "fact_count",
                "source_count",
            }.isdisjoint(versions[0])
            assert versions[0]["is_current"] is True
            assert versions[0]["previous_version_number"] == 1
            assert versions[0]["added_fact_count"] == 1
            assert versions[0]["removed_fact_count"] == 0
            assert versions[0]["added_source_count"] == 1
            assert versions[1]["previous_version_number"] is None
            assert versions[1]["added_fact_count"] == 1

            diff = client.get(f"/api/v1/knowledge/pages/{page.id}/versions/2/diff")
            assert diff.status_code == 200
            body = diff.json()
            assert body["from_version_number"] == 1
            assert body["to_version_number"] == 2
            assert body["added_fact_count"] == 1
            assert "page_id" not in body
            assert "fact_id" not in body["added_facts"][0]
            assert body["added_facts"][0]["predicate"] == "has_competitor"
            assert "source_document_id" not in body["added_facts"][0]
            assert "confidence" not in body["added_facts"][0]
            assert "citation_number" not in body["added_facts"][0]
            assert body["added_facts"][0]["source_title"] == "Competitive landscape update"
            assert body["added_facts"][0]["source_locator"] == "page=2"
            assert body["added_sources"] == [{"title": "Competitive landscape update", "locator": "page=2"}]
            assert body["truncated"] is False

            first_diff = client.get(f"/api/v1/knowledge/pages/{page.id}/versions/1/diff")
            assert first_diff.status_code == 200
            assert first_diff.json()["from_version_number"] is None
            assert first_diff.json()["added_fact_count"] == 1

            assert client.get(f"/api/v1/knowledge/pages/{page.id}/versions/3/diff").status_code == 404
            assert client.get("/api/v1/knowledge/pages/missing/coverage").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_public_knowledge_endpoints_hide_unpublished_pages(session: Session, tenant: Tenant) -> None:
    page = KnowledgePage(
        tenant_id=tenant.id,
        page_key="entity/target/no-version",
        page_type="target",
        title="No version",
        status=KnowledgePageStatus.DRAFT,
    )
    session.add(page)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = lambda: Principal(
        tenant.id,
        "test-key",
        "api_key",
        frozenset({"knowledge:read"}),
    )
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/knowledge/pages/{page.id}/coverage")
            assert response.status_code == 404
            assert response.json()["detail"] == "Knowledge page not found"
            assert client.get(f"/api/v1/knowledge/pages/{page.id}").status_code == 404
            assert client.get(f"/api/v1/knowledge/pages/{page.id}/versions").status_code == 404
            assert client.get(f"/api/v1/knowledge/pages/{page.id}/versions/1/diff").status_code == 404
            assert client.get("/api/v1/knowledge/pages").json() == []
    finally:
        app.dependency_overrides.clear()
