from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.ingest.data_factory import DataFactoryService
from pharma_intel.ingest.malware import MalwareDetected, MalwareScanResult
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    AuditEvent,
    DataSource,
    DataSourceType,
    QuarantineStatus,
    SourceVersion,
    SourceVersionQuarantineDecision,
    Tenant,
    TenantDataset,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.security import Principal, require_principal


class DetectingScanner:
    def scan(self, _: Path) -> MalwareScanResult:
        raise MalwareDetected("Win.Test.EICAR_HDB-1")


def test_quarantine_decisions_are_idempotent_versioned_audited_and_never_bypass_rescan(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "quarantine-source"
    root.mkdir()
    (root / "first.md").write_text("controlled untrusted fixture one", encoding="utf-8")
    source = DataSource(
        tenant_id=tenant.id,
        name="Quarantine source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(root),
        owner="Security Operations",
        authorization_scopes=["contract:test-source"],
        authorization_valid_from=datetime.now(UTC),
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
        temporal_enabled=True,
    )
    data_factory = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
        malware_scanner=DetectingScanner(),
    )
    first_scan = data_factory.scan_source(source.id, "quarantine-first")
    data_factory.process_version(first_scan.version_ids[0])
    first = session.get(SourceVersion, first_scan.version_ids[0])
    assert first is not None

    (root / "second.md").write_text("controlled untrusted fixture two", encoding="utf-8")
    second_scan = data_factory.scan_source(source.id, "quarantine-second")
    second_id = next(version_id for version_id in second_scan.version_ids if version_id != first.id)
    data_factory.process_version(second_id)
    second = session.get(SourceVersion, second_id)
    assert second is not None

    (root / "third.md").write_text("controlled untrusted fixture three", encoding="utf-8")
    third_scan = data_factory.scan_source(source.id, "quarantine-third")
    third_id = next(version_id for version_id in third_scan.version_ids if version_id not in {first.id, second.id})
    data_factory.process_version(third_id)
    third = session.get(SourceVersion, third_id)
    assert third is not None

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "security-operator", "user", frozenset({"ingestion:read", "ingestion:manage"}))

    temporal_client = AsyncMock()
    monkeypatch.setattr("pharma_intel.api.Client.connect", AsyncMock(return_value=temporal_client))
    monkeypatch.setattr("pharma_intel.api.get_settings", lambda: settings)
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            queue = client.get("/api/v1/admin/quarantine-cases")
            detail = client.get(f"/api/v1/admin/quarantine-cases/{first.id}")
            hold_payload = {
                "operation_key": "test-hold",
                "expected_version": 1,
                "action": "hold",
                "reason": "Security review requires the immutable sample to remain isolated",
            }
            hold = client.post(f"/api/v1/admin/quarantine-cases/{first.id}/decisions", json=hold_payload)
            hold_duplicate = client.post(f"/api/v1/admin/quarantine-cases/{first.id}/decisions", json=hold_payload)
            hold_conflict = client.post(
                f"/api/v1/admin/quarantine-cases/{first.id}/decisions",
                json={**hold_payload, "reason": "Different decision intent"},
            )
            stale = client.post(
                f"/api/v1/admin/quarantine-cases/{first.id}/decisions",
                json={
                    "operation_key": "test-stale",
                    "expected_version": 1,
                    "action": "reject",
                    "reason": "This stale decision must fail closed",
                },
            )
            rescan = client.post(
                f"/api/v1/admin/quarantine-cases/{first.id}/decisions",
                json={
                    "operation_key": "test-rescan",
                    "expected_version": 2,
                    "action": "rescan",
                    "reason": "Updated signatures are available; perform the complete scan again",
                },
            )
            rejected = client.post(
                f"/api/v1/admin/quarantine-cases/{second.id}/decisions",
                json={
                    "operation_key": "test-reject",
                    "expected_version": 1,
                    "action": "reject",
                    "reason": "Confirmed malicious content must remain permanently rejected",
                },
            )
            rejected_rescan = client.post(
                f"/api/v1/admin/quarantine-cases/{second.id}/decisions",
                json={
                    "operation_key": "test-reject-rescan",
                    "expected_version": 2,
                    "action": "rescan",
                    "reason": "Rejected content cannot use the standard release path",
                },
            )
            direct_replay = client.post(
                f"/api/v1/admin/source-versions/{second.id}/replay",
                json={
                    "operation_key": "test-direct-replay",
                    "expected_state": "failed",
                    "expected_error_code": "malware_detected",
                    "from_stage": "malware_scan",
                    "reason": "A generic replay must not bypass quarantine governance",
                },
            )
            monkeypatch.setattr(
                "pharma_intel.api.Client.connect",
                AsyncMock(side_effect=RuntimeError("temporal unavailable")),
            )
            failed_rescan = client.post(
                f"/api/v1/admin/quarantine-cases/{third.id}/decisions",
                json={
                    "operation_key": "test-failed-rescan",
                    "expected_version": 1,
                    "action": "rescan",
                    "reason": "A workflow launch failure must restore the prior quarantine state",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert queue.status_code == 200
    assert {item["source_version_id"] for item in queue.json()} == {first.id, second.id, third.id}
    assert detail.status_code == 200
    assert detail.json()["quarantine_status"] == "pending_review"
    assert [item["action"] for item in detail.json()["decisions"]] == ["scan_detected"]
    assert hold.status_code == 200
    assert hold.json() == hold_duplicate.json()
    assert hold.json()["quarantine_status"] == "held"
    assert hold.json()["quarantine_version"] == 2
    assert hold_conflict.status_code == 409
    assert stale.status_code == 409
    assert rescan.status_code == 202
    assert rescan.json()["quarantine_status"] == "rescan_requested"
    assert rescan.json()["workflow_id"] == f"source-version-reprocess-{first.id}"
    assert rejected.status_code == 200
    assert rejected.json()["quarantine_status"] == "rejected"
    assert rejected_rescan.status_code == 409
    assert direct_replay.status_code == 409
    assert failed_rescan.status_code == 503
    temporal_client.start_workflow.assert_awaited_once()
    process_input = temporal_client.start_workflow.await_args.args[1]
    assert process_input.source_version_id == first.id
    assert process_input.from_stage == "malware_scan"
    assert session.scalar(select(func.count()).select_from(SourceVersionQuarantineDecision)) == 8
    actions = set(
        session.scalars(
            select(AuditEvent.action).where(
                AuditEvent.resource_type == "source_version",
                AuditEvent.resource_id.in_([first.id, second.id]),
            )
        )
    )
    assert {
        "source_version.quarantine.hold",
        "source_version.quarantine.rescan",
        "source_version.quarantine.reject",
    } <= actions
    session.refresh(second)
    assert second.quarantine_status == QuarantineStatus.REJECTED
    session.refresh(third)
    assert third.quarantine_status == QuarantineStatus.PENDING_REVIEW
    assert third.quarantine_version == 3
