from __future__ import annotations

import io
import json
import stat
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import paramiko  # type: ignore[import-untyped]
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
    Tenant,
    TenantDataset,
)
from pharma_intel.object_store import FileSystemObjectStore

CREDENTIAL_ENV = "TEST_SFTP_SOURCE_CREDENTIALS"
ORIGIN = "sftp://supplier.example:2222"
MODIFIED_AT = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)


def _attributes(filename: str, mode: int, size: int = 0, modified_at: datetime = MODIFIED_AT) -> Any:
    item = paramiko.SFTPAttributes()
    item.filename = filename
    item.st_mode = mode
    item.st_size = size
    item.st_mtime = int(modified_at.timestamp())
    return item


class FakeSFTP:
    def __init__(self) -> None:
        self.read_count = 0
        self.files: dict[str, tuple[bytes, datetime]] = {
            "/delivery/literature/egfr.md": (b"EGFR SFTP evidence v1", MODIFIED_AT),
            "/delivery/literature/mapk.md": (b"MAPK SFTP evidence v1", MODIFIED_AT),
            "/delivery/tool.exe": (b"excluded executable", MODIFIED_AT),
        }

    def listdir_attr(self, directory: str) -> list[Any]:
        if directory == "/delivery/":
            return [
                _attributes("literature", stat.S_IFDIR | 0o755),
                _attributes("latest", stat.S_IFLNK | 0o777),
                self._file_attributes("tool.exe", "/delivery/tool.exe"),
            ]
        if directory == "/delivery/literature/":
            return [
                self._file_attributes(Path(remote_path).name, remote_path)
                for remote_path in sorted(self.files)
                if remote_path.startswith("/delivery/literature/")
            ]
        raise OSError("unexpected directory")

    def lstat(self, remote_path: str) -> Any:
        return self._file_attributes(Path(remote_path).name, remote_path)

    def file(self, remote_path: str, mode: str) -> io.BytesIO:
        assert mode == "rb"
        self.read_count += 1
        return io.BytesIO(self.files[remote_path][0])

    def _file_attributes(self, filename: str, remote_path: str) -> Any:
        payload, modified_at = self.files[remote_path]
        return _attributes(filename, stat.S_IFREG | 0o440, len(payload), modified_at)


def _known_hosts(tmp_path: Path, hostname: str = "supplier.example", port: int = 2222) -> Path:
    key = paramiko.RSAKey.generate(1024)
    path = tmp_path / "known_hosts"
    path.write_text(f"[{hostname}]:{port} {key.get_name()} {key.get_base64()}\n", encoding="ascii")
    return path


def _settings(tmp_path: Path, *, password_auth: bool = True) -> Settings:
    return Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=CREDENTIAL_ENV,
        source_sftp_allowed_origins_config=ORIGIN,
        source_sftp_known_hosts_path=str(_known_hosts(tmp_path)),
        source_sftp_allow_password_auth=password_auth,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )


def _source(tenant_id: str) -> DataSource:
    return DataSource(
        id="sftp-source",
        tenant_id=tenant_id,
        name="Supplier SFTP delivery",
        source_type=DataSourceType.SFTP_SNAPSHOT,
        root_uri=f"{ORIGIN}/delivery/",
        credential_ref=f"env://{CREDENTIAL_ENV}",
        owner="Scientific Data Operations",
        data_classification="confidential",
        authorization_scopes=["contract:supplier-sftp"],
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
def sftp_environment(monkeypatch: pytest.MonkeyPatch) -> FakeSFTP:
    fake = FakeSFTP()
    monkeypatch.setenv(
        CREDENTIAL_ENV,
        json.dumps({"username": "source-user", "password": "test-password"}, separators=(",", ":")),
    )
    return fake


def _bind_fake_session(monkeypatch: pytest.MonkeyPatch, connector: Any, fake: FakeSFTP) -> None:
    @contextmanager
    def session(_origin: str, _credential_ref: str) -> Any:
        yield fake

    monkeypatch.setattr(connector, "_session", session)


def test_sftp_snapshot_connector_discovers_without_following_links_and_snapshots_atomically(
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sftp_environment: FakeSFTP,
) -> None:
    connector = SourceConnectorRegistry(_settings(tmp_path)).get(DataSourceType.SFTP_SNAPSHOT)
    _bind_fake_session(monkeypatch, connector, sftp_environment)
    source = _source(tenant.id)

    batch = connector.discover(source)

    assert [item.logical_path for item in batch.objects] == ["literature/egfr.md", "literature/mapk.md"]
    assert batch.authoritative_inventory is True
    assert batch.excluded_count == 2
    assert batch.cursor["kind"] == "sftp_inventory"
    assert batch.cursor["object_count"] == 2
    evidence = batch.objects[0]
    assert evidence.source_uri == f"{ORIGIN}/delivery/literature/egfr.md"
    assert "source-user" not in evidence.source_uri
    with connector.materialize(evidence) as materialized:
        snapshot = materialized
        assert materialized.read_bytes() == b"EGFR SFTP evidence v1"
    assert not snapshot.exists()

    payload, _ = sftp_environment.files["/delivery/literature/egfr.md"]
    sftp_environment.files["/delivery/literature/egfr.md"] = (
        payload,
        datetime(2026, 7, 17, 12, 1, tzinfo=UTC),
    )
    with pytest.raises(ConnectorTransportError, match="changed after discovery"):
        with connector.materialize(evidence):
            pass


def test_sftp_snapshot_connector_fails_closed_on_origin_host_key_and_password_policy(
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sftp_environment: FakeSFTP,
) -> None:
    source = _source(tenant.id)
    settings = _settings(tmp_path)
    connector = SourceConnectorRegistry(settings).get(DataSourceType.SFTP_SNAPSHOT)
    assert connector.validate_configuration(source) == []

    invalid_cursor = _source(tenant.id)
    invalid_cursor.connector_cursor = {
        "schema_version": "1.0",
        "kind": "sftp_inventory",
        "inventory_sha256": "0" * 64,
        "object_count": True,
    }
    assert connector.validate_configuration(invalid_cursor) == ["SFTP snapshot connector cursor is invalid"]

    disallowed = _source(tenant.id)
    disallowed.root_uri = "sftp://unapproved.example:22/delivery/"
    assert connector.validate_configuration(disallowed)[0] == (
        "SFTP source origin is not present in SOURCE_SFTP_ALLOWED_ORIGINS"
    )

    invalid_idna = _source(tenant.id)
    invalid_idna.root_uri = f"sftp://{'a' * 64}.example:2222/delivery/"
    assert connector.validate_configuration(invalid_idna)[0] == "SFTP source URI is invalid"

    password_disabled = SourceConnectorRegistry(
        settings.model_copy(update={"source_sftp_allow_password_auth": False})
    ).get(DataSourceType.SFTP_SNAPSHOT)
    assert password_disabled.validate_configuration(source)[0] == "SFTP password authentication is not enabled"

    wrong_hosts = tmp_path / "wrong_known_hosts"
    wrong_hosts.write_text("", encoding="ascii")
    missing_host = SourceConnectorRegistry(
        settings.model_copy(update={"source_sftp_known_hosts_path": str(wrong_hosts)})
    ).get(DataSourceType.SFTP_SNAPSHOT)
    assert missing_host.validate_configuration(source)[0] == (
        "SFTP origin is missing from SOURCE_SFTP_KNOWN_HOSTS_PATH"
    )


def test_data_factory_uses_sftp_inventory_fingerprint_and_authoritative_delete(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sftp_environment: FakeSFTP,
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
    connector = service.connector_registry.get(DataSourceType.SFTP_SNAPSHOT)
    _bind_fake_session(monkeypatch, connector, sftp_environment)

    initial = service.scan_source(source.id, "sftp-initial")
    assert initial.state == "succeeded"
    assert len(initial.version_ids) == 2
    for version_id in initial.version_ids:
        version = session.get(SourceVersion, version_id)
        assert version is not None
        version.state = SourceVersionState.PARSED
    session.commit()
    reads_after_initial = sftp_environment.read_count
    unchanged = service.scan_source(source.id, "sftp-unchanged")
    assert unchanged.unchanged == 2
    assert sftp_environment.read_count == reads_after_initial + 2

    payload, _ = sftp_environment.files["/delivery/literature/egfr.md"]
    sftp_environment.files["/delivery/literature/egfr.md"] = (
        payload.replace(b"v1", b"v2"),
        MODIFIED_AT,
    )
    changed = service.scan_source(source.id, "sftp-same-metadata-change")
    assert len(changed.version_ids) == 1
    egfr = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "literature/egfr.md"))
    assert egfr is not None
    assert session.scalar(select(func.count(SourceVersion.id)).where(SourceVersion.source_asset_id == egfr.id)) == 2

    del sftp_environment.files["/delivery/literature/mapk.md"]
    deleted = service.scan_source(source.id, "sftp-deleted")
    assert deleted.state == "succeeded"
    mapk = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "literature/mapk.md"))
    assert mapk is not None and mapk.state == SourceAssetState.MISSING
