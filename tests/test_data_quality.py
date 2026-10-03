from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TypedDict

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pharma_intel.accounts.identity import create_account
from pharma_intel.config import Settings
from pharma_intel.models import (
    Base,
    DataQualityIssue,
    DataSource,
    DataSourceType,
    Entity,
    EntityType,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    GovernanceStatus,
    IngestionRun,
    ReviewStatus,
    RunState,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    StagedFact,
    StageStatus,
    Tenant,
    User,
    UserRole,
)
from pharma_intel.quality.service import DataQualityError, DataQualityService
from pharma_intel.quality.worker import DataQualityWorker


class QualityFixture(TypedDict):
    owner: User
    source: DataSource
    asset: SourceAsset
    version: SourceVersion
    document: SourceDocument
    fact: StagedFact
    claim: EvidenceClaim
    run: IngestionRun


def _quality_fixture(session: Session, tenant: Tenant, tmp_path: Path) -> QualityFixture:
    owner = create_account(
        tenant_id=tenant.id,
        email=f"quality-owner-{tenant.id}@example.test",
        normalized_email=f"quality-owner-{tenant.id}@example.test",
        display_name="Quality Owner",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ANALYST,
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Quality source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Data Quality",
        authorization_scopes=["contract:quality-test"],
        dataset_key="literature",
        expected_freshness_seconds=3600,
        last_success_at=datetime.now(UTC) - timedelta(hours=3),
    )
    session.add_all([owner, source])
    session.flush()
    digest = hashlib.sha256(str(tmp_path).encode()).hexdigest()
    document = SourceDocument(
        tenant_id=tenant.id,
        title="Quality source document",
        source_type="folder",
        source_uri=f"file://{tmp_path}/quality.md",
        content_sha256=digest,
    )
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="quality.md",
        source_uri=document.source_uri,
        file_name="quality.md",
        extension=".md",
        processing_mode="parse",
    )
    session.add_all([document, asset])
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=digest,
        size_bytes=200,
        parse_status=StageStatus.FAILED,
        source_document_id=None,
    )
    session.add(version)
    session.flush()
    asset.current_version_id = version.id
    extraction = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=version.id,
        schema_name="pharma_document_facts",
        schema_version="2.12.0",
        model_provider="quality-test",
        model_name="quality-test",
        prompt_sha256="a" * 64,
        policy_sha256="b" * 64,
        input_sha256="c" * 64,
        status=RunState.SUCCEEDED,
    )
    subject = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.TARGET,
        name="Quality EGFR",
        normalized_name="quality egfr",
        review_status=ReviewStatus.VERIFIED,
    )
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id=f"quality-test-run-{tenant.id}",
        state=RunState.FAILED,
    )
    session.add_all([extraction, subject, run])
    session.flush()
    fact = StagedFact(
        tenant_id=tenant.id,
        extraction_run_id=extraction.id,
        fact_kind="claim",
        fact_key="quality-claim",
        raw_payload={"value": "EGFR"},
        payload={"value": "EGFR"},
        source_document_id=document.id,
        source_locator="page=1",
        source_quote="Quality evidence",
        confidence=0.95,
        status=GovernanceStatus.PUBLISHED,
    )
    claim = EvidenceClaim(
        tenant_id=tenant.id,
        subject_id=subject.id,
        predicate="has_quality_marker",
        value={"value": "EGFR"},
        source_document_id=document.id,
        source_locator="page=1",
        quote="Quality evidence",
        confidence=0.95,
        review_status=ReviewStatus.VERIFIED,
    )
    session.add_all([fact, claim])
    session.commit()
    return {
        "owner": owner,
        "source": source,
        "asset": asset,
        "version": version,
        "document": document,
        "fact": fact,
        "claim": claim,
        "run": run,
    }


def test_quality_snapshots_open_assign_recover_and_resolve_issues(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    fixture = _quality_fixture(session, tenant, tmp_path)
    settings = Settings(data_quality_issue_sla_hours=8)
    service = DataQualityService(session, settings, tenant.id)

    first = service.evaluate(trigger="manual", actor_type="user", actor_id=fixture["owner"].id)
    assert first.metrics["completeness"]["status"] == "failed"
    assert first.metrics["duplicate_rate"]["status"] == "passed"
    assert first.metrics["citation_coverage"]["status"] == "failed"
    assert first.metrics["freshness_coverage"]["status"] == "failed"
    assert first.metrics["ingestion_success"]["status"] == "failed"
    assert first.metrics["drift"]["status"] == "not_applicable"

    completeness = next(issue for issue in service.issues() if issue.metric_key == "completeness")
    assigned = service.act(
        completeness.id,
        action="assign",
        expected_version=1,
        actor_id=fixture["owner"].id,
        request_id="quality-assign",
        owner_user_id=fixture["owner"].id,
        notes=None,
    )
    assert assigned.owner_user_id == fixture["owner"].id
    acknowledged = service.act(
        completeness.id,
        action="acknowledge",
        expected_version=2,
        actor_id=fixture["owner"].id,
        request_id="quality-ack",
        owner_user_id=None,
        notes=None,
    )
    assert acknowledged.status == "acknowledged"

    fixture["version"].parse_status = StageStatus.SUCCEEDED
    fixture["version"].source_document_id = fixture["document"].id
    fixture["source"].last_success_at = datetime.now(UTC)
    fixture["run"].state = RunState.SUCCEEDED
    session.add(
        FactProvenanceLink(
            tenant_id=tenant.id,
            resource_type="evidence_claim",
            resource_id=fixture["claim"].id,
            staged_fact_id=fixture["fact"].id,
            evidence_claim_id=fixture["claim"].id,
            source_asset_id=fixture["asset"].id,
            source_version_id=fixture["version"].id,
            source_document_id=fixture["document"].id,
            dataset_key="literature",
            source_locator="page=1",
        )
    )
    session.commit()

    second = service.evaluate(trigger="scheduled", actor_type="system", actor_id="quality-worker")
    assert second.metrics["completeness"]["status"] == "passed"
    session.refresh(completeness)
    assert completeness.status == "ready_to_resolve"
    assert completeness.version == 4
    assert any(issue.metric_key == "drift" and issue.status == "open" for issue in service.issues())

    with pytest.raises(DataQualityError, match="changed"):
        service.act(
            completeness.id,
            action="resolve",
            expected_version=3,
            actor_id=fixture["owner"].id,
            request_id="quality-stale",
            owner_user_id=None,
            notes="stale",
        )
    resolved = service.act(
        completeness.id,
        action="resolve",
        expected_version=4,
        actor_id=fixture["owner"].id,
        request_id="quality-resolve",
        owner_user_id=None,
        notes="Parser backlog was replayed and verified",
    )
    assert resolved.status == "resolved"
    assert resolved.active_key is None
    assert [event.action for event in service.events(resolved.id)] == [
        "opened",
        "assign",
        "acknowledge",
        "recovered",
        "resolve",
    ]
    assert session.scalar(select(DataQualityIssue).where(DataQualityIssue.id == resolved.id)) is not None


def test_quality_coverage_reports_source_level_freshness_authorization_and_fact_gates(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    fixture = _quality_fixture(session, tenant, tmp_path)
    coverage = DataQualityService(session, Settings(data_quality_issue_sla_hours=8), tenant.id).coverage()

    assert len(coverage) == 1
    report = coverage[0]
    assert report["source_id"] == fixture["source"].id
    assert report["dataset_key"] == "literature"
    assert report["owner"] == "Data Quality"
    assert report["authorization_status"] == "valid"
    assert report["asset_count"] == 1
    assert report["active_asset_count"] == 1
    assert report["parsed_asset_count"] == 0
    assert report["parse_missing_count"] == 1
    assert report["parse_coverage"] == 0
    assert report["fact_count"] == 0
    assert report["freshness_status"] == "stale"
    assert report["run_count"] == 1
    assert report["successful_run_count"] == 0
    assert report["failed_run_count"] == 1
    assert report["ingestion_success_rate"] == 0
    assert report["failure_sla_status"] == "healthy"


def test_quality_issue_assignment_and_versions_enforce_operational_concurrency(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    fixture = _quality_fixture(session, tenant, tmp_path)
    viewer = create_account(
        tenant_id=tenant.id,
        email="quality-viewer@example.test",
        normalized_email="quality-viewer@example.test",
        display_name="Quality Viewer",
        password_hash="not-used",  # noqa: S106
        role=UserRole.VIEWER,
    )
    session.add(viewer)
    session.commit()
    service = DataQualityService(session, Settings(), tenant.id)
    service.evaluate(trigger="manual", actor_type="user", actor_id=fixture["owner"].id)
    completeness = next(issue for issue in service.issues() if issue.metric_key == "completeness")

    with pytest.raises(DataQualityError, match="administrator or analyst"):
        service.act(
            completeness.id,
            action="assign",
            expected_version=1,
            actor_id=fixture["owner"].id,
            request_id="quality-viewer-owner",
            owner_user_id=viewer.id,
            notes=None,
        )
    with pytest.raises(DataQualityError, match="Assign an owner"):
        service.act(
            completeness.id,
            action="acknowledge",
            expected_version=1,
            actor_id=fixture["owner"].id,
            request_id="quality-ack-unassigned",
            owner_user_id=None,
            notes=None,
        )

    service.evaluate(trigger="scheduled", actor_type="system", actor_id="quality-worker")
    session.refresh(completeness)
    assert completeness.status == "open"
    assert completeness.version == 2
    assert [event.action for event in service.events(completeness.id)] == ["opened"]


def test_quality_worker_schedules_one_durable_snapshot_per_interval(tmp_path: Path) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            tenant = Tenant(slug="quality-worker", name="Quality Worker")
            session.add(tenant)
            session.commit()
            _quality_fixture(session, tenant, tmp_path)
        worker = DataQualityWorker(
            factory,
            Settings(data_quality_evaluation_interval_seconds=3600),
            worker_id="quality-worker-test",
        )
        first = worker.process_once()
        assert first is not None and first.trigger == "scheduled"
        assert worker.process_once() is None
        worker._next_check = 0  # noqa: SLF001 - force the due-check branch without sleeping
        assert worker.process_once() is None
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
