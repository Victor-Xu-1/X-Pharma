from __future__ import annotations

import io
import json
import os
import stat
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import smbclient  # type: ignore[import-untyped]
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import ConnectorTransportError, SMBSnapshotSourceConnector, SourceConnectorRegistry
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

CREDENTIAL_ENV = "TEST_SMB_SOURCE_CREDENTIALS"
ORIGIN = "smb://supplier.example:445"
MODIFIED_AT = datetime(2026, 7, 22, 7, 0, tzinfo=UTC)
REMOTE_ROOT = r"\\supplier.example\research\delivery"


class FakeSMBEntry:
    def __init__(self, runtime: FakeSMBRuntime, directory: str, name: str, kind: str) -> None:
        self.runtime = runtime
        self.directory = directory
        self.name = name
        self.kind = kind

    @property
    def path(self) -> str:
        return f"{self.directory}\\{self.name}"

    def is_symlink(self) -> bool:
        return self.kind == "link"

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        assert follow_symlinks is False
        return self.kind == "directory"

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        assert follow_symlinks is False
        return self.kind == "file"

    def stat(self, follow_symlinks: bool = True) -> SimpleNamespace:
        assert follow_symlinks is False
        return self.runtime.attributes(self.path)


class FakeSMBRuntime:
    def __init__(self) -> None:
        self.read_count = 0
        self.operation_ports: list[int] = []
        self.files: dict[str, tuple[bytes, datetime]] = {
            f"{REMOTE_ROOT}\\literature\\egfr.md": (b"EGFR SMB evidence v1", MODIFIED_AT),
            f"{REMOTE_ROOT}\\literature\\mapk.md": (b"MAPK SMB evidence v1", MODIFIED_AT),
            f"{REMOTE_ROOT}\\tool.exe": (b"excluded executable", MODIFIED_AT),
        }

    def entries(self, directory: str) -> list[FakeSMBEntry]:
        if directory == REMOTE_ROOT:
            return [
                FakeSMBEntry(self, directory, "literature", "directory"),
                FakeSMBEntry(self, directory, "latest", "link"),
                FakeSMBEntry(self, directory, "tool.exe", "file"),
            ]
        if directory == f"{REMOTE_ROOT}\\literature":
            return [
                FakeSMBEntry(self, directory, remote_path.rsplit("\\", maxsplit=1)[1], "file")
                for remote_path in sorted(self.files)
                if remote_path.startswith(f"{REMOTE_ROOT}\\literature\\")
            ]
        raise OSError("unexpected SMB directory")

    def attributes(self, remote_path: str) -> SimpleNamespace:
        payload, modified_at = self.files[remote_path]
        return SimpleNamespace(
            st_mode=stat.S_IFREG | 0o440,
            st_size=len(payload),
            st_mtime=modified_at.timestamp(),
        )

    def open_file(self, remote_path: str) -> io.BytesIO:
        self.read_count += 1
        return io.BytesIO(self.files[remote_path][0])


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=CREDENTIAL_ENV,
        source_smb_allowed_origins_config=ORIGIN,
        source_smb_require_encryption=True,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )


def _source(tenant_id: str) -> DataSource:
    return DataSource(
        id="smb-source",
        tenant_id=tenant_id,
        name="Enterprise SMB delivery",
        source_type=DataSourceType.SMB_SNAPSHOT,
        root_uri=f"{ORIGIN}/research/delivery/",
        credential_ref=f"env://{CREDENTIAL_ENV}",
        owner="Scientific Data Operations",
        data_classification="confidential",
        authorization_scopes=["contract:enterprise-smb"],
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
def smb_environment(monkeypatch: pytest.MonkeyPatch) -> FakeSMBRuntime:
    runtime = FakeSMBRuntime()
    monkeypatch.setenv(
        CREDENTIAL_ENV,
        json.dumps(
            {"username": "source-user", "password": "test-password", "domain": "RESEARCH"},
            separators=(",", ":"),
        ),
    )
    return runtime


def _bind_fake_runtime(monkeypatch: pytest.MonkeyPatch, connector: Any, runtime: FakeSMBRuntime) -> None:
    def record_port(kwargs: dict[str, object]) -> None:
        port = kwargs.get("port")
        assert isinstance(port, int)
        runtime.operation_ports.append(port)

    @contextmanager
    def session(_origin: str, _credential_ref: str) -> Any:
        yield {}

    @contextmanager
    def scandir(path: str, **kwargs: object) -> Any:
        record_port(kwargs)
        yield iter(runtime.entries(path))

    def smb_stat(path: str, **kwargs: object) -> SimpleNamespace:
        record_port(kwargs)
        return runtime.attributes(path)

    def open_file(path: str, **kwargs: object) -> io.BytesIO:
        record_port(kwargs)
        return runtime.open_file(path)

    monkeypatch.setattr(connector, "_session", session)
    monkeypatch.setattr(smbclient, "scandir", scandir)
    monkeypatch.setattr(smbclient, "stat", smb_stat)
    monkeypatch.setattr(smbclient, "open_file", open_file)


def test_smb_snapshot_discovers_without_following_links_and_materializes_atomically(
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    smb_environment: FakeSMBRuntime,
) -> None:
    connector = SourceConnectorRegistry(_settings(tmp_path)).get(DataSourceType.SMB_SNAPSHOT)
    assert isinstance(connector, SMBSnapshotSourceConnector)
    _bind_fake_runtime(monkeypatch, connector, smb_environment)
    source = _source(tenant.id)

    batch = connector.discover(source)

    assert [item.logical_path for item in batch.objects] == ["literature/egfr.md", "literature/mapk.md"]
    assert batch.authoritative_inventory is True
    assert batch.excluded_count == 2
    assert batch.cursor["kind"] == "smb_inventory"
    assert batch.cursor["object_count"] == 2
    evidence = batch.objects[0]
    assert evidence.source_uri == f"{ORIGIN}/research/delivery/literature/egfr.md"
    assert "source-user" not in evidence.source_uri
    with connector.materialize(evidence) as materialized:
        snapshot = materialized
        assert materialized.read_bytes() == b"EGFR SMB evidence v1"
    assert not snapshot.exists()
    assert set(smb_environment.operation_ports) == {445}

    payload, _ = smb_environment.files[f"{REMOTE_ROOT}\\literature\\egfr.md"]
    smb_environment.files[f"{REMOTE_ROOT}\\literature\\egfr.md"] = (
        payload,
        datetime(2026, 7, 22, 7, 1, tzinfo=UTC),
    )
    with pytest.raises(ConnectorTransportError, match="changed after discovery"):
        with connector.materialize(evidence):
            pass


def test_smb_snapshot_configuration_rejects_unapproved_or_unsafe_inputs(
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    smb_environment: FakeSMBRuntime,
) -> None:
    source = _source(tenant.id)
    connector = SourceConnectorRegistry(_settings(tmp_path)).get(DataSourceType.SMB_SNAPSHOT)
    assert connector.validate_configuration(source) == []

    disallowed = _source(tenant.id)
    disallowed.root_uri = "smb://unapproved.example/research/"
    assert connector.validate_configuration(disallowed)[0] == (
        "SMB source origin is not present in SOURCE_SMB_ALLOWED_ORIGINS"
    )
    credentials_in_uri = _source(tenant.id)
    credentials_in_uri.root_uri = "smb://user:secret@supplier.example/research/"
    assert connector.validate_configuration(credentials_in_uri)[0] == (
        "SMB source URI cannot contain credentials, query, or fragment"
    )
    traversal = _source(tenant.id)
    traversal.root_uri = f"{ORIGIN}/research/../private/"
    assert connector.validate_configuration(traversal)[0] == "SMB source path is not canonical"

    monkeypatch.setenv(CREDENTIAL_ENV, '{"username":"source-user","password":"secret","unexpected":true}')
    assert connector.validate_configuration(source)[0] == (
        "SMB credential payload does not match the required JSON schema"
    )


def test_smb_session_requires_signing_encryption_and_clears_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    smb_environment: FakeSMBRuntime,
) -> None:
    connector = SourceConnectorRegistry(_settings(tmp_path)).get(DataSourceType.SMB_SNAPSHOT)
    assert isinstance(connector, SMBSnapshotSourceConnector)
    observed: dict[str, object] = {}

    def register_session(server: str, **kwargs: object) -> None:
        observed.update({"server": server, **kwargs})

    def reset_connection_cache(**kwargs: object) -> None:
        observed["reset"] = kwargs

    monkeypatch.setattr(smbclient, "register_session", register_session)
    monkeypatch.setattr(smbclient, "reset_connection_cache", reset_connection_cache)

    with connector._session(ORIGIN, f"env://{CREDENTIAL_ENV}") as cache:
        assert cache == {}

    assert observed["server"] == "supplier.example"
    assert observed["username"] == r"RESEARCH\source-user"
    assert observed["password"] == json.loads(os.environ[CREDENTIAL_ENV])["password"]
    assert observed["encrypt"] is True
    assert observed["require_signing"] is True
    assert observed["port"] == 445
    assert isinstance(observed["reset"], dict)


def test_data_factory_uses_smb_fingerprint_and_authoritative_delete(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    smb_environment: FakeSMBRuntime,
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
                license_policy=internal_evidence_license_policy(source="smb-test"),
            ),
        ]
    )
    session.commit()
    service = DataFactoryService(session, settings, FileSystemObjectStore(settings.object_store_root), tenant.id)
    connector = service.connector_registry.get(DataSourceType.SMB_SNAPSHOT)
    _bind_fake_runtime(monkeypatch, connector, smb_environment)

    initial = service.scan_source(source.id, "smb-initial")
    assert initial.state == "succeeded"
    assert len(initial.version_ids) == 2
    for version_id in initial.version_ids:
        version = session.get(SourceVersion, version_id)
        assert version is not None
        version.state = SourceVersionState.PARSED
    session.commit()
    unchanged = service.scan_source(source.id, "smb-unchanged")
    assert unchanged.unchanged == 2

    remote_egfr = f"{REMOTE_ROOT}\\literature\\egfr.md"
    _, modified_at = smb_environment.files[remote_egfr]
    smb_environment.files[remote_egfr] = (b"EGFR SMB evidence v2", modified_at)
    changed = service.scan_source(source.id, "smb-same-metadata-change")
    assert len(changed.version_ids) == 1
    egfr = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "literature/egfr.md"))
    assert egfr is not None
    assert session.scalar(select(func.count(SourceVersion.id)).where(SourceVersion.source_asset_id == egfr.id)) == 2

    del smb_environment.files[f"{REMOTE_ROOT}\\literature\\mapk.md"]
    deleted = service.scan_source(source.id, "smb-deleted")
    assert deleted.state == "succeeded"
    mapk = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "literature/mapk.md"))
    assert mapk is not None and mapk.state == SourceAssetState.MISSING
