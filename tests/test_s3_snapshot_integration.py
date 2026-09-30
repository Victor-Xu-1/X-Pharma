from __future__ import annotations

import os
from pathlib import Path

import boto3  # type: ignore[import-untyped]
import pytest
from botocore.config import Config  # type: ignore[import-untyped]
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
CREDENTIAL_ENV = "TEST_S3_SOURCE_CREDENTIAL_JSON"


def required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is required for the real S3 protocol integration test")
    return value


def test_real_s3_protocol_snapshot_versioning_and_authoritative_delete(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = required_environment("TEST_S3_SOURCE_ENDPOINT")
    bucket = required_environment("TEST_S3_SOURCE_BUCKET")
    access_key = required_environment("TEST_S3_SOURCE_ACCESS_KEY")
    secret_key = required_environment("TEST_S3_SOURCE_SECRET_KEY")
    credential_json = required_environment(CREDENTIAL_ENV)
    monkeypatch.setenv(CREDENTIAL_ENV, credential_json)
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    initial_egfr = b"EGFR licensed evidence v1"
    updated_egfr = b"EGFR licensed evidence v2"
    mapk = b"MAPK licensed evidence"
    assert len(initial_egfr) == len(updated_egfr)
    client.put_object(Bucket=bucket, Key="research/egfr.md", Body=initial_egfr)
    client.put_object(Bucket=bucket, Key="research/mapk.md", Body=mapk)

    settings = Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=CREDENTIAL_ENV,
        source_s3_allowed_buckets_config=bucket,
        source_s3_endpoint_url=endpoint,
        source_s3_allow_insecure_loopback=True,
        source_s3_force_path_style=True,
        source_s3_page_size=1,
        source_s3_connect_timeout_seconds=2,
        source_s3_read_timeout_seconds=5,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Real S3 protocol source",
        source_type=DataSourceType.S3_SNAPSHOT,
        root_uri=f"s3://{bucket}/research/",
        credential_ref=f"env://{CREDENTIAL_ENV}",
        owner="Acceptance Data Operations",
        data_classification="confidential",
        authorization_scopes=["contract:s3-acceptance"],
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
                license_policy=internal_evidence_license_policy(source="real-s3-acceptance"),
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

    initial = service.scan_source(source.id, "real-s3-initial")
    assert initial.state == "succeeded"
    assert len(initial.version_ids) == 2
    pending_retry = service.scan_source(source.id, "real-s3-pending-retry")
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
    unchanged = service.scan_source(source.id, "real-s3-unchanged")
    assert unchanged.state == "succeeded"
    assert unchanged.unchanged == 2

    connector = SourceConnectorRegistry(settings).get(DataSourceType.S3_SNAPSHOT)
    stale_item = next(item for item in connector.discover(source).objects if item.logical_path == "egfr.md")
    client.put_object(Bucket=bucket, Key="research/egfr.md", Body=updated_egfr)
    with pytest.raises(ConnectorTransportError, match="PreconditionFailed"):
        with connector.materialize(stale_item):
            pass

    changed = service.scan_source(source.id, "real-s3-changed")
    assert changed.state == "succeeded"
    assert len(changed.version_ids) == 1
    egfr_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "egfr.md"))
    assert egfr_asset is not None
    assert (
        session.scalar(select(func.count(SourceVersion.id)).where(SourceVersion.source_asset_id == egfr_asset.id)) == 2
    )

    client.delete_object(Bucket=bucket, Key="research/mapk.md")
    deleted = service.scan_source(source.id, "real-s3-deleted")
    assert deleted.state == "succeeded"
    mapk_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "mapk.md"))
    assert mapk_asset is not None and mapk_asset.state == SourceAssetState.MISSING
    client.close()
