from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
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
    Tenant,
    TenantDataset,
)
from pharma_intel.object_store import FileSystemObjectStore

S3_CREDENTIAL_ENV = "TEST_S3_SOURCE_CREDENTIALS"
S3_BUCKET = "licensed-supplier"
MODIFIED_AT = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)


@dataclass
class FakeObject:
    payload: bytes
    modified_at: datetime = MODIFIED_AT

    @property
    def etag(self) -> str:
        return f'"{hashlib.sha256(self.payload).hexdigest()[:32]}"'


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, FakeObject] = {
            "research/literature/egfr.md": FakeObject(b"EGFR source evidence v1"),
            "research/literature/mapk.md": FakeObject(b"MAPK source evidence v1"),
            "research/installers/tool.exe": FakeObject(b"not research evidence"),
        }
        self.list_requests: list[dict[str, object]] = []
        self.get_requests: list[dict[str, object]] = []
        self.observed_client_options: list[dict[str, Any]] = []

    def list_objects_v2(self, **request: object) -> dict[str, object]:
        self.list_requests.append(request)
        prefix = str(request["Prefix"])
        keys = [key for key in sorted(self.objects) if key.startswith(prefix)]
        offset = int(str(request.get("ContinuationToken", "0")))
        maximum = request["MaxKeys"]
        assert isinstance(maximum, int)
        page_keys = keys[offset : offset + maximum]
        next_offset = offset + len(page_keys)
        return {
            "Contents": [
                {
                    "Key": key,
                    "Size": len(self.objects[key].payload),
                    "LastModified": self.objects[key].modified_at,
                    "ETag": self.objects[key].etag,
                }
                for key in page_keys
            ],
            "IsTruncated": next_offset < len(keys),
            **({"NextContinuationToken": str(next_offset)} if next_offset < len(keys) else {}),
        }

    def get_object(self, **request: object) -> dict[str, object]:
        self.get_requests.append(request)
        key = str(request["Key"])
        item = self.objects[key]
        if request.get("IfMatch") != item.etag:
            raise ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "object changed"}},
                "GetObject",
            )
        return {
            "Body": io.BytesIO(item.payload),
            "ContentLength": len(item.payload),
            "ETag": item.etag,
            "LastModified": item.modified_at,
        }

    def close(self) -> None:
        return


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=S3_CREDENTIAL_ENV,
        source_s3_allowed_buckets_config=S3_BUCKET,
        source_s3_endpoint_url="http://127.0.0.1:8333",
        source_s3_allow_insecure_loopback=True,
        source_s3_force_path_style=True,
        source_s3_page_size=2,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )


def _source(tenant_id: str) -> DataSource:
    return DataSource(
        id="s3-source",
        tenant_id=tenant_id,
        name="Supplier data lake",
        source_type=DataSourceType.S3_SNAPSHOT,
        root_uri=f"s3://{S3_BUCKET}/research/",
        credential_ref=f"env://{S3_CREDENTIAL_ENV}",
        owner="Scientific Data Operations",
        data_classification="confidential",
        authorization_scopes=["contract:supplier-s3"],
        dataset_key="literature",
        include_globs=["*", "**/*"],
        exclude_globs=[],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=60,
        expected_freshness_seconds=3600,
        rate_limit_per_minute=100_000,
    )


@pytest.fixture
def s3_environment(monkeypatch: pytest.MonkeyPatch) -> FakeS3Client:
    client = FakeS3Client()
    credentials = {
        "access_key_id": "source-access-key",
        "secret_access_key": "source-secret-key",
        "session_token": "short-lived-session-token",
    }
    monkeypatch.setenv(S3_CREDENTIAL_ENV, json.dumps(credentials, separators=(",", ":")))

    def client_factory(_service: str, **options: Any) -> FakeS3Client:
        client.observed_client_options.append(options)
        return client

    monkeypatch.setattr("pharma_intel.ingest.connectors.boto3.client", client_factory)
    return client


def test_s3_snapshot_connector_paginates_and_uses_conditional_streaming_get(
    tenant: Tenant,
    tmp_path: Path,
    s3_environment: FakeS3Client,
) -> None:
    connector = SourceConnectorRegistry(_settings(tmp_path)).get(DataSourceType.S3_SNAPSHOT)
    source = _source(tenant.id)
    batch = connector.discover(source)

    assert [item.logical_path for item in batch.objects] == ["literature/egfr.md", "literature/mapk.md"]
    assert batch.authoritative_inventory is True
    assert batch.excluded_count == 1
    assert batch.cursor["kind"] == "s3_inventory"
    assert batch.cursor["object_count"] == 2
    assert len(s3_environment.list_requests) == 2
    assert s3_environment.list_requests[1]["ContinuationToken"] == "2"

    evidence = batch.objects[0]
    with connector.materialize(evidence) as materialized:
        snapshot = materialized
        assert materialized.read_bytes() == b"EGFR source evidence v1"
    assert not snapshot.exists()
    assert s3_environment.get_requests[-1]["IfMatch"] == '"b52403ec2a8f562ec82836f661b4cbdb"'
    client_options = s3_environment.observed_client_options
    assert client_options[0]["aws_access_key_id"] == "source-access-key"
    assert client_options[0]["aws_secret_access_key"] == "source-secret-key"  # noqa: S105

    s3_environment.objects["research/literature/egfr.md"] = FakeObject(b"EGFR source evidence v2")
    with pytest.raises(ConnectorTransportError, match="PreconditionFailed"):
        with connector.materialize(evidence):
            pass


def test_s3_snapshot_connector_enforces_bucket_endpoint_and_credential_policy(
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(tenant.id)
    monkeypatch.setenv(S3_CREDENTIAL_ENV, "not-json")
    connector = SourceConnectorRegistry(_settings(tmp_path)).get(DataSourceType.S3_SNAPSHOT)
    assert connector.validate_configuration(source) == ["S3 credential payload does not match the required JSON schema"]

    monkeypatch.setenv(
        S3_CREDENTIAL_ENV,
        json.dumps({"access_key_id": "access", "secret_access_key": "secret"}),
    )
    invalid_cursor = _source(tenant.id)
    invalid_cursor.connector_cursor = {
        "schema_version": "1.0",
        "kind": "s3_inventory",
        "inventory_sha256": "0" * 64,
        "object_count": True,
    }
    assert connector.validate_configuration(invalid_cursor) == ["S3 snapshot connector cursor is invalid"]

    disallowed = _source(tenant.id)
    disallowed.root_uri = "s3://unapproved-bucket/research/"
    assert connector.validate_configuration(disallowed) == [
        "S3 source bucket is not present in SOURCE_S3_ALLOWED_BUCKETS"
    ]

    unsafe_settings = _settings(tmp_path).model_copy(update={"source_s3_endpoint_url": "http://supplier.example:8333"})
    unsafe_connector = SourceConnectorRegistry(unsafe_settings).get(DataSourceType.S3_SNAPSHOT)
    assert unsafe_connector.validate_configuration(source) == ["SOURCE_S3_ENDPOINT_URL must use HTTPS"]


def test_data_factory_uses_s3_fingerprint_and_authoritative_inventory(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    s3_environment: FakeS3Client,
) -> None:
    settings = _settings(tmp_path)
    source = _source(tenant.id)
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
    service = DataFactoryService(
        session,
        settings,
        FileSystemObjectStore(settings.object_store_root),
        tenant.id,
    )

    initial = service.scan_source(source.id, "s3-initial")
    assert initial.state == "succeeded"
    assert len(initial.version_ids) == 2
    for version_id in initial.version_ids:
        version = session.get(SourceVersion, version_id)
        assert version is not None
        version.state = SourceVersionState.PARSED
    session.commit()
    discovered_again = SourceConnectorRegistry(settings).get(DataSourceType.S3_SNAPSHOT).discover(source)
    for item in discovered_again.objects:
        asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == item.logical_path))
        assert asset is not None and asset.current_version_id is not None
        current = session.get(SourceVersion, asset.current_version_id)
        assert current is not None and current.source_modified_at is not None
        stored_modified_at = current.source_modified_at
        if stored_modified_at.tzinfo is None:
            stored_modified_at = stored_modified_at.replace(tzinfo=UTC)
        assert stored_modified_at == item.modified_at
        assert asset.source_fingerprint == item.source_fingerprint

    unchanged = service.scan_source(source.id, "s3-unchanged")
    assert unchanged.state == "succeeded"
    assert unchanged.unchanged == 2
    get_count_before_change = len(s3_environment.get_requests)

    original = s3_environment.objects["research/literature/egfr.md"]
    replacement = b"EGFR source evidence v2"
    assert len(replacement) == len(original.payload)
    s3_environment.objects["research/literature/egfr.md"] = FakeObject(
        replacement,
        modified_at=original.modified_at,
    )
    changed = service.scan_source(source.id, "s3-same-metadata-change")
    assert changed.state == "succeeded"
    assert len(changed.version_ids) == 1
    assert len(s3_environment.get_requests) == get_count_before_change + 1
    egfr_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "literature/egfr.md"))
    assert egfr_asset is not None and egfr_asset.source_fingerprint is not None
    assert (
        session.scalar(select(func.count(SourceVersion.id)).where(SourceVersion.source_asset_id == egfr_asset.id)) == 2
    )

    del s3_environment.objects["research/literature/mapk.md"]
    deleted = service.scan_source(source.id, "s3-authoritative-delete")
    assert deleted.state == "succeeded"
    mapk_asset = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "literature/mapk.md"))
    assert mapk_asset is not None and mapk_asset.state == SourceAssetState.MISSING
