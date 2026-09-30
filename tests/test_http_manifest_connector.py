from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TypedDict
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import ConnectorConfigurationError, SourceConnectorRegistry
from pharma_intel.ingest.data_factory import DataFactoryService
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import DataSource, DataSourceType, SourceAsset, SourceAssetState, Tenant, TenantDataset
from pharma_intel.object_store import FileSystemObjectStore

TOKEN_ENV_NAME = "TEST_HTTP_MANIFEST_TOKEN"  # noqa: S105
TOKEN = "local-protocol-token"  # noqa: S105
INITIAL_DOCUMENT = b"EGFR is a receptor tyrosine kinase."
SAME_METADATA_UPDATE = b"X" * len(INITIAL_DOCUMENT)
ASSET_DOCUMENT = b"compound asset"
INCREMENTAL_DOCUMENT = b"Osimertinib inhibits EGFR mutants."


class RequestRecord(TypedDict):
    path: str
    query: dict[str, list[str]]
    authorized: bool


@dataclass
class ManifestServerState:
    origin: str = ""
    mode: str = "initial"
    requests: list[RequestRecord] = field(default_factory=list)

    def manifest(self, query: dict[str, list[str]]) -> dict[str, object]:
        if self.mode == "same_metadata_update":
            return {
                "schema_version": "1.0",
                "items": [self.item("literature/egfr.md", SAME_METADATA_UPDATE)],
                "next_page_token": None,
                "next_cursor": "cursor-3",
            }
        if self.mode in {"incremental_corrupt", "incremental_valid"}:
            return {
                "schema_version": "1.0",
                "items": [
                    self.item("incremental/new-evidence.md", INCREMENTAL_DOCUMENT),
                    {
                        "operation": "delete",
                        "logical_path": "chemistry/compound.sdf",
                        "modified_at": "2026-07-17T13:00:00Z",
                    },
                ],
                "next_page_token": None,
                "next_cursor": "cursor-2",
            }
        if query.get("page_token") == ["page-2"]:
            return {
                "schema_version": "1.0",
                "items": [self.item("chemistry/compound.sdf", ASSET_DOCUMENT)],
                "next_page_token": None,
                "next_cursor": "cursor-1",
            }
        return {
            "schema_version": "1.0",
            "items": [self.item("literature/egfr.md", INITIAL_DOCUMENT)],
            "next_page_token": "page-2",
            "next_cursor": None,
        }

    def item(self, logical_path: str, content: bytes) -> dict[str, object]:
        download_url = f"{self.origin}/objects/{Path(logical_path).name}"
        if self.mode == "cross_origin":
            download_url = "https://unapproved.example/object.md"
        return {
            "operation": "upsert",
            "logical_path": logical_path,
            "download_url": download_url,
            "file_name": Path(logical_path).name,
            "size_bytes": len(content),
            "modified_at": "2026-07-17T12:00:00Z",
            "content_sha256": hashlib.sha256(content).hexdigest(),
        }

    def object_bytes(self, path: str) -> bytes | None:
        content_by_path = {
            "/objects/egfr.md": INITIAL_DOCUMENT,
            "/objects/compound.sdf": ASSET_DOCUMENT,
            "/objects/new-evidence.md": INCREMENTAL_DOCUMENT,
        }
        content = content_by_path.get(path)
        if self.mode == "same_metadata_update" and path == "/objects/egfr.md":
            return SAME_METADATA_UPDATE
        if content is not None and self.mode == "incremental_corrupt" and path == "/objects/new-evidence.md":
            return b"x" * len(content)
        return content


@pytest.fixture
def manifest_server() -> Iterator[ManifestServerState]:
    state = ManifestServerState()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlsplit(self.path)
            authorized = self.headers.get("Authorization") == f"Bearer {TOKEN}"
            state.requests.append(
                {
                    "path": parsed.path,
                    "query": parse_qs(parsed.query),
                    "authorized": authorized,
                }
            )
            if not authorized:
                self.send_error(401)
                return
            if parsed.path == "/manifest":
                payload = json.dumps(state.manifest(parse_qs(parsed.query))).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            content = state.object_bytes(parsed.path)
            if content is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    state.origin = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _settings(tmp_path: Path, state: ManifestServerState) -> Settings:
    return Settings(
        source_roots_config=str(tmp_path),
        source_credential_env_allowlist_config=TOKEN_ENV_NAME,
        source_http_allowed_origins_config=state.origin,
        source_http_allow_insecure_loopback=True,
        source_http_connect_timeout_seconds=2,
        source_http_read_timeout_seconds=2,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )


def _source(tenant_id: str, state: ManifestServerState) -> DataSource:
    return DataSource(
        id="http-source",
        tenant_id=tenant_id,
        name="Supplier API",
        source_type=DataSourceType.HTTP_MANIFEST,
        root_uri=f"{state.origin}/manifest",
        credential_ref=f"env://{TOKEN_ENV_NAME}",
        owner="Scientific Data Operations",
        data_classification="confidential",
        authorization_scopes=["contract:supplier-api"],
        dataset_key="literature",
        include_globs=["*", "**/*"],
        exclude_globs=[],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=60,
        expected_freshness_seconds=3600,
        rate_limit_per_minute=100_000,
        connector_cursor={
            "schema_version": "1.0",
            "kind": "http_manifest",
            "token": "previous-cursor",
        },
    )


def test_http_manifest_connector_uses_real_paginated_protocol_and_verified_download(
    manifest_server: ManifestServerState,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TOKEN_ENV_NAME, TOKEN)
    settings = _settings(tmp_path, manifest_server)
    connector = SourceConnectorRegistry(settings).get(DataSourceType.HTTP_MANIFEST)
    batch = connector.discover(_source(tenant.id, manifest_server))

    assert [item.logical_path for item in batch.objects] == [
        "chemistry/compound.sdf",
        "literature/egfr.md",
    ]
    assert batch.cursor["token"] == "cursor-1"  # noqa: S105
    assert batch.cursor["object_count"] == 2
    manifest_requests = [request for request in manifest_server.requests if request["path"] == "/manifest"]
    assert manifest_requests[0]["query"] == {"cursor": ["previous-cursor"]}
    assert manifest_requests[1]["query"] == {
        "cursor": ["previous-cursor"],
        "page_token": ["page-2"],
    }
    assert all(request["authorized"] is True for request in manifest_requests)
    invalid_stability_source = _source(tenant.id, manifest_server)
    invalid_stability_source.stable_seconds = 30
    assert connector.validate_configuration(invalid_stability_source) == [
        "HTTP manifest sources require stable_seconds=0"
    ]

    evidence = next(item for item in batch.objects if item.file_name == "egfr.md")
    with connector.materialize(evidence) as materialized:
        snapshot = materialized
        assert materialized.read_bytes() == INITIAL_DOCUMENT
    assert not snapshot.exists()


def test_http_manifest_connector_rejects_cross_origin_downloads(
    manifest_server: ManifestServerState,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TOKEN_ENV_NAME, TOKEN)
    manifest_server.mode = "cross_origin"
    connector = SourceConnectorRegistry(_settings(tmp_path, manifest_server)).get(DataSourceType.HTTP_MANIFEST)

    with pytest.raises(ConnectorConfigurationError, match="must use the manifest origin"):
        connector.discover(_source(tenant.id, manifest_server))


def test_data_factory_replays_failed_http_increment_without_advancing_cursor(
    manifest_server: ManifestServerState,
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(TOKEN_ENV_NAME, TOKEN)
    settings = _settings(tmp_path, manifest_server)
    source = _source(tenant.id, manifest_server)
    source.connector_cursor = {}
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

    initial = service.scan_source(source.id, "http-workflow-initial")
    session.refresh(source)
    assert initial.state == "succeeded"
    assert source.connector_cursor["token"] == "cursor-1"  # noqa: S105
    initial_success_at = source.last_success_at

    manifest_server.mode = "incremental_corrupt"
    partial = service.scan_source(source.id, "http-workflow-corrupt")
    session.refresh(source)
    assert partial.state == "partial"
    assert partial.failed == 1
    assert source.connector_cursor["token"] == "cursor-1"  # noqa: S105
    assert source.last_success_at == initial_success_at
    assert session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "incremental/new-evidence.md")) is None
    compound = session.scalar(select(SourceAsset).where(SourceAsset.logical_path == "chemistry/compound.sdf"))
    assert compound is not None and compound.state == SourceAssetState.ACTIVE

    manifest_server.mode = "incremental_valid"
    replayed = service.scan_source(source.id, "http-workflow-replayed")
    session.refresh(source)
    assert replayed.state == "succeeded"
    assert len(replayed.version_ids) == 1
    assert source.connector_cursor["token"] == "cursor-2"  # noqa: S105
    deleted_compound = session.get(SourceAsset, compound.id)
    assert deleted_compound is not None and deleted_compound.state == SourceAssetState.MISSING
    incremental_manifest_requests = [
        request
        for request in manifest_server.requests
        if request["path"] == "/manifest" and request["query"].get("cursor") == ["cursor-1"]
    ]
    assert len(incremental_manifest_requests) == 2

    manifest_server.mode = "same_metadata_update"
    hash_driven_update = service.scan_source(source.id, "http-workflow-hash-update")
    session.refresh(source)
    assert hash_driven_update.state == "succeeded"
    assert len(hash_driven_update.version_ids) == 1
    assert source.connector_cursor["token"] == "cursor-3"  # noqa: S105
