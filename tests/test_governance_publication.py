from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.publication import GovernancePublicationService, PublicationError
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    FactWithdrawalTombstone,
    GovernancePublicationBatch,
    GovernanceStatus,
    KnowledgeCitation,
    KnowledgePage,
    KnowledgePageVersion,
    OutboxEvent,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    StagedFact,
    Tenant,
    User,
    UserRole,
)
from pharma_intel.object_store import FileSystemObjectStore


def _publication_service(session: Session, tenant: Tenant, tmp_path: Path) -> GovernancePublicationService:
    settings = Settings(object_store_root=tmp_path / "objects")
    return GovernancePublicationService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
    )


def _reviewer(session: Session, tenant: Tenant) -> User:
    reviewer = User(
        tenant_id=tenant.id,
        email="publication-reviewer@example.test",
        normalized_email="publication-reviewer@example.test",
        display_name="Publication Reviewer",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add(reviewer)
    session.flush()
    return reviewer


def _reviewable_claims(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    *,
    count: int,
    shared_projection: bool = False,
) -> list[StagedFact]:
    source = DataSource(
        tenant_id=tenant.id,
        name=f"Publication source {hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8]}",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Data Governance",
        authorization_scopes=["contract:publication-test"],
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="publication.md",
        source_uri=f"file://{tmp_path}/publication.md",
        file_name="publication.md",
        extension=".md",
        processing_mode="parse",
    )
    document = SourceDocument(
        tenant_id=tenant.id,
        title="Publication governance fixture",
        source_type="folder",
        source_uri=asset.source_uri,
        content_sha256=hashlib.sha256(str(tmp_path).encode()).hexdigest(),
    )
    session.add_all([asset, document])
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=document.content_sha256,
        size_bytes=1024,
        source_document_id=document.id,
    )
    session.add(version)
    session.flush()
    extraction = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=version.id,
        schema_name="pharma_document_facts",
        schema_version="2.12.0",
        model_provider="publication-test",
        model_name="publication-test",
        prompt_sha256="a" * 64,
        policy_sha256="b" * 64,
        input_sha256="c" * 64,
        status=RunState.SUCCEEDED,
    )
    session.add(extraction)
    session.flush()
    facts: list[StagedFact] = []
    for index in range(count):
        fact = StagedFact(
            tenant_id=tenant.id,
            extraction_run_id=extraction.id,
            fact_kind="claim",
            fact_key=f"publication-claim-{index}",
            raw_payload={"value": index},
            payload={
                "subject": {"entity_type": "target", "name": "Publication EGFR"},
                "predicate": "has_publication_marker" if shared_projection else f"has_publication_marker_{index}",
                "value": {"index": index},
            },
            source_document_id=document.id,
            source_locator="page=1" if shared_projection else f"page={index + 1}",
            source_quote=f"Publication evidence {index}",
            confidence=0.91,
            status=GovernanceStatus.REVIEW_PENDING,
        )
        session.add(fact)
        session.flush()
        session.add(
            ReviewTask(
                tenant_id=tenant.id,
                staged_fact_id=fact.id,
                status=GovernanceStatus.REVIEW_PENDING,
                reasons=[{"code": "human_review_required"}],
            )
        )
        facts.append(fact)
    session.commit()
    return facts


def test_publication_batch_previews_commits_and_withdraws_atomically(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    reviewer = _reviewer(session, tenant)
    facts = _reviewable_claims(session, tenant, tmp_path / "atomic", count=2)
    service = _publication_service(session, tenant, tmp_path)

    preview = service.preview(
        operation="publish",
        staged_fact_ids=[fact.id for fact in facts],
        idempotency_key="publication-preview-atomic",
        user_id=reviewer.id,
        reason="Both source quotes were verified",
    )
    duplicate = service.preview(
        operation="publish",
        staged_fact_ids=[fact.id for fact in reversed(facts)],
        idempotency_key="publication-preview-atomic",
        user_id=reviewer.id,
        reason="Both source quotes were verified",
    )
    assert duplicate.id == preview.id
    assert preview.blocked_count == 0

    committed = service.commit(preview.id, preview.preview_sha256, reviewer.id)
    assert committed.status == "committed"
    published_facts = [session.get(StagedFact, fact.id) for fact in facts]
    assert all(fact is not None for fact in published_facts)
    assert [fact.status for fact in published_facts if fact is not None] == [
        GovernanceStatus.PUBLISHED,
        GovernanceStatus.PUBLISHED,
    ]
    assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 2
    assert session.scalar(select(func.count()).select_from(FactProvenanceLink)) == 2

    withdrawal = service.preview(
        operation="withdraw",
        staged_fact_ids=[fact.id for fact in facts],
        idempotency_key="publication-withdraw-atomic",
        user_id=reviewer.id,
        reason="The licensed source issued a formal correction",
    )
    assert withdrawal.blocked_count == 0
    withdrawn = service.commit(withdrawal.id, withdrawal.preview_sha256, reviewer.id)
    assert withdrawn.status == "committed"
    withdrawn_facts = [session.get(StagedFact, fact.id) for fact in facts]
    assert all(fact is not None for fact in withdrawn_facts)
    assert [fact.status for fact in withdrawn_facts if fact is not None] == [
        GovernanceStatus.WITHDRAWN,
        GovernanceStatus.WITHDRAWN,
    ]
    assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 0
    assert session.scalar(select(func.count()).select_from(FactProvenanceLink)) == 0
    assert session.scalar(select(func.count()).select_from(FactWithdrawalTombstone)) == 2
    assert (
        session.scalar(
            select(func.count()).select_from(OutboxEvent).where(OutboxEvent.event_type == "governance.fact.withdrawn")
        )
        == 2
    )


def test_publication_commit_rejects_status_drift_without_partial_publish(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    reviewer = _reviewer(session, tenant)
    facts = _reviewable_claims(session, tenant, tmp_path / "drift", count=2)
    service = _publication_service(session, tenant, tmp_path)
    preview = service.preview(
        operation="publish",
        staged_fact_ids=[fact.id for fact in facts],
        idempotency_key="publication-preview-drift",
        user_id=reviewer.id,
        reason="Initial review completed",
    )
    facts[1].status = GovernanceStatus.REJECTED
    session.commit()

    with pytest.raises(PublicationError, match="status changed"):
        service.commit(preview.id, preview.preview_sha256, reviewer.id)

    session.expire_all()
    stored_batch = session.get(GovernancePublicationBatch, preview.id)
    stored_fact = session.get(StagedFact, facts[0].id)
    assert stored_batch is not None and stored_batch.status == "previewed"
    assert stored_fact is not None and stored_fact.status == GovernanceStatus.REVIEW_PENDING
    assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 0


def test_withdraw_preview_blocks_a_projection_shared_by_another_published_fact(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    reviewer = _reviewer(session, tenant)
    facts = _reviewable_claims(session, tenant, tmp_path / "shared", count=2, shared_projection=True)
    service = _publication_service(session, tenant, tmp_path)
    publication = service.preview(
        operation="publish",
        staged_fact_ids=[fact.id for fact in facts],
        idempotency_key="publication-preview-shared",
        user_id=reviewer.id,
        reason="Shared claim publication test",
    )
    service.commit(publication.id, publication.preview_sha256, reviewer.id)
    assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 1

    withdrawal = service.preview(
        operation="withdraw",
        staged_fact_ids=[facts[0].id],
        idempotency_key="publication-withdraw-shared",
        user_id=reviewer.id,
        reason="Attempt to retract one supporting fact",
    )
    items = service.items(withdrawal.id)
    assert withdrawal.blocked_count == 1
    assert items[0].blockers == [
        {
            "code": "shared_published_projection",
            "resource_type": "evidence_claim",
            "resource_id": facts[0].published_resource_id,
            "other_published_fact_count": 1,
        }
    ]
    with pytest.raises(PublicationError, match="blocking findings"):
        service.commit(withdrawal.id, withdrawal.preview_sha256, reviewer.id)

    complete_withdrawal = service.preview(
        operation="withdraw",
        staged_fact_ids=[fact.id for fact in facts],
        idempotency_key="publication-withdraw-shared-complete",
        user_id=reviewer.id,
        reason="Retract every supporting fact atomically",
    )
    assert complete_withdrawal.blocked_count == 0
    service.commit(complete_withdrawal.id, complete_withdrawal.preview_sha256, reviewer.id)
    assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 0
    assert session.scalar(select(func.count()).select_from(FactWithdrawalTombstone)) == 2


def test_withdraw_preview_blocks_evidence_used_by_immutable_knowledge_history(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    reviewer = _reviewer(session, tenant)
    fact = _reviewable_claims(session, tenant, tmp_path / "knowledge", count=1)[0]
    service = _publication_service(session, tenant, tmp_path)
    publication = service.preview(
        operation="publish",
        staged_fact_ids=[fact.id],
        idempotency_key="publication-preview-knowledge",
        user_id=reviewer.id,
        reason="Evidence citation publication test",
    )
    service.commit(publication.id, publication.preview_sha256, reviewer.id)
    session.refresh(fact)
    assert fact.published_resource_id is not None

    page = KnowledgePage(
        tenant_id=tenant.id,
        page_key="target:publication-egfr",
        page_type="target",
        title="Publication EGFR",
    )
    session.add(page)
    session.flush()
    version = KnowledgePageVersion(
        tenant_id=tenant.id,
        knowledge_page_id=page.id,
        version_number=1,
        compiler_version="publication-test",
        content_json={"title": page.title},
        rendered_markdown="# Publication EGFR",
        content_sha256="d" * 64,
        source_snapshot_at=datetime.now(UTC),
    )
    session.add(version)
    session.flush()
    session.add(
        KnowledgeCitation(
            tenant_id=tenant.id,
            page_version_id=version.id,
            ordinal=1,
            source_document_id=fact.source_document_id,
            evidence_claim_id=fact.published_resource_id,
            source_locator=fact.source_locator,
            quote=fact.source_quote,
        )
    )
    session.commit()

    withdrawal = service.preview(
        operation="withdraw",
        staged_fact_ids=[fact.id],
        idempotency_key="publication-withdraw-knowledge",
        user_id=reviewer.id,
        reason="Source correction requires a superseding knowledge page first",
    )
    assert withdrawal.blocked_count == 1
    assert service.items(withdrawal.id)[0].blockers == [
        {
            "code": "downstream_reference",
            "resource_type": "evidence_claim",
            "resource_id": fact.published_resource_id,
            "reference_type": "knowledge_citations",
            "reference_count": 1,
        }
    ]
    with pytest.raises(PublicationError, match="blocking findings"):
        service.commit(withdrawal.id, withdrawal.preview_sha256, reviewer.id)
