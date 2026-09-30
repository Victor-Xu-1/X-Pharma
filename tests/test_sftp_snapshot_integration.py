from __future__ import annotations

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
CREDENTIAL_ENV = "TEST_SFTP_SOURCE_CREDENTIAL_JSON"


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is required for the real SFTP protocol integration test")
    return value


def test_real_sftp_protocol_snapshot_versioning_race_and_authoritative_delete(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    origin = required_environment("TEST_SFTP_SOURCE_ORIGIN")
    known_hosts = required_environment("TEST_SFTP_SOURCE_KNOWN_HOSTS")
    source_directory = Path(required_environment("TEST_SFTP_SOURCE_DIRECTORY"))
    credential_json = required_environment(CREDENTIAL_ENV)
    monkeypatch.setenv(CREDENTIAL_ENV, credential_json)
    settings = Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=CREDENTIAL_ENV,
        source_sftp_allowed_origins_config=origin,
        source_sftp_known_hosts_path=known_hosts,
        source_sftp_connect_timeout_seconds=3,
        source_sftp_read_timeout_seconds=5,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Real SFTP protocol source",
        source_type=DataSourceType.SFTP_SNAPSHOT,
        root_uri=f"{origin}/data/",
        credential_ref=f"env://{CREDENTIAL_ENV}",
        owner="Acceptance Data Operations",
        data_classification="confidential",
        authorization_scopes=["contract:sftp-acceptance"],
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
                license_policy=internal_evidence_license_policy(source="real-sftp-acceptance"),
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

    initial = service.scan_source(source.id, "real-sftp-initial")
    assert initial.state == "succeeded"
    assert len(initial.version_ids) == 2
    pending_retry = service.scan_source(source.id, "real-sftp-pending-retry")
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
    unchanged = service.scan_source(source.id, "real-sftp-unchanged")
    assert unchanged.state == "succeeded"
    assert unchanged.unchanged == 2

    connector = SourceConnectorRegistry(settings).get(DataSourceType.SFTP_SNAPSHOT)
    stale_item = next(item for item in connector.discover(source).objects if item.logical_path == "egfr.md")
    updated_egfr = b"EGFR licensed SFTP evidence v2"
    egfr_path = source_directory / "egfr.md"
    egfr_path.write_bytes(updated_egfr)
    timestamp = datetime(2026, 7, 17, 12, 1, tzinfo=UTC).timestamp()
    os.utime(egfr_path, (timestamp, timestamp))
    with pytest.raises(ConnectorTransportError, match="changed after discovery"):
        with connector.materialize(stale_item):
            pass

    changed = service.scan_source(source.id, "real-sftp-changed")
    assert changed.state == "succeeded"
    assert len(changed.version_ids) == 1
    egfr_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "egfr.md"))
    assert egfr_asset is not None
    assert (
        session.scalar(select(func.count(SourceVersion.id)).where(SourceVersion.source_asset_id == egfr_asset.id)) == 2
    )

    (source_directory / "mapk.md").unlink()
    deleted = service.scan_source(source.id, "real-sftp-deleted")
    assert deleted.state == "succeeded"
    mapk_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "mapk.md"))
    assert mapk_asset is not None and mapk_asset.state == SourceAssetState.MISSING
