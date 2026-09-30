from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pharma_intel.db import set_tenant_context
from pharma_intel.knowledge.read_model import KnowledgePageNotFound, KnowledgeReadService
from pharma_intel.models import (
    KnowledgeCitation,
    KnowledgeLink,
    KnowledgePage,
    KnowledgePageStatus,
    KnowledgePageVersion,
    SourceDocument,
    Tenant,
)
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.mark.integration
def test_knowledge_history_is_tenant_isolated_traceable_and_append_only() -> None:
    database_url = os.getenv("TEST_KNOWLEDGE_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_KNOWLEDGE_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_KNOWLEDGE_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        session.add_all(
            [
                Tenant(id=tenant_id, slug=f"knowledge-{tenant_id}", name="Knowledge PostgreSQL"),
                Tenant(id=other_tenant_id, slug=f"knowledge-{other_tenant_id}", name="Other tenant"),
            ]
        )
        session.flush()
        source = SourceDocument(
            tenant_id=tenant_id,
            title="EGFR competitive landscape",
            source_type="literature",
            source_uri="file:///research/egfr.pdf",
            content_sha256="a" * 64,
        )
        page = KnowledgePage(
            tenant_id=tenant_id,
            page_key="entity/target/egfr",
            page_type="target",
            title="EGFR",
            status=KnowledgePageStatus.PUBLISHED,
        )
        session.add_all([source, page])
        session.flush()
        version_one = KnowledgePageVersion(
            tenant_id=tenant_id,
            knowledge_page_id=page.id,
            version_number=1,
            compiler_version="knowledge-v1",
            content_json={"facts": [], "sources": []},
            rendered_markdown="# EGFR",
            content_sha256="1" * 64,
            source_snapshot_at=now - timedelta(days=1),
        )
        version_two = KnowledgePageVersion(
            tenant_id=tenant_id,
            knowledge_page_id=page.id,
            version_number=2,
            compiler_version="knowledge-v1",
            content_json={
                "facts": [
                    {
                        "id": "fact-1",
                        "predicate": "has_competitor",
                        "object_entity": None,
                        "value": {"name": "Drug B"},
                        "confidence": 0.92,
                        "citation": 1,
                    }
                ],
                "sources": [
                    {
                        "number": 1,
                        "document_id": source.id,
                        "title": source.title,
                        "source_uri": source.source_uri,
                        "locator": "page=8",
                    }
                ],
            },
            rendered_markdown="# EGFR\n\nDrug B [1]",
            content_sha256="2" * 64,
            source_snapshot_at=now,
        )
        session.add_all([version_one, version_two])
        session.flush()
        citation = KnowledgeCitation(
            tenant_id=tenant_id,
            page_version_id=version_two.id,
            ordinal=1,
            source_document_id=source.id,
            source_locator="page=8",
            quote="Drug B is an EGFR competitor.",
        )
        link = KnowledgeLink(
            tenant_id=tenant_id,
            page_version_id=version_two.id,
            relationship="has_competitor",
            target_key="entity/drug/drug-b",
            confidence=0.92,
        )
        session.add_all([citation, link])
        page.current_version_id = version_two.id
        session.commit()
        page_id = page.id

        service = KnowledgeReadService(session, tenant_id)
        coverage = service.coverage(page_id)
        assert coverage.fact_count == 1
        assert coverage.cited_fact_count == 1
        assert coverage.source_count == 1
        assert coverage.linked_entity_count == 1
        assert [item.version_number for item in service.version_history(page_id, 50)] == [2, 1]
        diff = service.version_diff(page_id, 2, None)
        assert diff.added_fact_count == 1
        assert diff.added_facts[0].source_document_id == source.id
        assert diff.added_facts[0].source_locator == "page=8"

        immutable_updates = (
            (text("UPDATE knowledge_page_versions SET compiler_version = 'tampered' WHERE id = :id"), version_two.id),
            (text("UPDATE knowledge_citations SET quote = 'tampered' WHERE id = :id"), citation.id),
            (text("UPDATE knowledge_links SET confidence = 0 WHERE id = :id"), link.id),
        )
        for statement, row_id in immutable_updates:
            with pytest.raises(DBAPIError, match="knowledge history is append-only"):
                session.execute(statement, {"id": row_id})
                session.commit()
            session.rollback()

        set_tenant_context(session, other_tenant_id)
        with pytest.raises(KnowledgePageNotFound):
            KnowledgeReadService(session, other_tenant_id).coverage(page_id)
    engine.dispose()
