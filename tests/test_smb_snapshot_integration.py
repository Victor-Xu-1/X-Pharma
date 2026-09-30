from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import ConnectorTransportError, SourceConnectorRegistry
from pharma_intel.ingest.data_factory import DataFactoryService
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    DataSource,
    DataSourceState,
    DataSourceType,
    SourceAsset,
    SourceAssetState,
    SourceVersion,
    SourceVersionState,
    StageStatus,
    Tenant,
    TenantDataset,
)
from pharma_intel.object_store import FileSystemObjectStore

pytestmark = pytest.mark.integration
CREDENTIAL_ENV = "TEST_SMB_SOURCE_CREDENTIAL_JSON"


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is required for the real SMB protocol integration test")
    return value


def test_real_encrypted_smb_snapshot_versioning_race_delete_outage_and_recovery(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = required_environment("TEST_SMB_SOURCE_ORIGIN")
    source_directory = Path(required_environment("TEST_SMB_SOURCE_DIRECTORY"))
    credential_json = required_environment(CREDENTIAL_ENV)
    monkeypatch.setenv(CREDENTIAL_ENV, credential_json)
    settings = Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=CREDENTIAL_ENV,
        source_smb_allowed_origins_config=origin,
        source_smb_require_encryption=True,
        source_smb_allow_insecure_loopback=True,
        source_smb_connect_timeout_seconds=3,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Real encrypted SMB protocol source",
        source_type=DataSourceType.SMB_SNAPSHOT,
        root_uri=f"{origin}/research/",
        credential_ref=f"env://{CREDENTIAL_ENV}",
        owner="Acceptance Data Operations",
        data_classification="confidential",
        authorization_scopes=["contract:smb-acceptance"],
        dataset_key="literature",
        include_globs=["*", "**/*"],
        exclude_globs=[],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=60,
        expected_freshness_seconds=3600,
        rate_limit_per_minute=100_000,
    )
    session.add_all(
        [
            source,
            TenantDataset(
                tenant_id=tenant.id,
                dataset_key="literature",
                display_name="Literature",
                license_policy=internal_evidence_license_policy(source="real-smb-acceptance"),
            ),
        ]
    )
    session.commit()
    service = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
    )

    preflight_connector = SourceConnectorRegistry(settings).get(DataSourceType.SMB_SNAPSHOT)
    preflight = preflight_connector.discover(source)
    assert len(preflight.objects) == 2, preflight.errors
    initial = service.scan_source(source.id, "real-smb-initial")
    session.refresh(source)
    assert initial.state == "succeeded", source.last_error
    assert len(initial.version_ids) == 2
    pending_retry = service.scan_source(source.id, "real-smb-pending-retry")
    assert pending_retry.state == "succeeded"
    assert pending_retry.version_ids == initial.version_ids
    assert pending_retry.unchanged == 0
    assert session.scalar(select(func.count()).select_from(SourceVersion)) == 2
    for version_id in initial.version_ids:
        version = session.get(SourceVersion, version_id)
        assert version is not None
        version.state = SourceVersionState.PARSED
        version.snapshot_status = StageStatus.SUCCEEDED
    session.commit()
    unchanged = service.scan_source(source.id, "real-smb-unchanged")
    assert unchanged.state == "succeeded"
    assert unchanged.unchanged == 2

    connector = SourceConnectorRegistry(settings).get(DataSourceType.SMB_SNAPSHOT)
    stale_item = next(item for item in connector.discover(source).objects if item.logical_path == "egfr.md")
    egfr_path = source_directory / "egfr.md"
    updated_egfr = b"EGFR licensed SMB evidence v2"
    egfr_path.write_bytes(updated_egfr)
    changed_timestamp = datetime(2026, 7, 17, 12, 1, tzinfo=UTC).timestamp()
    os.utime(egfr_path, (changed_timestamp, changed_timestamp))
    with pytest.raises(ConnectorTransportError, match="changed after discovery"):
        with connector.materialize(stale_item):
            pass

    original_timestamp = float(required_environment("TEST_SMB_SOURCE_FILE_TIMESTAMP"))
    os.utime(egfr_path, (original_timestamp, original_timestamp))
    changed = service.scan_source(source.id, "real-smb-same-metadata-content-changed")
    assert changed.state == "succeeded"
    assert len(changed.version_ids) == 1
    egfr_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "egfr.md"))
    assert egfr_asset is not None
    assert (
        session.scalar(select(func.count(SourceVersion.id)).where(SourceVersion.source_asset_id == egfr_asset.id)) == 2
    )

    (source_directory / "mapk.md").unlink()
    deleted = service.scan_source(source.id, "real-smb-deleted")
    assert deleted.state == "succeeded"
    mapk_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "mapk.md"))
    assert mapk_asset is not None and mapk_asset.state == SourceAssetState.MISSING
    version_count = session.scalar(select(func.count()).select_from(SourceVersion))

    monkeypatch.setenv(
        CREDENTIAL_ENV,
        json.dumps({"username": "sourceuser", "password": "wrong-password"}, separators=(",", ":")),
    )
    unavailable = service.scan_source(source.id, "real-smb-unavailable")
    session.refresh(source)
    assert unavailable.state == "failed"
    assert source.state == DataSourceState.UNAVAILABLE
    assert session.scalar(select(func.count()).select_from(SourceVersion)) == version_count

    monkeypatch.setenv(CREDENTIAL_ENV, credential_json)
    recovered = service.scan_source(source.id, "real-smb-recovered")
    recovered_source = session.get(DataSource, source.id)
    session.refresh(egfr_asset)
    assert recovered.state == "succeeded"
    assert recovered_source is not None and recovered_source.state == DataSourceState.ACTIVE
    assert egfr_asset.state == SourceAssetState.ACTIVE
    assert session.scalar(select(func.count()).select_from(SourceVersion)) == version_count
