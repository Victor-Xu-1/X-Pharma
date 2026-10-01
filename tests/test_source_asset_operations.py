from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.models import (
    AuditEvent,
    DataSource,
    DataSourceType,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StageStatus,
    Tenant,
)
from pharma_intel.security import Principal, require_principal


class PreviewObjectStore:
    def read_bytes(self, uri: str, max_bytes: int) -> bytes:
        assert uri == "file:///controlled/extracted.txt"
        payload = ("page one evidence\n" * 20).encode()
        assert len(payload) < max_bytes
        return payload


def test_source_asset_inventory_detail_and_safe_text_preview(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = DataSource(
        tenant_id=tenant.id,
        name="Asset inventory source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Data Operations",
        authorization_scopes=["contract:test"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="reports/egfr.pdf",
        source_uri="file:///sources/reports/egfr.pdf",
        file_name="egfr.pdf",
        extension=".pdf",
        media_type="application/pdf",
        processing_mode="parse",
    )
    session.add(asset)
    session.flush()
    parsed = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256="a" * 64,
        size_bytes=1024,
        state=SourceVersionState.PARSED,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.NOT_STARTED,
        extracted_text_object_uri="file:///controlled/extracted.txt",
        extracted_text_sha256="b" * 64,
        parser_name="pypdf",
        parser_version="6.0",
        metadata_json={"parser": {"page_count": 3}},
    )
    quarantined = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=2,
        content_sha256="c" * 64,
        size_bytes=2048,
        state=SourceVersionState.FAILED,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.FAILED,
        parse_status=StageStatus.NOT_STARTED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.NOT_STARTED,
        raw_object_uri="file:///controlled/quarantined.pdf",
        error_code="malware_detected",
        error_message="Malicious content was detected",
        metadata_json={"malware_scan": {"status": "failed", "threat_name": "Test-Signature"}},
    )
    session.add_all([parsed, quarantined])
    session.flush()
    asset.current_version_id = quarantined.id
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(
            tenant.id,
            "operator-1",
            "user",
            frozenset({"ingestion:read", "ingestion:manage"}),
        )

    temporal_client = AsyncMock()
    monkeypatch.setattr("pharma_intel.ingest.commands.versions.Client.connect", AsyncMock(return_value=temporal_client))
    monkeypatch.setattr(
        "pharma_intel.http.runtime.get_settings",
        lambda: Settings(source_roots_config=str(tmp_path), temporal_enabled=True),
    )
    monkeypatch.setattr(
        "pharma_intel.http.source_versions.object_store_module.build_object_store",
        lambda _settings: PreviewObjectStore(),
    )
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            inventory = client.get("/api/v1/admin/source-assets", params={"data_source_id": source.id})
            detail = client.get(f"/api/v1/admin/source-assets/{asset.id}")
            preview = client.get(
                f"/api/v1/admin/source-versions/{parsed.id}/preview",
                params={"max_chars": 100},
            )
            blocked = client.get(f"/api/v1/admin/source-versions/{quarantined.id}/preview")
            replay = client.post(
                f"/api/v1/admin/source-versions/{quarantined.id}/replay",
                json={
                    "operation_key": "source-version-replay-0001",
                    "expected_state": "failed",
                    "expected_error_code": "malware_detected",
                    "from_stage": "malware_scan",
                    "reason": "Security signatures were updated",
                },
            )
            replay_duplicate = client.post(
                f"/api/v1/admin/source-versions/{quarantined.id}/replay",
                json={
                    "operation_key": "source-version-replay-0001",
                    "expected_state": "failed",
                    "expected_error_code": "malware_detected",
                    "from_stage": "malware_scan",
                    "reason": "Security signatures were updated",
                },
            )
            replay_conflict = client.post(
                f"/api/v1/admin/source-versions/{quarantined.id}/replay",
                json={
                    "operation_key": "source-version-replay-0001",
                    "expected_state": "failed",
                    "expected_error_code": "malware_detected",
                    "from_stage": "malware_scan",
                    "reason": "Different recovery intent",
                },
            )
            missing = client.get("/api/v1/admin/source-assets/missing")
    finally:
        app.dependency_overrides.clear()

    assert inventory.status_code == 200
    assert inventory.json()["total"] == 1
    assert inventory.json()["items"][0]["logical_path"] == "reports/egfr.pdf"
    assert "source_fingerprint" not in inventory.json()["items"][0]
    assert detail.status_code == 200
    versions = detail.json()["versions"]
    assert [version["version_number"] for version in versions] == [2, 1]
    assert versions[0]["metadata_json"]["malware_scan"]["threat_name"] == "Test-Signature"
    assert "raw_object_uri" not in versions[0]
    assert "extracted_text_object_uri" not in versions[1]
    assert preview.status_code == 200
    assert preview.json()["returned_chars"] == 100
    assert preview.json()["truncated"] is True
    assert preview.json()["extracted_text_sha256"] == "b" * 64
    assert blocked.status_code == 409
    assert replay.status_code == 202
    assert replay.json() == replay_duplicate.json()
    assert replay.json()["source_version_id"] == quarantined.id
    assert replay_conflict.status_code == 409
    temporal_client.start_workflow.assert_awaited_once()
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "source_version.replay",
            AuditEvent.resource_id == quarantined.id,
        )
    )
    assert audit is not None
    assert audit.details["from_stage"] == "malware_scan"
    assert missing.status_code == 404


def test_source_version_replay_accepts_the_failed_stage_and_binds_it_to_temporal(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = DataSource(
        tenant_id=tenant.id,
        name="Stage recovery source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Data Operations",
        authorization_scopes=["contract:test"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="reports/stage-recovery.md",
        source_uri="file:///sources/reports/stage-recovery.md",
        file_name="stage-recovery.md",
        extension=".md",
        media_type="text/markdown",
        processing_mode="parse",
    )
    document = SourceDocument(
        tenant_id=tenant.id,
        title="stage-recovery.md",
        source_type="folder",
        source_uri=asset.source_uri,
        canonical_uri="file:///objects/source.md",
        content_sha256="d" * 64,
    )
    session.add_all([asset, document])
    session.flush()
    parse_failed = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256="a" * 64,
        size_bytes=128,
        state=SourceVersionState.FAILED,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.FAILED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.NOT_STARTED,
        raw_object_uri="file:///objects/parse-failed.md",
        error_code="parse_failed",
        error_message="parser rejected the document",
    )
    governance_failed = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=2,
        content_sha256="b" * 64,
        size_bytes=128,
        state=SourceVersionState.GOVERNANCE_PENDING,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.FAILED,
        raw_object_uri="file:///objects/governance-failed.md",
        extracted_text_object_uri="file:///objects/governance-failed.txt",
        extracted_text_sha256="e" * 64,
        source_document_id=document.id,
        error_code="governance_model_failed",
        error_message="provider was unavailable",
    )
    retrieval_failed = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=3,
        content_sha256="d" * 64,
        size_bytes=128,
        state=SourceVersionState.PUBLISHED,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        retrieval_status=StageStatus.FAILED,
        governance_status=StageStatus.SUCCEEDED,
        raw_object_uri="file:///objects/retrieval-failed.md",
        extracted_text_object_uri="file:///objects/retrieval-failed.txt",
        extracted_text_sha256="f" * 64,
        source_document_id=document.id,
        error_code=None,
        error_message=None,
    )
    session.add_all([parse_failed, governance_failed, retrieval_failed])
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "operator-1", "user", frozenset({"ingestion:read", "ingestion:manage"}))

    temporal_client = AsyncMock()
    monkeypatch.setattr("pharma_intel.ingest.commands.versions.Client.connect", AsyncMock(return_value=temporal_client))
    monkeypatch.setattr(
        "pharma_intel.http.runtime.get_settings",
        lambda: Settings(
            source_roots_config=str(tmp_path),
            temporal_enabled=True,
            ai_governance_enabled=True,
            ai_base_url="https://model.example.test/v1",
            ai_api_key="test-only-key",
            ai_model="test-model",
        ),
    )
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            detail = client.get(f"/api/v1/admin/source-assets/{asset.id}")
            responses = []
            for version, stage in (
                (parse_failed, "parse"),
                (governance_failed, "governance"),
                (retrieval_failed, "retrieval"),
            ):
                responses.append(
                    client.post(
                        f"/api/v1/admin/source-versions/{version.id}/replay",
                        json={
                            "operation_key": f"stage-replay-{stage}-0001",
                            "expected_state": version.state.value,
                            "expected_error_code": version.error_code,
                            "from_stage": stage,
                            "reason": f"Recover the failed {stage} stage",
                        },
                    )
                )
    finally:
        app.dependency_overrides.clear()

    assert detail.status_code == 200
    replayable = {item["id"]: item["replayable_stages"] for item in detail.json()["versions"]}
    assert replayable == {
        parse_failed.id: ["malware_scan", "parse"],
        governance_failed.id: ["governance"],
        retrieval_failed.id: ["retrieval"],
    }
    assert [response.status_code for response in responses] == [202, 202, 202]
    assert [response.json()["from_stage"] for response in responses] == ["parse", "governance", "retrieval"]
    payloads = [call.args[1] for call in temporal_client.start_workflow.await_args_list]
    assert [payload.from_stage for payload in payloads] == ["parse", "governance", "retrieval"]
