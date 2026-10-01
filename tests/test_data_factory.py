from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, Never

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.config import Settings
from pharma_intel.governance.lifecycle import DataLifecycleService
from pharma_intel.governance.service import SCHEMA_NAME, SCHEMA_VERSION, governance_policy_sha256
from pharma_intel.ingest.connectors import ConnectorCapabilities, ConnectorTransportError, SourceConnectorRegistry
from pharma_intel.ingest.data_factory import (
    DataFactoryService,
    IngestionRunCanceled,
    SourceVersionReplayRejected,
)
from pharma_intel.ingest.malware import MalwareDetected, MalwareScanResult
from pharma_intel.ingest.parser_client import ParserServiceUnavailable
from pharma_intel.ingest.parsers import DocumentParseError, ParsedDocument
from pharma_intel.ingest.quarantine import apply_operator_decision
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    DataSource,
    DataSourceState,
    DataSourceType,
    ExtractionRun,
    IngestionFinding,
    IngestionRun,
    OutboxEvent,
    QuarantineStatus,
    RunState,
    SourceAsset,
    SourceAssetState,
    SourceDocument,
    SourceVersion,
    SourceVersionQuarantineDecision,
    SourceVersionState,
    StageStatus,
    Tenant,
    TenantDataset,
    UserRole,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.security import Principal

Chem: Any = import_module("rdkit.Chem")


def _service(session: Session, tenant: Tenant, tmp_path: Path) -> DataFactoryService:
    dataset_keys = set(session.scalars(select(DataSource.dataset_key).where(DataSource.tenant_id == tenant.id)))
    for dataset_key in dataset_keys:
        session.add(
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key=dataset_key,
                display_name=dataset_key.title(),
                license_policy=internal_evidence_license_policy(source="test"),
            )
        )
    session.commit()
    settings = Settings(
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
        ai_governance_enabled=False,
        source_roots_config=str(tmp_path),
    )
    return DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
    )


class _UnavailableConnector:
    source_type = DataSourceType.FOLDER
    capabilities = ConnectorCapabilities(
        connector_id="test-unavailable-v1",
        incremental=True,
        replayable=True,
        credentials_required=False,
    )

    def normalize_root_uri(self, root_uri: str) -> str:
        return root_uri

    def validate_configuration(self, source: DataSource) -> list[str]:
        return []

    def discover(self, source: DataSource) -> Never:
        raise ConnectorTransportError("upstream source is unavailable")

    def materialize(self, item: Any) -> Never:
        raise AssertionError("materialize must not run when discovery fails")


def test_failed_discovery_records_attempt_for_scheduler_backoff(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    source = DataSource(
        tenant_id=tenant.id,
        name="Unavailable upstream",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        include_globs=["*"],
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)
    service.connector_registry = SourceConnectorRegistry(
        service.settings,
        connectors=[_UnavailableConnector()],
    )
    attempted_before = datetime.now(UTC) - timedelta(minutes=5)
    source.last_scanned_at = attempted_before
    session.commit()

    outcome = service.scan_source(source.id, "unavailable-source-workflow")

    assert outcome.state == "failed"
    session.refresh(source)
    assert source.state == DataSourceState.UNAVAILABLE
    assert source.last_scanned_at is not None
    observed_scan = source.last_scanned_at
    if observed_scan.tzinfo is None:
        observed_scan = observed_scan.replace(tzinfo=UTC)
    assert observed_scan > attempted_before
    assert source.last_success_at is None


def test_registered_folder_is_ingested_idempotently_and_versioned(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    document = root / "target.md"
    document.write_text("EGFR is a receptor tyrosine kinase.", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Research",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        include_globs=["*", "**/*"],
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)

    first = service.scan_source(source.id, "workflow-1")
    assert first.state == "succeeded"
    assert len(first.version_ids) == 1
    processed = service.process_version(first.version_ids[0])
    assert processed.malware_scan_status == "skipped"
    assert processed.parse_status == "succeeded"
    assert processed.retrieval_status == "not_started"

    second = service.scan_source(source.id, "workflow-2")
    assert second.version_ids == []
    assert second.unchanged == 1
    assert session.scalar(select(func.count()).select_from(SourceVersion)) == 1
    assert session.scalar(select(func.count()).select_from(SourceDocument)) == 1

    document.write_text("EGFR L858R can alter inhibitor sensitivity.", encoding="utf-8")
    third = service.scan_source(source.id, "workflow-3")
    assert len(third.version_ids) == 1
    assert session.scalar(select(func.count()).select_from(SourceVersion)) == 2
    current_asset = session.scalar(select(SourceAsset))
    assert current_asset is not None
    assert current_asset.current_version_id == third.version_ids[0]
    session.refresh(source)
    assert source.connector_cursor["kind"] == "folder_inventory"
    assert source.connector_cursor["object_count"] == 1
    assert source.last_cursor_at is not None

    original_version = session.get(SourceVersion, first.version_ids[0])
    assert original_version is not None
    document.write_text("EGFR is a receptor tyrosine kinase.", encoding="utf-8")
    fourth = service.scan_source(source.id, "workflow-4")
    assert len(fourth.version_ids) == 1
    versions = list(
        session.scalars(
            select(SourceVersion)
            .where(SourceVersion.source_asset_id == current_asset.id)
            .order_by(SourceVersion.version_number)
        )
    )
    assert [version.version_number for version in versions] == [1, 2, 3]
    assert versions[0].content_sha256 == versions[2].content_sha256 == original_version.content_sha256
    assert versions[0].id != versions[2].id
    assert current_asset.current_version_id == versions[2].id


def test_temporal_identity_is_bound_and_cancellation_stops_later_processing(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "cancel-source"
    root.mkdir()
    (root / "target.md").write_text("EGFR controlled cancellation", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Cancellation source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Data Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)

    scan = service.scan_source(
        source.id,
        "cancel-correlation",
        temporal_workflow_id="source-ingest-cancel-source",
        temporal_run_id="temporal-cancel-run",
    )
    run = session.scalar(select(IngestionRun).where(IngestionRun.id == scan.run_id))
    assert run is not None
    assert run.temporal_workflow_id == "source-ingest-cancel-source"
    assert run.temporal_run_id == "temporal-cancel-run"
    run.state = RunState.CANCELED
    run.cancel_requested_at = datetime.now(UTC)
    session.commit()

    with pytest.raises(IngestionRunCanceled, match="before stage version_start"):
        service.process_version(scan.version_ids[0], run.id)

    version = session.get(SourceVersion, scan.version_ids[0])
    assert version is not None
    assert version.state == SourceVersionState.SNAPSHOTTED
    assert version.parse_status == StageStatus.NOT_STARTED

    resumed = service.scan_source(source.id, "cancel-correlation-resumed")
    assert resumed.version_ids == scan.version_ids
    assert resumed.unchanged == 0


def test_unchanged_recoverable_failure_is_reprocessed_without_duplicate_version(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "recoverable-source"
    root.mkdir()
    (root / "article.xml").write_text("<article><body><p>EGFR evidence</p></body></article>", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Recoverable parser source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        include_globs=["*", "**/*"],
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)
    service.document_parser = RejectingDocumentParser()

    first = service.scan_source(source.id, "recoverable-failure-1")
    failed = service.process_version(first.version_ids[0])
    assert failed.state == "failed"
    assert failed.error == "parser capability is temporarily incomplete"

    service.document_parser = RecoveredDocumentParser()
    second = service.scan_source(source.id, "recoverable-failure-2")
    assert second.version_ids == first.version_ids
    assert second.unchanged == 0
    recovered = service.process_version(second.version_ids[0])
    assert recovered.state == "parsed"
    assert recovered.parse_status == "succeeded"
    assert session.scalar(select(func.count()).select_from(SourceVersion)) == 1

    third = service.scan_source(source.id, "recoverable-failure-3")
    assert third.version_ids == []
    assert third.unchanged == 1

    service.settings.ai_governance_enabled = True
    governance_backfill = service.scan_source(source.id, "recoverable-failure-4")
    assert governance_backfill.version_ids == first.version_ids
    assert governance_backfill.unchanged == 0

    version = session.get(SourceVersion, first.version_ids[0])
    assert version is not None
    version.governance_status = StageStatus.FAILED
    version.state = SourceVersionState.GOVERNANCE_PENDING
    version.error_code = "governance_model_failed"
    version.error_message = "temporary provider rejection"
    session.commit()
    governance_retry = service.scan_source(source.id, "recoverable-failure-5")
    assert governance_retry.version_ids == first.version_ids
    assert governance_retry.unchanged == 0


def test_interrupted_governance_is_requeued_and_auto_replayed_from_governance(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "interrupted-governance-source"
    root.mkdir()
    (root / "evidence.md").write_text("EGFR governance recovery evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Interrupted governance source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Data Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        include_globs=["*"],
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)
    first = service.scan_source(source.id, "interrupted-governance-1")
    service.process_version(first.version_ids[0])
    version = session.get(SourceVersion, first.version_ids[0])
    assert version is not None
    version.state = SourceVersionState.GOVERNANCE_PENDING
    version.governance_status = StageStatus.NOT_STARTED
    session.commit()
    service.settings.ai_governance_enabled = True

    class RecoveredGovernanceService:
        def __init__(self, db: Session, *_: object) -> None:
            self.session = db

        def govern_version(self, source_version_id: str) -> dict[str, int | str]:
            recovered = self.session.get(SourceVersion, source_version_id)
            assert recovered is not None
            recovered.governance_status = StageStatus.SUCCEEDED
            recovered.state = SourceVersionState.PUBLISHED
            self.session.commit()
            return {"run_id": "recovered", "fact_count": 0}

    monkeypatch.setattr("pharma_intel.ingest.data_factory.GovernanceService", RecoveredGovernanceService)
    resumed = service.scan_source(source.id, "interrupted-governance-2")
    assert resumed.version_ids == first.version_ids
    recovered = service.process_version(resumed.version_ids[0], from_stage="auto")
    assert recovered.state == "published"
    assert recovered.governance_status == "succeeded"


def test_stage_replay_skips_completed_security_and_parser_work(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "stage-replay-source"
    root.mkdir()
    (root / "evidence.md").write_text("EGFR stage recovery evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Stage replay source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Data Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)
    service.malware_scanner = CleanMalwareScanner()
    service.document_parser = RejectingDocumentParser()

    scan = service.scan_source(source.id, "stage-replay-scan")
    failed = service.process_version(scan.version_ids[0])
    assert failed.state == "failed"
    assert failed.malware_scan_status == "succeeded"
    assert failed.parse_status == "failed"

    service.malware_scanner = DetectingMalwareScanner()
    service.document_parser = RecoveredDocumentParser()
    parsed = service.process_version(scan.version_ids[0], from_stage="parse")
    assert parsed.state == "parsed"
    assert parsed.malware_scan_status == "succeeded"
    assert parsed.parse_status == "succeeded"
    assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 2

    version = session.get(SourceVersion, scan.version_ids[0])
    assert version is not None
    version.retrieval_status = StageStatus.FAILED
    session.commit()
    service.document_parser = RejectingDocumentParser()
    queued = service.process_version(version.id, from_stage="retrieval")
    assert queued.parse_status == "succeeded"
    assert queued.retrieval_status == "not_started"
    assert session.scalar(select(func.count()).select_from(OutboxEvent)) == 3


def test_governance_stage_replay_requires_prerequisites_and_queues_projection(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "governance-replay-source"
    root.mkdir()
    (root / "evidence.md").write_text("EGFR governance recovery evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Governance replay source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Data Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)
    scan = service.scan_source(source.id, "governance-replay-scan")
    service.process_version(scan.version_ids[0])
    version = session.get(SourceVersion, scan.version_ids[0])
    assert version is not None
    version.governance_status = StageStatus.FAILED
    version.state = SourceVersionState.GOVERNANCE_PENDING
    version.error_code = "governance_model_failed"
    version.error_message = "provider unavailable"
    session.commit()

    with pytest.raises(SourceVersionReplayRejected, match="AI governance is disabled"):
        service.process_version(version.id, from_stage="governance")

    class RecoveredGovernanceService:
        def __init__(self, db: Session, *_: object) -> None:
            self.session = db

        def govern_version(self, source_version_id: str) -> dict[str, int | str]:
            recovered = self.session.get(SourceVersion, source_version_id)
            assert recovered is not None
            recovered.governance_status = StageStatus.SUCCEEDED
            recovered.state = SourceVersionState.PUBLISHED
            self.session.commit()
            return {"run_id": "recovered", "fact_count": 0}

    service.settings.ai_governance_enabled = True
    service.malware_scanner = DetectingMalwareScanner()
    service.document_parser = RejectingDocumentParser()
    monkeypatch.setattr("pharma_intel.ingest.data_factory.GovernanceService", RecoveredGovernanceService)
    before = int(session.scalar(select(func.count()).select_from(OutboxEvent)) or 0)
    recovered = service.process_version(version.id, from_stage="governance")
    assert recovered.state == "published"
    assert recovered.governance_status == "succeeded"
    assert recovered.retrieval_status == "not_started"
    assert session.scalar(select(func.count()).select_from(OutboxEvent)) == before + 1


def test_unchanged_source_is_requeued_when_the_governance_policy_changes(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "policy-source"
    root.mkdir()
    (root / "target.md").write_text("EGFR evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Policy-aware source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)
    discovered = service.scan_source(source.id, "policy-scan-1")
    service.process_version(discovered.version_ids[0])
    version = session.get(SourceVersion, discovered.version_ids[0])
    assert version is not None

    service.settings.ai_governance_enabled = True
    service.settings.ai_base_url = "https://model-v1.test"
    service.settings.ai_api_key = "test-key"
    service.settings.ai_model = "extractor-v1"
    current_policy = governance_policy_sha256(service.settings)
    session.add(
        ExtractionRun(
            tenant_id=tenant.id,
            source_version_id=version.id,
            schema_name=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            model_provider="openai-compatible",
            model_name=service.settings.ai_model,
            prompt_sha256="a" * 64,
            policy_sha256=current_policy,
            input_sha256=version.extracted_text_sha256 or "b" * 64,
            status=RunState.SUCCEEDED,
        )
    )
    version.governance_status = StageStatus.SUCCEEDED
    version.state = SourceVersionState.PUBLISHED
    session.commit()

    unchanged = service.scan_source(source.id, "policy-scan-2")
    assert unchanged.version_ids == []
    assert unchanged.unchanged == 1

    service.settings.ai_model = "extractor-v2"
    requeued = service.scan_source(source.id, "policy-scan-3")
    assert requeued.version_ids == [version.id]
    assert requeued.unchanged == 0
    assert session.scalar(select(func.count()).select_from(SourceVersion)) == 1


def test_scan_does_not_silently_resurrect_a_deleted_source_asset(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "withdrawn-source"
    root.mkdir()
    (root / "withdrawn.md").write_text("Withdrawn EGFR evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Withdrawn source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)
    service.scan_source(source.id, "withdrawal-before")
    asset = session.scalar(select(SourceAsset).where(SourceAsset.data_source_id == source.id))
    assert asset is not None
    asset.state = SourceAssetState.DELETED
    asset.current_version_id = None
    session.commit()

    second = service.scan_source(source.id, "withdrawal-after")

    assert second.failed == 1
    session.refresh(asset)
    assert asset.state == SourceAssetState.DELETED
    assert asset.current_version_id is None
    finding = session.scalar(select(IngestionFinding).where(IngestionFinding.ingestion_run_id == second.run_id))
    assert finding is not None
    assert "explicit operator reauthorization" in finding.message

    user = create_account(
        tenant_id=tenant.id,
        email="reauthorization@example.test",
        normalized_email="reauthorization@example.test",
        display_name="Reauthorization Operator",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.commit()
    principal = Principal(tenant.id, user.id, "user", frozenset({"commercial:read", "commercial:write"}))
    lifecycle = DataLifecycleService(session, service.object_store)
    lifecycle.upsert_source_policy(
        principal,
        retention_seconds=300,
        legal_basis="restored source authorization",
        geographic_scope=["CN"],
        active=True,
        request_id="reauthorization-policy",
    )
    outcome = lifecycle.reauthorize_source_asset(
        principal,
        asset.id,
        idempotency_key="data-factory.reauthorize.1",
        reason="source rights restored",
        request_id="data-factory-reauthorize",
    )
    assert outcome.event.outcome == "succeeded"

    resumed = service.scan_source(source.id, "withdrawal-reauthorized")
    assert resumed.failed == 0
    assert len(resumed.version_ids) == 1
    versions = list(
        session.scalars(
            select(SourceVersion)
            .where(SourceVersion.source_asset_id == asset.id)
            .order_by(SourceVersion.version_number)
        )
    )
    assert [version.version_number for version in versions] == [1, 2]
    assert versions[0].content_sha256 == versions[1].content_sha256
    assert versions[0].id != versions[1].id
    resumed_asset = session.get(SourceAsset, asset.id, populate_existing=True)
    assert resumed_asset is not None
    assert resumed_asset.state == SourceAssetState.ACTIVE
    assert resumed_asset.current_version_id == versions[1].id


def test_scan_fails_closed_outside_configured_source_roots(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    (outside / "evidence.md").write_text("Unapproved evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Outside source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(outside),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add_all(
        [
            source,
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                license_policy=internal_evidence_license_policy(source="test"),
            ),
        ]
    )
    session.commit()
    settings = Settings(
        source_roots_config=str(allowed),
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )
    service = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
    )

    result = service.scan_source(source.id, "outside-source-workflow")

    assert result.state == "failed"
    finding = session.scalar(select(IngestionFinding).where(IngestionFinding.ingestion_run_id == result.run_id))
    assert finding is not None
    assert finding.code == "source_governance_blocked"
    assert finding.retryable is False
    assert session.scalar(select(func.count()).select_from(SourceAsset)) == 0


def test_expired_source_authorization_blocks_discovery_and_renewal_resumes_it(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "licensed-source"
    root.mkdir()
    (root / "evidence.md").write_text("Licensed EGFR evidence", encoding="utf-8")
    now = datetime.now(UTC)
    source = DataSource(
        tenant_id=tenant.id,
        name="Time-bound licensed source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        authorization_valid_from=now - timedelta(days=60),
        authorization_valid_until=now - timedelta(seconds=1),
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)

    blocked = service.scan_source(source.id, "expired-source-workflow")

    assert blocked.state == "failed"
    finding = session.scalar(select(IngestionFinding).where(IngestionFinding.ingestion_run_id == blocked.run_id))
    assert finding is not None
    assert finding.code == "source_governance_blocked"
    assert "expired" in finding.message
    assert session.scalar(select(func.count()).select_from(SourceAsset)) == 0

    source.authorization_valid_from = now - timedelta(minutes=1)
    source.authorization_valid_until = now + timedelta(days=365)
    session.commit()
    resumed = service.scan_source(source.id, "renewed-source-workflow")

    assert resumed.state == "succeeded"
    assert len(resumed.version_ids) == 1
    assert session.scalar(select(func.count()).select_from(SourceAsset)) == 1


def test_source_disconnect_preserves_snapshots_and_marks_availability(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "mounted-source"
    root.mkdir()
    (root / "compound.sdf").write_text("compound asset", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Chemistry",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="projects",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)

    scan = service.scan_source(source.id, "workflow-up")
    service.process_version(scan.version_ids[0])
    version = session.get(SourceVersion, scan.version_ids[0])
    assert version is not None
    assert version.snapshot_status == StageStatus.SUCCEEDED
    immutable_uri = version.raw_object_uri

    root.rename(tmp_path / "disconnected")
    failed = service.scan_source(source.id, "workflow-down")
    session.refresh(source)
    asset = session.scalar(select(SourceAsset))

    assert failed.state == "failed"
    assert source.state == DataSourceState.UNAVAILABLE
    assert asset is not None and asset.state == SourceAssetState.SOURCE_UNAVAILABLE
    assert session.get(SourceVersion, version.id).raw_object_uri == immutable_uri  # type: ignore[union-attr]

    source.root_uri = str(tmp_path / "disconnected")
    session.commit()
    resumed = service.scan_source(source.id, "workflow-recovered")
    recovered_source = session.get(DataSource, source.id)
    recovered_asset = session.get(SourceAsset, asset.id)
    assert resumed.state == "succeeded"
    assert recovered_source is not None
    assert recovered_asset is not None
    assert recovered_source.state == DataSourceState.ACTIVE
    assert recovered_asset.state == SourceAssetState.ACTIVE


def test_unexpected_scan_failure_is_persisted_and_retryable(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "failing-source"
    root.mkdir()
    (root / "paper.md").write_text("Evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Failing source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
        )
    )
    session.commit()
    settings = Settings(
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
        source_roots_config=str(tmp_path),
    )

    def fail_heartbeat(_: str) -> None:
        raise RuntimeError("heartbeat transport unavailable")

    service = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
        heartbeat=fail_heartbeat,
    )

    with pytest.raises(RuntimeError, match="heartbeat transport unavailable"):
        service.scan_source(source.id, "workflow-failure")

    run = session.scalar(select(IngestionRun).where(IngestionRun.workflow_id == "workflow-failure"))
    assert run is not None
    finding = session.scalar(select(IngestionFinding).where(IngestionFinding.ingestion_run_id == run.id))
    session.refresh(source)
    assert run.state == RunState.FAILED
    assert run.completed_at is not None
    assert finding is not None and finding.code == "scan_activity_failed" and finding.retryable is True
    assert source.consecutive_failures == 1


class CleanMalwareScanner:
    def scan(self, _: Path) -> MalwareScanResult:
        return MalwareScanResult("clamd-instream-v1", "ClamAV 1.4.3/27562/test")


class DetectingMalwareScanner:
    def scan(self, _: Path) -> MalwareScanResult:
        raise MalwareDetected("Win.Test.EICAR_HDB-1")


class UnavailableDocumentParser:
    def parse(self, _: Path, __: int) -> Never:
        raise ParserServiceUnavailable("parser capacity exhausted", error_code="parser_capacity_exhausted")


class RejectingDocumentParser:
    def parse(self, _: Path, __: int) -> Never:
        raise DocumentParseError("parser capability is temporarily incomplete")


class RecoveredDocumentParser:
    def parse(self, _: Path, __: int) -> ParsedDocument:
        return ParsedDocument("EGFR evidence", {}, "recovered-parser", "2")


def test_malware_detection_blocks_parse_and_preserves_snapshot(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "malware-source"
    root.mkdir()
    (root / "report.md").write_text("untrusted source content", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Malware source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Security Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add_all(
        [
            source,
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                license_policy=internal_evidence_license_policy(source="test"),
            ),
        ]
    )
    session.commit()
    settings = Settings(
        source_roots_config=str(tmp_path),
        object_store_root=tmp_path / "objects",
        malware_scan_enabled=True,
    )
    service = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
        malware_scanner=DetectingMalwareScanner(),
    )

    scan = service.scan_source(source.id, "malware-detection-workflow")
    result = service.process_version(scan.version_ids[0])
    version = session.get(SourceVersion, scan.version_ids[0])

    assert result.state == "failed"
    assert result.malware_scan_status == "failed"
    assert result.parse_status == "not_started"
    assert version is not None
    assert version.raw_object_uri is not None
    assert version.extracted_text_object_uri is None
    assert version.error_code == "malware_detected"
    assert version.quarantine_status == QuarantineStatus.PENDING_REVIEW
    assert version.quarantine_version == 1
    assert version.metadata_json["malware_scan"] == {
        "status": "failed",
        "reason_code": "malware_detected",
        "threat_name": "Win.Test.EICAR_HDB-1",
    }
    assert session.scalar(select(func.count()).select_from(SourceDocument)) == 0
    decisions = list(
        session.scalars(
            select(SourceVersionQuarantineDecision).where(
                SourceVersionQuarantineDecision.source_version_id == version.id
            )
        )
    )
    assert [decision.action for decision in decisions] == ["scan_detected"]

    repeated = service.scan_source(source.id, "malware-detection-repeat")
    assert repeated.version_ids == []
    assert repeated.unchanged == 1

    apply_operator_decision(
        session,
        version,
        operation_key="unit:quarantine-rescan:0001",
        expected_version=1,
        action="rescan",
        reason="Unit recovery requires a complete scanner pass",
        actor_type="user",
        actor_id="test-operator",
        workflow_id=f"source-version-reprocess-{version.id}",
    )
    session.commit()
    service.malware_scanner = CleanMalwareScanner()
    recovered = service.process_version(version.id)
    recovered_version = session.get(SourceVersion, version.id, populate_existing=True)
    assert recovered_version is not None
    assert recovered.parse_status == "succeeded"
    assert recovered_version.quarantine_status == QuarantineStatus.CLEARED
    assert recovered_version.quarantine_version == 3
    decisions = list(
        session.scalars(
            select(SourceVersionQuarantineDecision)
            .where(SourceVersionQuarantineDecision.source_version_id == version.id)
            .order_by(SourceVersionQuarantineDecision.resulting_version)
        )
    )
    assert [decision.action for decision in decisions] == ["scan_detected", "rescan", "scan_clean"]


def test_transient_parser_failure_is_persisted_for_temporal_retry(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "parser-retry-source"
    root.mkdir()
    (root / "report.md").write_text("retryable evidence", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Parser retry source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add_all(
        [
            source,
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                license_policy=internal_evidence_license_policy(source="test"),
            ),
        ]
    )
    session.commit()
    settings = Settings(
        source_roots_config=str(tmp_path),
        object_store_root=tmp_path / "objects",
        malware_scan_enabled=True,
    )
    service = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
        malware_scanner=CleanMalwareScanner(),
        document_parser=UnavailableDocumentParser(),
    )

    scan = service.scan_source(source.id, "parser-retry-workflow")
    with pytest.raises(ParserServiceUnavailable, match="capacity exhausted"):
        service.process_version(scan.version_ids[0])
    version = session.get(SourceVersion, scan.version_ids[0])

    assert version is not None
    assert version.state == SourceVersionState.SNAPSHOTTED
    assert version.malware_scan_status == StageStatus.SUCCEEDED
    assert version.parse_status == StageStatus.NOT_STARTED
    assert version.error_code == "parser_capacity_exhausted"
    assert version.extracted_text_object_uri is None
    assert session.scalar(select(func.count()).select_from(SourceDocument)) == 0


def test_asset_only_unsupported_scientific_file_is_scanned_before_registration(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "structure-source"
    root.mkdir()
    (root / "drawing.cdx").write_text("registered scientific asset", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Structure source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Chemistry Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="projects",
        stable_seconds=0,
    )
    session.add_all(
        [
            source,
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="projects",
                display_name="Projects",
                license_policy=internal_evidence_license_policy(source="test"),
            ),
        ]
    )
    session.commit()
    settings = Settings(
        source_roots_config=str(tmp_path),
        object_store_root=tmp_path / "objects",
        malware_scan_enabled=True,
    )
    service = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
        malware_scanner=CleanMalwareScanner(),
    )

    scan = service.scan_source(source.id, "scientific-asset-workflow")
    result = service.process_version(scan.version_ids[0])
    version = session.get(SourceVersion, scan.version_ids[0])

    assert result.state == "asset_only"
    assert result.malware_scan_status == "succeeded"
    assert result.parse_status == "skipped"
    assert version is not None
    assert version.malware_scanner == "clamd-instream-v1"
    assert version.malware_signature_version == "ClamAV 1.4.3/27562/test"
    assert version.malware_scanned_at is not None
    assert version.source_document_id is not None


def test_real_sdf_is_automatically_parsed_and_projected_for_governance(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    root = tmp_path / "chemistry-source"
    root.mkdir()
    sdf = root / "ethanol.sdf"
    molecule = Chem.MolFromSmiles("CCO")
    assert molecule is not None
    molecule.SetProp("_Name", "Ethanol")
    writer = Chem.SDWriter(str(sdf))
    writer.write(molecule)
    writer.close()
    source = DataSource(
        tenant_id=tenant.id,
        name="Chemistry source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Chemistry Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="projects",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    service = _service(session, tenant, tmp_path)

    scan = service.scan_source(source.id, "scientific-parse-workflow")
    result = service.process_version(scan.version_ids[0])
    version = session.get(SourceVersion, scan.version_ids[0])
    assert version is not None and version.source_document_id is not None
    document = session.get(SourceDocument, version.source_document_id)

    assert result.state == "parsed"
    assert result.parse_status == "succeeded"
    assert result.retrieval_status == "not_started"
    assert result.governance_status == "skipped"
    assert version.parser_name == "rdkit-sdf"
    assert version.extracted_text_object_uri is not None
    assert version.metadata_json["retrieval_projection"]["status"] == "queued"
    assert document is not None
    assert document.metadata_json["parser"]["scientific_format"] == "sdf"
    assert document.metadata_json["parser"]["record_preview"][0]["standard_inchi_key"] == (
        "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    )
