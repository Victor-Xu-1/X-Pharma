from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

import pharma_intel.object_store as object_store_module
from pharma_intel.http import governance_review, runtime
from pharma_intel.models import EvidenceClaim, GovernanceStatus
from pharma_intel.schemas import ReviewDecision
from pharma_intel.security import Principal


def test_approval_returns_published_fact_when_markdown_export_fails(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
) -> None:
    staged = SimpleNamespace(
        id="fact-1",
        fact_kind="program",
        raw_payload={},
        payload={"subject": {"name": "EGFR"}},
        normalization_version=None,
        source_document_id="document-1",
        source_locator="sheet=Results,row=2",
        source_quote="A real source quote",
        confidence=0.95,
        status=GovernanceStatus.PUBLISHED,
        quality_findings=[],
        conflict_with_ids=[],
        created_at=datetime.now(UTC),
        published_resource_type="evidence_claim",
        published_resource_id="claim-1",
    )

    class FakeGovernanceService:
        def __init__(self, *args: object) -> None:
            pass

        def approve_fact(self, staged_fact_id: str, reviewer_id: str, notes: str | None) -> object:
            assert staged_fact_id == staged.id
            assert reviewer_id == "reviewer-1"
            return staged

    class FakeCompiler:
        def __init__(self, *args: object) -> None:
            pass

        def compile_entity(self, entity_id: str, run_id: str) -> object:
            assert entity_id == "entity-1"
            assert run_id == f"review:{staged.id}"
            return SimpleNamespace(page_id="page-1")

        def export_page(self, page_id: str, export_root: object) -> None:
            assert page_id == "page-1"
            raise OSError("temporary export filesystem failure")

    def fixture_get(model: object, identifier: str) -> object:
        assert model is EvidenceClaim
        assert identifier == staged.published_resource_id
        return SimpleNamespace(subject_id="entity-1")

    events: list[tuple[str, dict[str, object]]] = []

    class FakeLogger:
        def error(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

    monkeypatch.setattr(governance_review, "GovernanceService", FakeGovernanceService)
    monkeypatch.setattr(governance_review, "KnowledgeCompiler", FakeCompiler)
    monkeypatch.setattr(object_store_module, "build_object_store", lambda settings: object())
    monkeypatch.setattr(session, "get", fixture_get)
    monkeypatch.setattr(runtime, "get_settings", lambda: SimpleNamespace(markdown_export_root="unused"))
    monkeypatch.setattr(governance_review, "request_logger", FakeLogger())

    result = governance_review.decide_staged_fact(
        staged.id,
        ReviewDecision(decision="approve"),
        Principal("tenant-1", "reviewer-1", "user", frozenset({"governance:review"})),
        session,
    )

    assert result.id == staged.id
    assert result.status is GovernanceStatus.PUBLISHED
    assert events == [
        (
            "knowledge_markdown_export_failed_after_publish",
            {"page_id": "page-1", "error_type": "OSError"},
        )
    ]
