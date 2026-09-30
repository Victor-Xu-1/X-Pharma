from __future__ import annotations

import fnmatch
import hashlib
import io
import ipaddress
import json
import os
import posixpath
import re
import stat
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Protocol
from urllib.parse import SplitResult, quote, unquote, urljoin, urlsplit, urlunsplit

import boto3  # type: ignore[import-untyped]
import httpx
import paramiko  # type: ignore[import-untyped]
import smbclient  # type: ignore[import-untyped]
from botocore.config import Config as BotoConfig  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from smbprotocol.exceptions import SMBException  # type: ignore[import-untyped]

from pharma_intel.config import Settings
from pharma_intel.ingest.scanner import DiscoveryError, classify_path, scan_folder
from pharma_intel.ingest.source_roots import validate_folder_source_root
from pharma_intel.models import DataSource, DataSourceType
from pharma_intel.product import SOURCE_USER_AGENT

ENV_CREDENTIAL_PATTERN = re.compile(r"^env://([A-Z_][A-Z0-9_]*)$")
S3_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def _is_non_negative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _cursor_payload(value: object) -> dict[str, object] | None:
    if value is None:
        return {}
    return value if isinstance(value, dict) else None


class ConnectorConfigurationError(ValueError):
    pass


class ConnectorTransportError(OSError):
    pass


@dataclass(frozen=True)
class ConnectorCapabilities:
    connector_id: str
    incremental: bool
    replayable: bool
    credentials_required: bool
    immutable_snapshot_required: bool = True


@dataclass(frozen=True)
class SourceObject:
    logical_path: str
    source_uri: str
    file_name: str
    extension: str
    size_bytes: int
    modified_at: datetime
    processing_mode: str
    dataset_key: str
    content_sha256: str | None
    handle: object
    source_fingerprint: str | None = None
    always_materialize: bool = False


@dataclass(frozen=True)
class DiscoveryBatch:
    objects: list[SourceObject]
    errors: list[DiscoveryError]
    excluded_count: int
    cursor: dict[str, object]
    authoritative_inventory: bool = False
    deleted_paths: list[str] | None = None


class SourceCredentialResolver(Protocol):
    def validation_errors(self, reference: str | None) -> list[str]: ...

    def resolve_bearer_token(self, reference: str | None) -> str: ...

    def resolve_secret(self, reference: str | None) -> str: ...


class EnvironmentCredentialResolver:
    def __init__(self, allowed_names: frozenset[str], max_bytes: int = 16_384) -> None:
        self.allowed_names = allowed_names
        self.max_bytes = max_bytes

    def validation_errors(self, reference: str | None) -> list[str]:
        if not reference:
            return ["HTTP manifest sources require a credential reference"]
        match = ENV_CREDENTIAL_PATTERN.fullmatch(reference)
        if match is None:
            return ["Credential references must use env://VARIABLE_NAME"]
        variable_name = match.group(1)
        if variable_name not in self.allowed_names:
            return ["Credential reference is not present in SOURCE_CREDENTIAL_ENV_ALLOWLIST"]
        token = os.environ.get(variable_name)
        if not token:
            return ["Referenced source credential is not available to this service"]
        if any(character in token for character in ("\x00", "\r", "\n")):
            return ["Referenced source credential contains invalid characters"]
        if len(token.encode("utf-8")) > self.max_bytes:
            return ["Referenced source credential exceeds SOURCE_CREDENTIAL_MAX_BYTES"]
        return []

    def resolve_bearer_token(self, reference: str | None) -> str:
        errors = self.validation_errors(reference)
        if errors:
            raise ConnectorConfigurationError(errors[0])
        assert reference is not None
        match = ENV_CREDENTIAL_PATTERN.fullmatch(reference)
        assert match is not None
        return os.environ[match.group(1)]

    def resolve_secret(self, reference: str | None) -> str:
        return self.resolve_bearer_token(reference)


class SourceConnector(Protocol):
    source_type: DataSourceType
    capabilities: ConnectorCapabilities

    def normalize_root_uri(self, root_uri: str) -> str: ...

    def validate_configuration(self, source: DataSource) -> list[str]: ...

    def discover(self, source: DataSource) -> DiscoveryBatch: ...

    def materialize(self, item: SourceObject) -> AbstractContextManager[Path]: ...


class FolderSourceConnector:
    source_type = DataSourceType.FOLDER
    capabilities = ConnectorCapabilities(
        connector_id="folder-v1",
        incremental=True,
        replayable=True,
        credentials_required=False,
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def normalize_root_uri(self, root_uri: str) -> str:
        return str(
            validate_folder_source_root(
                Path(root_uri),
                self.settings.source_roots,
                require_existing=False,
            )
        )

    def validate_configuration(self, source: DataSource) -> list[str]:
        if source.credential_ref:
            return ["Folder sources cannot store a connector credential reference"]
        try:
            self.normalize_root_uri(source.root_uri)
        except ValueError as exc:
            return [str(exc)]
        return []

    def discover(self, source: DataSource) -> DiscoveryBatch:
        root = validate_folder_source_root(
            Path(source.root_uri),
            self.settings.source_roots,
            require_existing=True,
        )
        scan = scan_folder(
            root,
            source.max_file_bytes,
            source.dataset_key,
            source.include_globs,
            source.exclude_globs,
        )
        objects = [
            SourceObject(
                logical_path=item.relative_path,
                source_uri=str(item.path),
                file_name=item.path.name,
                extension=item.extension,
                size_bytes=item.size_bytes,
                modified_at=item.modified_at,
                processing_mode=item.mode,
                dataset_key=item.dataset_key,
                content_sha256=None,
                handle=item.path,
            )
            for item in scan.files
        ]
        inventory = [
            {
                "logical_path": item.logical_path,
                "modified_at": item.modified_at.isoformat(),
                "size_bytes": item.size_bytes,
            }
            for item in objects
        ]
        inventory_sha256 = _inventory_sha256(inventory)
        cursor: dict[str, object] = {
            "schema_version": "1.0",
            "kind": "folder_inventory",
            "inventory_sha256": inventory_sha256,
            "object_count": len(objects),
        }
        return DiscoveryBatch(
            objects=objects,
            errors=scan.errors,
            excluded_count=scan.excluded_count,
            cursor=cursor,
            authoritative_inventory=True,
            deleted_paths=[],
        )

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, Path):
            raise ConnectorConfigurationError("Folder connector received an invalid source-object handle")
        source_path = item.handle
        if source_path.is_symlink():
            raise ConnectorConfigurationError("Folder source object became a symbolic link after discovery")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(source_path, flags)
        except OSError as exc:
            raise ConnectorConfigurationError("Folder source object is no longer safely readable") from exc

        with tempfile.TemporaryDirectory(prefix="pharma-source-materialize-") as temporary:
            snapshot = Path(temporary) / f"snapshot{source_path.suffix.casefold()}"
            try:
                with os.fdopen(descriptor, "rb") as source, snapshot.open("xb") as destination:
                    before = os.fstat(source.fileno())
                    observed_modified_at = datetime.fromtimestamp(before.st_mtime, UTC)
                    if before.st_size != item.size_bytes or observed_modified_at != item.modified_at:
                        raise ConnectorConfigurationError("Folder source object changed after discovery")
                    copied = 0
                    while chunk := source.read(min(1024 * 1024, item.size_bytes + 1 - copied)):
                        destination.write(chunk)
                        copied += len(chunk)
                        if copied > item.size_bytes:
                            raise ConnectorConfigurationError("Folder source object grew during materialization")
                    destination.flush()
                    os.fsync(destination.fileno())
                    after = os.fstat(source.fileno())
                observed_state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                final_state = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                if observed_state != final_state or snapshot.stat().st_size != before.st_size:
                    raise ConnectorConfigurationError("Folder source object changed during materialization")
            except Exception:
                snapshot.unlink(missing_ok=True)
                raise
            yield snapshot


class HttpManifestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["upsert"] = "upsert"
    logical_path: str = Field(min_length=1, max_length=4000)
    download_url: str = Field(min_length=1, max_length=8000)
    file_name: str = Field(min_length=1, max_length=1000)
    size_bytes: int = Field(ge=0, le=10_737_418_240)
    modified_at: datetime
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("modified_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("modified_at must include a timezone")
        return value.astimezone(UTC)


class HttpManifestDeleteItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["delete"]
    logical_path: str = Field(min_length=1, max_length=4000)
    modified_at: datetime

    @field_validator("modified_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("modified_at must include a timezone")
        return value.astimezone(UTC)


class HttpManifestPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    items: list[Annotated[HttpManifestItem | HttpManifestDeleteItem, Field(discriminator="operation")]] = Field(
        max_length=1000
    )
    next_page_token: str | None = Field(default=None, min_length=1, max_length=4096)
    next_cursor: str | None = Field(default=None, min_length=1, max_length=4096)

    @model_validator(mode="after")
    def validate_cursor_position(self) -> HttpManifestPage:
        if self.next_page_token is not None and self.next_cursor is not None:
            raise ValueError("next_cursor is only valid on the final manifest page")
        if self.next_page_token is None and self.next_cursor is None:
            raise ValueError("The final manifest page must provide next_cursor")
        return self


@dataclass(frozen=True)
class HttpManifestObjectHandle:
    download_url: str
    content_sha256: str
    expected_size_bytes: int
    credential_ref: str
    source_id: str
    rate_limit_per_minute: int


class _SourceRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request_at: dict[str, float] = {}

    def wait(self, source_id: str, requests_per_minute: int) -> None:
        minimum_interval = 60.0 / requests_per_minute
        with self._lock:
            now = time.monotonic()
            wait_seconds = minimum_interval - (now - self._last_request_at.get(source_id, 0.0))
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_at[source_id] = time.monotonic()


class HttpManifestSourceConnector:
    source_type = DataSourceType.HTTP_MANIFEST
    capabilities = ConnectorCapabilities(
        connector_id="http-manifest-v1",
        incremental=True,
        replayable=True,
        credentials_required=True,
    )

    def __init__(
        self,
        settings: Settings,
        credential_resolver: SourceCredentialResolver,
    ) -> None:
        self.settings = settings
        self.credential_resolver = credential_resolver
        self.rate_limiter = _SourceRateLimiter()

    def normalize_root_uri(self, root_uri: str) -> str:
        return _normalize_manifest_url(root_uri, self.settings)

    def validate_configuration(self, source: DataSource) -> list[str]:
        errors: list[str] = []
        if source.stable_seconds != 0:
            errors.append("HTTP manifest sources require stable_seconds=0")
        try:
            self.normalize_root_uri(source.root_uri)
        except ValueError as exc:
            errors.append(str(exc))
        errors.extend(self.credential_resolver.validation_errors(source.credential_ref))
        cursor = _cursor_payload(source.connector_cursor)
        if cursor is None or (
            cursor
            and (
                cursor.get("schema_version") != "1.0"
                or cursor.get("kind") != "http_manifest"
                or not isinstance(cursor.get("token"), str)
                or not cursor.get("token")
                or len(str(cursor.get("token"))) > 4096
            )
        ):
            errors.append("HTTP manifest connector cursor is invalid")
        return errors

    def discover(self, source: DataSource) -> DiscoveryBatch:
        configuration_errors = self.validate_configuration(source)
        if configuration_errors:
            raise ConnectorConfigurationError(configuration_errors[0])
        root_uri = self.normalize_root_uri(source.root_uri)
        prior_cursor = _cursor_payload(source.connector_cursor)
        assert prior_cursor is not None
        cursor_token = str(prior_cursor["token"]) if prior_cursor else None
        page_token: str | None = None
        seen_page_tokens: set[str] = set()
        seen_paths: set[str] = set()
        objects: list[SourceObject] = []
        deleted_paths: list[str] = []
        inventory: list[dict[str, object]] = []
        excluded_count = 0
        final_cursor: str | None = None

        for _ in range(self.settings.source_http_max_pages):
            page = self._fetch_page(source, root_uri, cursor_token, page_token)
            for manifest_item in page.items:
                logical_path = _normalize_logical_path(manifest_item.logical_path)
                if logical_path in seen_paths:
                    raise ConnectorConfigurationError("HTTP manifest contains a duplicate logical_path")
                seen_paths.add(logical_path)
                if isinstance(manifest_item, HttpManifestDeleteItem):
                    deleted_paths.append(logical_path)
                    inventory.append(
                        {
                            "logical_path": logical_path,
                            "modified_at": manifest_item.modified_at.isoformat(),
                            "operation": "delete",
                        }
                    )
                    continue
                if manifest_item.file_name != PurePosixPath(logical_path).name:
                    raise ConnectorConfigurationError("HTTP manifest file_name must match logical_path")
                processing_mode = classify_path(Path(manifest_item.file_name))
                if (
                    processing_mode == "exclude"
                    or manifest_item.size_bytes > source.max_file_bytes
                    or not _matches(logical_path, source.include_globs)
                    or _matches(logical_path, source.exclude_globs)
                ):
                    excluded_count += 1
                    continue
                download_url = _normalize_download_url(root_uri, manifest_item.download_url)
                source_uri = f"{root_uri}#{quote(logical_path, safe='/')}"
                objects.append(
                    SourceObject(
                        logical_path=logical_path,
                        source_uri=source_uri,
                        file_name=manifest_item.file_name,
                        extension=Path(manifest_item.file_name).suffix.casefold(),
                        size_bytes=manifest_item.size_bytes,
                        modified_at=manifest_item.modified_at,
                        processing_mode=processing_mode,
                        dataset_key=source.dataset_key,
                        content_sha256=manifest_item.content_sha256,
                        handle=HttpManifestObjectHandle(
                            download_url=download_url,
                            content_sha256=manifest_item.content_sha256,
                            expected_size_bytes=manifest_item.size_bytes,
                            credential_ref=source.credential_ref or "",
                            source_id=source.id,
                            rate_limit_per_minute=source.rate_limit_per_minute,
                        ),
                    )
                )
                inventory.append(
                    {
                        "content_sha256": manifest_item.content_sha256,
                        "logical_path": logical_path,
                        "modified_at": manifest_item.modified_at.isoformat(),
                        "operation": "upsert",
                        "size_bytes": manifest_item.size_bytes,
                    }
                )
            if page.next_page_token is None:
                final_cursor = page.next_cursor
                break
            if page.next_page_token in seen_page_tokens:
                raise ConnectorConfigurationError("HTTP manifest pagination token repeated")
            seen_page_tokens.add(page.next_page_token)
            page_token = page.next_page_token
        else:
            raise ConnectorConfigurationError("HTTP manifest exceeded SOURCE_HTTP_MAX_PAGES")

        assert final_cursor is not None
        objects.sort(key=lambda item: item.logical_path.casefold())
        inventory.sort(key=lambda item: str(item["logical_path"]).casefold())
        return DiscoveryBatch(
            objects=objects,
            errors=[],
            excluded_count=excluded_count,
            cursor={
                "schema_version": "1.0",
                "kind": "http_manifest",
                "token": final_cursor,
                "inventory_sha256": _inventory_sha256(inventory),
                "object_count": len(objects),
                "deleted_count": len(deleted_paths),
            },
            authoritative_inventory=False,
            deleted_paths=deleted_paths,
        )

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, HttpManifestObjectHandle):
            raise ConnectorConfigurationError("HTTP connector received an invalid source-object handle")
        handle = item.handle
        if item.size_bytes != handle.expected_size_bytes:
            raise ConnectorConfigurationError("HTTP source-object size contract changed after discovery")
        token = self.credential_resolver.resolve_bearer_token(handle.credential_ref)
        self.rate_limiter.wait(handle.source_id, handle.rate_limit_per_minute)
        with tempfile.TemporaryDirectory(prefix="pharma-http-materialize-") as temporary:
            snapshot = Path(temporary) / f"snapshot{item.extension}"
            digest = hashlib.sha256()
            copied = 0
            try:
                with self._client() as client:
                    with client.stream(
                        "GET",
                        handle.download_url,
                        headers=_request_headers(token),
                    ) as response:
                        _require_success(response, "HTTP source object")
                        _validate_content_length(response, handle.expected_size_bytes)
                        with snapshot.open("xb") as destination:
                            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                                copied += len(chunk)
                                if copied > handle.expected_size_bytes:
                                    raise ConnectorTransportError("HTTP source object exceeded its declared size")
                                destination.write(chunk)
                                digest.update(chunk)
                            destination.flush()
                            os.fsync(destination.fileno())
            except httpx.HTTPError as exc:
                snapshot.unlink(missing_ok=True)
                raise ConnectorTransportError("HTTP source object request failed") from exc
            except Exception:
                snapshot.unlink(missing_ok=True)
                raise
            if copied != handle.expected_size_bytes:
                raise ConnectorTransportError("HTTP source object size did not match its manifest")
            if digest.hexdigest() != handle.content_sha256:
                raise ConnectorTransportError("HTTP source object SHA-256 did not match its manifest")
            yield snapshot

    def _fetch_page(
        self,
        source: DataSource,
        root_uri: str,
        cursor_token: str | None,
        page_token: str | None,
    ) -> HttpManifestPage:
        token = self.credential_resolver.resolve_bearer_token(source.credential_ref)
        params: dict[str, str] = {}
        if cursor_token is not None:
            params["cursor"] = cursor_token
        if page_token is not None:
            params["page_token"] = page_token
        self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
        try:
            with self._client() as client:
                with client.stream(
                    "GET",
                    root_uri,
                    params=params,
                    headers=_request_headers(token),
                ) as response:
                    _require_success(response, "HTTP manifest")
                    content_type = response.headers.get("content-type", "").partition(";")[0].strip().casefold()
                    if content_type != "application/json":
                        raise ConnectorTransportError("HTTP manifest response must use application/json")
                    payload = _read_bounded(response, self.settings.source_http_max_manifest_bytes)
        except httpx.HTTPError as exc:
            raise ConnectorTransportError("HTTP manifest request failed") from exc
        try:
            decoded = json.loads(payload)
            return HttpManifestPage.model_validate(decoded)
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
            raise ConnectorConfigurationError("HTTP manifest response does not match schema version 1.0") from exc

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(
                connect=self.settings.source_http_connect_timeout_seconds,
                read=self.settings.source_http_read_timeout_seconds,
                write=self.settings.source_http_read_timeout_seconds,
                pool=self.settings.source_http_connect_timeout_seconds,
            ),
            follow_redirects=False,
            trust_env=False,
        )


CLINICALTRIALS_GOV_STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"
CLINICALTRIALS_GOV_STUDY_URL = "https://clinicaltrials.gov/study"
CLINICALTRIALS_GOV_NCT_ID = re.compile(r"^NCT[0-9]{8}$")
ClinicalTrialsGovSort = Literal[
    "LastUpdatePostDate:asc",
    "LastUpdatePostDate:desc",
    "StudyFirstPostDate:asc",
    "StudyFirstPostDate:desc",
]


class ClinicalTrialsGovRoutingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_term: str = Field(min_length=1, max_length=1000)
    max_records: int = Field(default=100, ge=1, le=1000)
    page_size: int = Field(default=100, ge=1, le=1000)
    sort: ClinicalTrialsGovSort = "LastUpdatePostDate:desc"

    @field_validator("query_term")
    @classmethod
    def normalize_query_term(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or any(character in normalized for character in ("\x00", "\r", "\n")):
            raise ValueError("query_term contains invalid characters")
        return normalized


class ClinicalTrialsGovPage(BaseModel):
    model_config = ConfigDict(extra="allow")

    studies: list[dict[str, Any]] = Field(max_length=1000)
    nextPageToken: str | None = Field(default=None, min_length=1, max_length=4096)
    totalCount: int | None = Field(default=None, ge=0)


@dataclass(frozen=True)
class ClinicalTrialsGovObjectHandle:
    content: bytes


class ClinicalTrialsGovSourceConnector:
    source_type = DataSourceType.CLINICALTRIALS_GOV
    capabilities = ConnectorCapabilities(
        connector_id="clinicaltrials-gov-v2",
        incremental=True,
        replayable=True,
        credentials_required=False,
    )

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport
        self.rate_limiter = _SourceRateLimiter()

    def normalize_root_uri(self, root_uri: str) -> str:
        if root_uri.strip() != CLINICALTRIALS_GOV_STUDIES_URL:
            raise ConnectorConfigurationError(f"ClinicalTrials.gov sources must use {CLINICALTRIALS_GOV_STUDIES_URL}")
        return CLINICALTRIALS_GOV_STUDIES_URL

    def validate_configuration(self, source: DataSource) -> list[str]:
        errors: list[str] = []
        try:
            self.normalize_root_uri(source.root_uri)
        except ValueError as exc:
            errors.append(str(exc))
        if source.credential_ref:
            errors.append("ClinicalTrials.gov sources do not accept connector credentials")
        if source.data_classification != "public":
            errors.append("ClinicalTrials.gov sources must use the public data classification")
        if "public:clinicaltrials-gov" not in source.authorization_scopes:
            errors.append("ClinicalTrials.gov sources require authorization scope public:clinicaltrials-gov")
        if source.stable_seconds != 0:
            errors.append("ClinicalTrials.gov sources require stable_seconds=0")
        try:
            self._routing_rule(source)
        except ConnectorConfigurationError as exc:
            errors.append(str(exc))
        cursor = _cursor_payload(source.connector_cursor)
        if cursor is None or (
            cursor
            and (
                cursor.get("schema_version") != "1.0"
                or cursor.get("kind") != "clinicaltrials_gov"
                or not _is_sha256(cursor.get("inventory_sha256"))
                or not _is_non_negative_integer(cursor.get("object_count"))
                or (
                    cursor.get("reported_total_count") is not None
                    and not _is_non_negative_integer(cursor.get("reported_total_count"))
                )
            )
        ):
            errors.append("ClinicalTrials.gov connector cursor is invalid")
        return errors

    def discover(self, source: DataSource) -> DiscoveryBatch:
        errors = self.validate_configuration(source)
        if errors:
            raise ConnectorConfigurationError(errors[0])
        rule = self._routing_rule(source)
        page_token: str | None = None
        seen_page_tokens: set[str] = set()
        objects: list[SourceObject] = []
        inventory: list[dict[str, object]] = []
        total_count: int | None = None

        for _ in range(self.settings.source_http_max_pages):
            remaining = rule.max_records - len(objects)
            if remaining <= 0:
                break
            page = self._fetch_page(
                source,
                rule,
                page_token=page_token,
                page_size=min(rule.page_size, remaining),
            )
            total_count = page.totalCount if page.totalCount is not None else total_count
            for study in page.studies:
                item = self._source_object(source, study)
                if any(existing.logical_path == item.logical_path for existing in objects):
                    raise ConnectorConfigurationError("ClinicalTrials.gov returned a duplicate NCT identifier")
                objects.append(item)
                inventory.append(
                    {
                        "content_sha256": item.content_sha256,
                        "logical_path": item.logical_path,
                        "modified_at": item.modified_at.isoformat(),
                        "size_bytes": item.size_bytes,
                    }
                )
                if len(objects) == rule.max_records:
                    break
            if len(objects) == rule.max_records or page.nextPageToken is None:
                break
            if page.nextPageToken in seen_page_tokens:
                raise ConnectorConfigurationError("ClinicalTrials.gov pagination token repeated")
            seen_page_tokens.add(page.nextPageToken)
            page_token = page.nextPageToken
        else:
            raise ConnectorConfigurationError("ClinicalTrials.gov source exceeded SOURCE_HTTP_MAX_PAGES")

        objects.sort(key=lambda item: item.logical_path)
        inventory.sort(key=lambda item: str(item["logical_path"]))
        inventory_sha256 = _inventory_sha256(inventory)
        return DiscoveryBatch(
            objects=objects,
            errors=[],
            excluded_count=0,
            cursor={
                "schema_version": "1.0",
                "kind": "clinicaltrials_gov",
                "query_term": rule.query_term,
                "max_records": rule.max_records,
                "sort": rule.sort,
                "object_count": len(objects),
                "reported_total_count": total_count,
                "inventory_sha256": inventory_sha256,
                "fetched_at": datetime.now(UTC).isoformat(),
            },
            authoritative_inventory=False,
            deleted_paths=[],
        )

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, ClinicalTrialsGovObjectHandle):
            raise ConnectorConfigurationError("ClinicalTrials.gov connector received an invalid object handle")
        content = item.handle.content
        if len(content) != item.size_bytes or hashlib.sha256(content).hexdigest() != item.content_sha256:
            raise ConnectorTransportError("ClinicalTrials.gov source object changed after discovery")
        with tempfile.TemporaryDirectory(prefix="pharma-clinicaltrials-gov-") as temporary:
            snapshot = Path(temporary) / "study.json"
            with snapshot.open("xb") as destination:
                destination.write(content)
                destination.flush()
                os.fsync(destination.fileno())
            yield snapshot

    def _fetch_page(
        self,
        source: DataSource,
        rule: ClinicalTrialsGovRoutingRule,
        *,
        page_token: str | None,
        page_size: int,
    ) -> ClinicalTrialsGovPage:
        params = {
            "query.term": rule.query_term,
            "pageSize": str(page_size),
            "countTotal": "true",
            "format": "json",
            "sort": rule.sort,
        }
        if page_token is not None:
            params["pageToken"] = page_token
        self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
        try:
            with self._client() as client:
                response = client.get(CLINICALTRIALS_GOV_STUDIES_URL, params=params)
                _require_success(response, "ClinicalTrials.gov studies API")
                content_type = response.headers.get("content-type", "").partition(";")[0].strip().casefold()
                if content_type != "application/json":
                    raise ConnectorTransportError("ClinicalTrials.gov response must use application/json")
                if len(response.content) > max(source.max_file_bytes * page_size, 1_048_576):
                    raise ConnectorTransportError("ClinicalTrials.gov response exceeded the configured safety limit")
                return ClinicalTrialsGovPage.model_validate_json(response.content)
        except httpx.HTTPError as exc:
            raise _http_transport_error("ClinicalTrials.gov", exc) from exc
        except ValidationError as exc:
            raise ConnectorConfigurationError("ClinicalTrials.gov response did not match API v2") from exc

    def _source_object(self, source: DataSource, study: dict[str, Any]) -> SourceObject:
        try:
            protocol = study["protocolSection"]
            identification = protocol["identificationModule"]
            status = protocol["statusModule"]
            nct_id = str(identification["nctId"])
        except (KeyError, TypeError) as exc:
            raise ConnectorConfigurationError("ClinicalTrials.gov study is missing required identifiers") from exc
        if CLINICALTRIALS_GOV_NCT_ID.fullmatch(nct_id) is None:
            raise ConnectorConfigurationError("ClinicalTrials.gov returned an invalid NCT identifier")
        modified_at = _clinicaltrials_gov_modified_at(status)
        content = json.dumps(study, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(content) > source.max_file_bytes:
            raise ConnectorConfigurationError(f"ClinicalTrials.gov study {nct_id} exceeds max_file_bytes")
        digest = hashlib.sha256(content).hexdigest()
        return SourceObject(
            logical_path=f"studies/{nct_id}.json",
            source_uri=f"{CLINICALTRIALS_GOV_STUDY_URL}/{nct_id}",
            file_name=f"{nct_id}.json",
            extension=".json",
            size_bytes=len(content),
            modified_at=modified_at,
            processing_mode="parse",
            dataset_key=source.dataset_key,
            content_sha256=digest,
            handle=ClinicalTrialsGovObjectHandle(content=content),
            source_fingerprint=digest,
        )

    @staticmethod
    def _routing_rule(source: DataSource) -> ClinicalTrialsGovRoutingRule:
        if len(source.routing_rules) != 1:
            raise ConnectorConfigurationError("ClinicalTrials.gov sources require exactly one routing rule")
        try:
            return ClinicalTrialsGovRoutingRule.model_validate(source.routing_rules[0])
        except ValidationError as exc:
            raise ConnectorConfigurationError("ClinicalTrials.gov routing rule is invalid") from exc

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(
                connect=self.settings.source_http_connect_timeout_seconds,
                read=self.settings.source_http_read_timeout_seconds,
                write=self.settings.source_http_read_timeout_seconds,
                pool=self.settings.source_http_connect_timeout_seconds,
            ),
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
            headers={"Accept": "application/json", "User-Agent": SOURCE_USER_AGENT},
        )


def _clinicaltrials_gov_modified_at(status_module: object) -> datetime:
    if not isinstance(status_module, dict):
        raise ConnectorConfigurationError("ClinicalTrials.gov study status module is invalid")
    date_value: object = None
    for field in ("lastUpdatePostDateStruct", "studyFirstPostDateStruct", "studyFirstSubmitDate"):
        candidate = status_module.get(field)
        if isinstance(candidate, dict):
            date_value = candidate.get("date")
        elif isinstance(candidate, str):
            date_value = candidate
        if isinstance(date_value, str) and date_value:
            break
    if not isinstance(date_value, str) or not date_value:
        raise ConnectorConfigurationError("ClinicalTrials.gov study is missing its update date")
    try:
        parsed = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConnectorConfigurationError("ClinicalTrials.gov study update date is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class S3CredentialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_key_id: str = Field(min_length=1, max_length=256)
    secret_access_key: str = Field(min_length=1, max_length=4096)
    session_token: str | None = Field(default=None, min_length=1, max_length=16_384)

    @field_validator("access_key_id", "secret_access_key", "session_token")
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("S3 credential values cannot contain control characters")
        return value


@dataclass(frozen=True)
class S3ObjectHandle:
    bucket: str
    key: str
    etag: str
    expected_size_bytes: int
    expected_modified_at: datetime
    credential_ref: str | None
    source_id: str
    rate_limit_per_minute: int


class S3SnapshotSourceConnector:
    source_type = DataSourceType.S3_SNAPSHOT
    capabilities = ConnectorCapabilities(
        connector_id="s3-snapshot-v1",
        incremental=True,
        replayable=True,
        credentials_required=False,
    )

    def __init__(
        self,
        settings: Settings,
        credential_resolver: SourceCredentialResolver,
    ) -> None:
        self.settings = settings
        self.credential_resolver = credential_resolver
        self.rate_limiter = _SourceRateLimiter()

    def normalize_root_uri(self, root_uri: str) -> str:
        return _normalize_s3_root_uri(root_uri, self.settings)

    def validate_configuration(self, source: DataSource) -> list[str]:
        errors: list[str] = []
        if source.stable_seconds != 0:
            errors.append("S3 snapshot sources require stable_seconds=0")
        try:
            self.normalize_root_uri(source.root_uri)
            _normalize_s3_endpoint(self.settings)
        except ValueError as exc:
            errors.append(str(exc))
        if source.credential_ref:
            credential_errors = self.credential_resolver.validation_errors(source.credential_ref)
            errors.extend(credential_errors)
            if not credential_errors:
                try:
                    self._credential_kwargs(source.credential_ref)
                except ConnectorConfigurationError as exc:
                    errors.append(str(exc))
        elif not self.settings.source_s3_allow_default_credential_chain:
            errors.append(
                "S3 snapshot sources require an env credential reference unless "
                "SOURCE_S3_ALLOW_DEFAULT_CREDENTIAL_CHAIN is enabled"
            )
        cursor = _cursor_payload(source.connector_cursor)
        if cursor is None or (
            cursor
            and (
                cursor.get("schema_version") != "1.0"
                or cursor.get("kind") != "s3_inventory"
                or not _is_sha256(cursor.get("inventory_sha256"))
                or not _is_non_negative_integer(cursor.get("object_count"))
            )
        ):
            errors.append("S3 snapshot connector cursor is invalid")
        return errors

    def discover(self, source: DataSource) -> DiscoveryBatch:
        configuration_errors = self.validate_configuration(source)
        if configuration_errors:
            raise ConnectorConfigurationError(configuration_errors[0])
        root_uri = self.normalize_root_uri(source.root_uri)
        bucket, prefix = _parse_s3_root_uri(root_uri)
        objects: list[SourceObject] = []
        errors: list[DiscoveryError] = []
        inventory: list[dict[str, object]] = []
        excluded_count = 0
        continuation_token: str | None = None
        seen_tokens: set[str] = set()
        seen_paths: set[str] = set()
        client = self._client(source.credential_ref)
        try:
            for _ in range(self.settings.source_s3_max_pages):
                request: dict[str, object] = {
                    "Bucket": bucket,
                    "Prefix": prefix,
                    "MaxKeys": self.settings.source_s3_page_size,
                }
                if continuation_token is not None:
                    request["ContinuationToken"] = continuation_token
                self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
                try:
                    response = client.list_objects_v2(**request)
                except (BotoCoreError, ClientError) as exc:
                    raise _s3_transport_error("inventory request", exc) from exc
                raw_contents = response.get("Contents", [])
                if not isinstance(raw_contents, list):
                    raise ConnectorTransportError("S3 inventory response has an invalid Contents field")
                for raw_item in raw_contents:
                    try:
                        item = self._source_object(source, root_uri, bucket, prefix, raw_item)
                    except ValueError as exc:
                        errors.append(
                            DiscoveryError(
                                _safe_s3_inventory_path(bucket, raw_item),
                                str(exc),
                            )
                        )
                        continue
                    if item is None:
                        excluded_count += 1
                        continue
                    if item.logical_path in seen_paths:
                        errors.append(DiscoveryError(item.source_uri, "S3 inventory contains a duplicate logical path"))
                        continue
                    seen_paths.add(item.logical_path)
                    objects.append(item)
                    inventory.append(
                        {
                            "logical_path": item.logical_path,
                            "modified_at": item.modified_at.isoformat(),
                            "size_bytes": item.size_bytes,
                            "source_fingerprint": item.source_fingerprint,
                        }
                    )
                if not bool(response.get("IsTruncated", False)):
                    break
                next_token = response.get("NextContinuationToken")
                if not isinstance(next_token, str) or not next_token or len(next_token) > 4096:
                    raise ConnectorTransportError("S3 inventory response omitted a valid continuation token")
                if next_token in seen_tokens:
                    raise ConnectorTransportError("S3 inventory continuation token repeated")
                seen_tokens.add(next_token)
                continuation_token = next_token
            else:
                raise ConnectorTransportError("S3 inventory exceeded SOURCE_S3_MAX_PAGES")
        finally:
            client.close()

        objects.sort(key=lambda item: item.logical_path.casefold())
        inventory.sort(key=lambda item: str(item["logical_path"]).casefold())
        return DiscoveryBatch(
            objects=objects,
            errors=errors,
            excluded_count=excluded_count,
            cursor={
                "schema_version": "1.0",
                "kind": "s3_inventory",
                "inventory_sha256": _inventory_sha256(inventory),
                "object_count": len(objects),
            },
            authoritative_inventory=True,
            deleted_paths=[],
        )

    def _source_object(
        self,
        source: DataSource,
        _root_uri: str,
        bucket: str,
        prefix: str,
        raw_item: object,
    ) -> SourceObject | None:
        if not isinstance(raw_item, dict):
            raise ConnectorConfigurationError("S3 inventory item is not an object")
        key = raw_item.get("Key")
        size_bytes = raw_item.get("Size")
        modified_at = raw_item.get("LastModified")
        etag = raw_item.get("ETag")
        if not isinstance(key, str) or not key.startswith(prefix) or key == prefix:
            raise ConnectorConfigurationError("S3 inventory key is outside the configured prefix")
        if key.endswith("/"):
            return None
        logical_path = _normalize_s3_logical_path(key[len(prefix) :])
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise ConnectorConfigurationError("S3 inventory object size is invalid")
        if not isinstance(modified_at, datetime) or modified_at.tzinfo is None or modified_at.utcoffset() is None:
            raise ConnectorConfigurationError("S3 inventory object LastModified is invalid")
        normalized_modified_at = modified_at.astimezone(UTC)
        if (
            not isinstance(etag, str)
            or not etag
            or len(etag) > 256
            or any(character in etag for character in ("\x00", "\r", "\n"))
        ):
            raise ConnectorConfigurationError("S3 inventory object ETag is invalid")
        file_name = PurePosixPath(logical_path).name
        if len(file_name) > 1000:
            raise ConnectorConfigurationError("S3 inventory object file name exceeds 1000 characters")
        processing_mode = classify_path(Path(file_name))
        if (
            processing_mode == "exclude"
            or size_bytes > source.max_file_bytes
            or not _matches(logical_path, source.include_globs)
            or _matches(logical_path, source.exclude_globs)
        ):
            return None
        source_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "bucket": bucket,
                    "etag": etag,
                    "key": key,
                    "modified_at": normalized_modified_at.isoformat(),
                    "size_bytes": size_bytes,
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return SourceObject(
            logical_path=logical_path,
            source_uri=f"s3://{bucket}/{quote(key, safe='/')}",
            file_name=file_name,
            extension=Path(file_name).suffix.casefold(),
            size_bytes=size_bytes,
            modified_at=normalized_modified_at,
            processing_mode=processing_mode,
            dataset_key=source.dataset_key,
            content_sha256=None,
            handle=S3ObjectHandle(
                bucket=bucket,
                key=key,
                etag=etag,
                expected_size_bytes=size_bytes,
                expected_modified_at=normalized_modified_at,
                credential_ref=source.credential_ref,
                source_id=source.id,
                rate_limit_per_minute=source.rate_limit_per_minute,
            ),
            source_fingerprint=source_fingerprint,
        )

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, S3ObjectHandle):
            raise ConnectorConfigurationError("S3 connector received an invalid source-object handle")
        handle = item.handle
        if item.size_bytes != handle.expected_size_bytes:
            raise ConnectorConfigurationError("S3 source-object size contract changed after discovery")
        self.rate_limiter.wait(handle.source_id, handle.rate_limit_per_minute)
        client = self._client(handle.credential_ref)
        body: Any = None
        with tempfile.TemporaryDirectory(prefix="pharma-s3-materialize-") as temporary:
            snapshot = Path(temporary) / f"snapshot{item.extension}"
            copied = 0
            try:
                try:
                    response = client.get_object(Bucket=handle.bucket, Key=handle.key, IfMatch=handle.etag)
                except (BotoCoreError, ClientError) as exc:
                    raise _s3_transport_error("object request", exc) from exc
                response_size = response.get("ContentLength")
                response_etag = response.get("ETag")
                response_modified_at = response.get("LastModified")
                if response_size != handle.expected_size_bytes:
                    raise ConnectorTransportError("S3 source object size changed after discovery")
                if response_etag != handle.etag:
                    raise ConnectorTransportError("S3 source object ETag changed after discovery")
                if (
                    not isinstance(response_modified_at, datetime)
                    or response_modified_at.tzinfo is None
                    or response_modified_at.astimezone(UTC) != handle.expected_modified_at
                ):
                    raise ConnectorTransportError("S3 source object LastModified changed after discovery")
                body = response.get("Body")
                if body is None or not hasattr(body, "read"):
                    raise ConnectorTransportError("S3 source object response omitted its body")
                with snapshot.open("xb") as destination:
                    while chunk := body.read(1024 * 1024):
                        if not isinstance(chunk, bytes):
                            raise ConnectorTransportError("S3 source object returned a non-byte chunk")
                        copied += len(chunk)
                        if copied > handle.expected_size_bytes:
                            raise ConnectorTransportError("S3 source object exceeded its discovered size")
                        destination.write(chunk)
                    destination.flush()
                    os.fsync(destination.fileno())
                if copied != handle.expected_size_bytes:
                    raise ConnectorTransportError("S3 source object size did not match its inventory")
            except Exception:
                snapshot.unlink(missing_ok=True)
                raise
            finally:
                if body is not None and hasattr(body, "close"):
                    body.close()
                client.close()
            yield snapshot

    def _credential_kwargs(self, credential_ref: str | None) -> dict[str, str]:
        if credential_ref is None:
            if not self.settings.source_s3_allow_default_credential_chain:
                raise ConnectorConfigurationError("S3 default credential chain is not enabled")
            return {}
        raw = self.credential_resolver.resolve_secret(credential_ref)
        try:
            payload = S3CredentialPayload.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            raise ConnectorConfigurationError("S3 credential payload does not match the required JSON schema") from exc
        credentials = {
            "aws_access_key_id": payload.access_key_id,
            "aws_secret_access_key": payload.secret_access_key,
        }
        if payload.session_token:
            credentials["aws_session_token"] = payload.session_token
        return credentials

    def _client(self, credential_ref: str | None) -> Any:
        endpoint_url = _normalize_s3_endpoint(self.settings)
        addressing_style = "path" if self.settings.source_s3_force_path_style else "auto"
        return boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=self.settings.source_s3_region,
            config=BotoConfig(
                signature_version="s3v4",
                connect_timeout=self.settings.source_s3_connect_timeout_seconds,
                read_timeout=self.settings.source_s3_read_timeout_seconds,
                retries={"max_attempts": 4, "mode": "standard"},
                s3={"addressing_style": addressing_style},
            ),
            **self._credential_kwargs(credential_ref),
        )


class SFTPCredentialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=1, max_length=4096)
    private_key_pem: str | None = Field(default=None, min_length=1, max_length=16_384)
    private_key_passphrase: str | None = Field(default=None, min_length=1, max_length=4096)

    @field_validator("username", "password", "private_key_passphrase")
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("SFTP credential values cannot contain control characters")
        return value

    @model_validator(mode="after")
    def require_one_authentication_method(self) -> SFTPCredentialPayload:
        if (self.password is None) == (self.private_key_pem is None):
            raise ValueError("SFTP credentials require exactly one of password or private_key_pem")
        if self.private_key_passphrase is not None and self.private_key_pem is None:
            raise ValueError("SFTP private_key_passphrase requires private_key_pem")
        return self


@dataclass(frozen=True)
class SFTPObjectHandle:
    origin: str
    remote_path: str
    expected_size_bytes: int
    expected_modified_at: datetime
    credential_ref: str
    source_id: str
    rate_limit_per_minute: int


class SFTPSnapshotSourceConnector:
    source_type = DataSourceType.SFTP_SNAPSHOT
    capabilities = ConnectorCapabilities(
        connector_id="sftp-snapshot-v1",
        incremental=True,
        replayable=True,
        credentials_required=True,
    )

    def __init__(self, settings: Settings, credential_resolver: SourceCredentialResolver) -> None:
        self.settings = settings
        self.credential_resolver = credential_resolver
        self.rate_limiter = _SourceRateLimiter()

    def normalize_root_uri(self, root_uri: str) -> str:
        return _normalize_sftp_root_uri(root_uri, self.settings)

    def validate_configuration(self, source: DataSource) -> list[str]:
        errors: list[str] = []
        if source.stable_seconds != 0:
            errors.append("SFTP snapshot sources require stable_seconds=0")
        try:
            normalized = self.normalize_root_uri(source.root_uri)
            origin, _, _, _ = _parse_sftp_root_uri(normalized)
            self._validate_known_host(origin)
        except ValueError as exc:
            errors.append(str(exc))
        if not source.credential_ref:
            errors.append("SFTP snapshot sources require an env credential reference")
        else:
            credential_errors = self.credential_resolver.validation_errors(source.credential_ref)
            errors.extend(credential_errors)
            if not credential_errors:
                try:
                    self._credentials(source.credential_ref)
                except ConnectorConfigurationError as exc:
                    errors.append(str(exc))
        cursor = _cursor_payload(source.connector_cursor)
        if cursor is None or (
            cursor
            and (
                cursor.get("schema_version") != "1.0"
                or cursor.get("kind") != "sftp_inventory"
                or not _is_sha256(cursor.get("inventory_sha256"))
                or not _is_non_negative_integer(cursor.get("object_count"))
            )
        ):
            errors.append("SFTP snapshot connector cursor is invalid")
        return errors

    def discover(self, source: DataSource) -> DiscoveryBatch:
        configuration_errors = self.validate_configuration(source)
        if configuration_errors:
            raise ConnectorConfigurationError(configuration_errors[0])
        assert source.credential_ref is not None
        root_uri = self.normalize_root_uri(source.root_uri)
        origin, _, _, remote_root = _parse_sftp_root_uri(root_uri)
        objects: list[SourceObject] = []
        errors: list[DiscoveryError] = []
        inventory: list[dict[str, object]] = []
        excluded_count = 0
        seen_paths: set[str] = set()
        pending: list[tuple[str, int]] = [(remote_root, 0)]
        entry_count = 0

        self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
        with self._session(origin, source.credential_ref) as sftp:
            while pending:
                directory, depth = pending.pop()
                self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
                try:
                    entries = sftp.listdir_attr(directory)
                except (OSError, EOFError, paramiko.SSHException) as exc:
                    if directory == remote_root:
                        raise _sftp_transport_error("root inventory request", exc) from exc
                    errors.append(
                        DiscoveryError(
                            _sftp_source_uri(origin, directory),
                            "SFTP directory inventory failed",
                        )
                    )
                    continue
                for raw_item in sorted(entries, key=lambda item: str(getattr(item, "filename", "")).casefold()):
                    entry_count += 1
                    if entry_count > self.settings.source_sftp_max_entries:
                        raise ConnectorTransportError("SFTP inventory exceeded SOURCE_SFTP_MAX_ENTRIES")
                    try:
                        remote_path, relative_path = _sftp_inventory_path(remote_root, directory, raw_item)
                        mode = getattr(raw_item, "st_mode", None)
                        if not isinstance(mode, int):
                            raise ConnectorConfigurationError("SFTP inventory item mode is invalid")
                        if stat.S_ISLNK(mode):
                            excluded_count += 1
                            continue
                        if stat.S_ISDIR(mode):
                            if depth >= self.settings.source_sftp_max_depth:
                                errors.append(
                                    DiscoveryError(
                                        _sftp_source_uri(origin, remote_path),
                                        "SFTP inventory exceeded SOURCE_SFTP_MAX_DEPTH",
                                    )
                                )
                            else:
                                pending.append((f"{remote_path}/", depth + 1))
                            continue
                        if not stat.S_ISREG(mode):
                            excluded_count += 1
                            continue
                        item = self._source_object(source, origin, remote_path, relative_path, raw_item)
                    except ValueError as exc:
                        errors.append(DiscoveryError(_sftp_source_uri(origin, directory), str(exc)))
                        continue
                    if item is None:
                        excluded_count += 1
                        continue
                    if item.logical_path in seen_paths:
                        errors.append(
                            DiscoveryError(item.source_uri, "SFTP inventory contains a duplicate logical path")
                        )
                        continue
                    seen_paths.add(item.logical_path)
                    objects.append(item)
                    inventory.append(
                        {
                            "logical_path": item.logical_path,
                            "modified_at": item.modified_at.isoformat(),
                            "size_bytes": item.size_bytes,
                            "source_fingerprint": item.source_fingerprint,
                        }
                    )

        objects.sort(key=lambda item: item.logical_path.casefold())
        inventory.sort(key=lambda item: str(item["logical_path"]).casefold())
        return DiscoveryBatch(
            objects=objects,
            errors=errors,
            excluded_count=excluded_count,
            cursor={
                "schema_version": "1.0",
                "kind": "sftp_inventory",
                "inventory_sha256": _inventory_sha256(inventory),
                "object_count": len(objects),
            },
            authoritative_inventory=True,
            deleted_paths=[],
        )

    def _source_object(
        self,
        source: DataSource,
        origin: str,
        remote_path: str,
        relative_path: str,
        raw_item: object,
    ) -> SourceObject | None:
        size_bytes = getattr(raw_item, "st_size", None)
        modified_timestamp = getattr(raw_item, "st_mtime", None)
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise ConnectorConfigurationError("SFTP inventory object size is invalid")
        if not isinstance(modified_timestamp, int | float) or isinstance(modified_timestamp, bool):
            raise ConnectorConfigurationError("SFTP inventory object mtime is invalid")
        try:
            modified_at = datetime.fromtimestamp(modified_timestamp, UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise ConnectorConfigurationError("SFTP inventory object mtime is invalid") from exc
        file_name = PurePosixPath(relative_path).name
        if len(file_name) > 1000:
            raise ConnectorConfigurationError("SFTP inventory object file name exceeds 1000 characters")
        processing_mode = classify_path(Path(file_name))
        if (
            processing_mode == "exclude"
            or size_bytes > source.max_file_bytes
            or not _matches(relative_path, source.include_globs)
            or _matches(relative_path, source.exclude_globs)
        ):
            return None
        source_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "modified_at": modified_at.isoformat(),
                    "origin": origin,
                    "path": remote_path,
                    "size_bytes": size_bytes,
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        assert source.credential_ref is not None
        return SourceObject(
            logical_path=relative_path,
            source_uri=_sftp_source_uri(origin, remote_path),
            file_name=file_name,
            extension=Path(file_name).suffix.casefold(),
            size_bytes=size_bytes,
            modified_at=modified_at,
            processing_mode=processing_mode,
            dataset_key=source.dataset_key,
            content_sha256=None,
            handle=SFTPObjectHandle(
                origin=origin,
                remote_path=remote_path,
                expected_size_bytes=size_bytes,
                expected_modified_at=modified_at,
                credential_ref=source.credential_ref,
                source_id=source.id,
                rate_limit_per_minute=source.rate_limit_per_minute,
            ),
            source_fingerprint=source_fingerprint,
            always_materialize=True,
        )

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, SFTPObjectHandle):
            raise ConnectorConfigurationError("SFTP connector received an invalid source-object handle")
        handle = item.handle
        if item.size_bytes != handle.expected_size_bytes:
            raise ConnectorConfigurationError("SFTP source-object size contract changed after discovery")
        self.rate_limiter.wait(handle.source_id, handle.rate_limit_per_minute)
        with tempfile.TemporaryDirectory(prefix="pharma-sftp-materialize-") as temporary:
            snapshot = Path(temporary) / f"snapshot{item.extension}"
            try:
                with self._session(handle.origin, handle.credential_ref) as sftp:
                    before = sftp.lstat(handle.remote_path)
                    self._require_expected_attributes(before, handle)
                    copied = 0
                    with sftp.file(handle.remote_path, mode="rb") as source, snapshot.open("xb") as destination:
                        while chunk := source.read(1024 * 1024):
                            if not isinstance(chunk, bytes):
                                raise ConnectorTransportError("SFTP source object returned a non-byte chunk")
                            copied += len(chunk)
                            if copied > handle.expected_size_bytes:
                                raise ConnectorTransportError("SFTP source object exceeded its discovered size")
                            destination.write(chunk)
                        destination.flush()
                        os.fsync(destination.fileno())
                    after = sftp.lstat(handle.remote_path)
                    self._require_expected_attributes(after, handle)
                    if copied != handle.expected_size_bytes:
                        raise ConnectorTransportError("SFTP source object size did not match its inventory")
            except Exception:
                snapshot.unlink(missing_ok=True)
                raise
            yield snapshot

    def _require_expected_attributes(self, attributes: object, handle: SFTPObjectHandle) -> None:
        mode = getattr(attributes, "st_mode", None)
        size = getattr(attributes, "st_size", None)
        modified_timestamp = getattr(attributes, "st_mtime", None)
        if not isinstance(mode, int) or not stat.S_ISREG(mode):
            raise ConnectorTransportError("SFTP source object is no longer a regular file")
        if size != handle.expected_size_bytes or not isinstance(modified_timestamp, int | float):
            raise ConnectorTransportError("SFTP source object changed after discovery")
        try:
            modified_at = datetime.fromtimestamp(modified_timestamp, UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise ConnectorTransportError("SFTP source object mtime became invalid") from exc
        if modified_at != handle.expected_modified_at:
            raise ConnectorTransportError("SFTP source object changed after discovery")

    def _credentials(self, credential_ref: str) -> tuple[SFTPCredentialPayload, paramiko.PKey | None]:
        raw = self.credential_resolver.resolve_secret(credential_ref)
        try:
            payload = SFTPCredentialPayload.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            raise ConnectorConfigurationError(
                "SFTP credential payload does not match the required JSON schema"
            ) from exc
        if payload.password is not None and not self.settings.source_sftp_allow_password_auth:
            raise ConnectorConfigurationError("SFTP password authentication is not enabled")
        private_key = _parse_sftp_private_key(payload.private_key_pem, payload.private_key_passphrase)
        return payload, private_key

    def _validate_known_host(self, origin: str) -> None:
        path = _sftp_known_hosts_path(self.settings)
        _, host, port, _ = _parse_sftp_root_uri(f"{origin}/")
        lookup_name = host if port == 22 else f"[{host}]:{port}"
        try:
            host_keys = paramiko.HostKeys(str(path))
        except (OSError, paramiko.SSHException) as exc:
            raise ConnectorConfigurationError("SOURCE_SFTP_KNOWN_HOSTS_PATH could not be loaded") from exc
        if host_keys.lookup(lookup_name) is None:
            raise ConnectorConfigurationError("SFTP origin is missing from SOURCE_SFTP_KNOWN_HOSTS_PATH")

    @contextmanager
    def _session(self, origin: str, credential_ref: str) -> Iterator[Any]:
        _, host, port, _ = _parse_sftp_root_uri(f"{origin}/")
        payload, private_key = self._credentials(credential_ref)
        client = paramiko.SSHClient()
        sftp: Any = None
        try:
            client.load_host_keys(str(_sftp_known_hosts_path(self.settings)))
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            client.connect(
                hostname=host,
                port=port,
                username=payload.username,
                password=payload.password,
                pkey=private_key,
                timeout=self.settings.source_sftp_connect_timeout_seconds,
                banner_timeout=self.settings.source_sftp_connect_timeout_seconds,
                auth_timeout=self.settings.source_sftp_connect_timeout_seconds,
                channel_timeout=self.settings.source_sftp_read_timeout_seconds,
                allow_agent=False,
                look_for_keys=False,
            )
            sftp = client.open_sftp()
            sftp.get_channel().settimeout(self.settings.source_sftp_read_timeout_seconds)
            yield sftp
        except (ConnectorConfigurationError, ConnectorTransportError):
            raise
        except (OSError, EOFError, paramiko.SSHException) as exc:
            raise _sftp_transport_error("connection or transfer", exc) from exc
        finally:
            if sftp is not None:
                sftp.close()
            client.close()


class SMBCredentialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=4096)
    domain: str | None = Field(default=None, min_length=1, max_length=255)
    auth_protocol: Literal["negotiate", "ntlm"] = "negotiate"

    @field_validator("username", "password", "domain")
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("SMB credential values cannot contain control characters")
        return value


@dataclass(frozen=True)
class SMBObjectHandle:
    origin: str
    remote_path: str
    expected_size_bytes: int
    expected_modified_at: datetime
    credential_ref: str
    source_id: str
    rate_limit_per_minute: int


class SMBSnapshotSourceConnector:
    source_type = DataSourceType.SMB_SNAPSHOT
    capabilities = ConnectorCapabilities(
        connector_id="smb-snapshot-v1",
        incremental=True,
        replayable=True,
        credentials_required=True,
    )

    def __init__(self, settings: Settings, credential_resolver: SourceCredentialResolver) -> None:
        self.settings = settings
        self.credential_resolver = credential_resolver
        self.rate_limiter = _SourceRateLimiter()

    def normalize_root_uri(self, root_uri: str) -> str:
        return _normalize_smb_root_uri(root_uri, self.settings)

    def validate_configuration(self, source: DataSource) -> list[str]:
        errors: list[str] = []
        if source.stable_seconds != 0:
            errors.append("SMB snapshot sources require stable_seconds=0")
        try:
            self.normalize_root_uri(source.root_uri)
        except ValueError as exc:
            errors.append(str(exc))
        if not source.credential_ref:
            errors.append("SMB snapshot sources require an env credential reference")
        else:
            credential_errors = self.credential_resolver.validation_errors(source.credential_ref)
            errors.extend(credential_errors)
            if not credential_errors:
                try:
                    self._credentials(source.credential_ref)
                except ConnectorConfigurationError as exc:
                    errors.append(str(exc))
        cursor = _cursor_payload(source.connector_cursor)
        if cursor is None or (
            cursor
            and (
                cursor.get("schema_version") != "1.0"
                or cursor.get("kind") != "smb_inventory"
                or not _is_sha256(cursor.get("inventory_sha256"))
                or not _is_non_negative_integer(cursor.get("object_count"))
            )
        ):
            errors.append("SMB snapshot connector cursor is invalid")
        return errors

    def discover(self, source: DataSource) -> DiscoveryBatch:
        configuration_errors = self.validate_configuration(source)
        if configuration_errors:
            raise ConnectorConfigurationError(configuration_errors[0])
        assert source.credential_ref is not None
        root_uri = self.normalize_root_uri(source.root_uri)
        origin, remote_root = _parse_smb_root_uri(root_uri)
        _, port = _parse_smb_origin(origin)
        objects: list[SourceObject] = []
        errors: list[DiscoveryError] = []
        inventory: list[dict[str, object]] = []
        excluded_count = 0
        seen_paths: set[str] = set()
        pending: list[tuple[str, str, int]] = [(remote_root, "", 0)]
        entry_count = 0

        self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
        with self._session(origin, source.credential_ref) as connection_cache:
            while pending:
                directory, relative_directory, depth = pending.pop()
                self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
                try:
                    with smbclient.scandir(directory, port=port, connection_cache=connection_cache) as entries:
                        raw_entries = sorted(entries, key=lambda item: str(getattr(item, "name", "")).casefold())
                except (OSError, TimeoutError, SMBException) as exc:
                    if directory == remote_root:
                        raise _smb_transport_error("root inventory request", exc) from exc
                    errors.append(
                        DiscoveryError(_smb_uri_from_unc(origin, directory), "SMB directory inventory failed")
                    )
                    continue
                for raw_item in raw_entries:
                    entry_count += 1
                    if entry_count > self.settings.source_smb_max_entries:
                        raise ConnectorTransportError("SMB inventory exceeded SOURCE_SMB_MAX_ENTRIES")
                    try:
                        name = _smb_inventory_name(raw_item)
                        remote_path = f"{directory.rstrip('\\')}\\{name}"
                        relative_path = _normalize_smb_relative_path(
                            posixpath.join(relative_directory, name) if relative_directory else name
                        )
                        if raw_item.is_symlink():
                            excluded_count += 1
                            continue
                        if raw_item.is_dir(follow_symlinks=False):
                            if depth >= self.settings.source_smb_max_depth:
                                errors.append(
                                    DiscoveryError(
                                        _smb_uri_from_unc(origin, remote_path),
                                        "SMB inventory exceeded SOURCE_SMB_MAX_DEPTH",
                                    )
                                )
                            else:
                                pending.append((remote_path, relative_path, depth + 1))
                            continue
                        if not raw_item.is_file(follow_symlinks=False):
                            excluded_count += 1
                            continue
                        attributes = smbclient.stat(
                            remote_path,
                            follow_symlinks=False,
                            port=port,
                            connection_cache=connection_cache,
                        )
                        item = self._source_object(source, origin, remote_path, relative_path, attributes)
                    except (OSError, TimeoutError, SMBException, ValueError) as exc:
                        errors.append(DiscoveryError(_smb_uri_from_unc(origin, directory), _smb_inventory_error(exc)))
                        continue
                    if item is None:
                        excluded_count += 1
                        continue
                    if item.logical_path in seen_paths:
                        errors.append(
                            DiscoveryError(item.source_uri, "SMB inventory contains a duplicate logical path")
                        )
                        continue
                    seen_paths.add(item.logical_path)
                    objects.append(item)
                    inventory.append(
                        {
                            "logical_path": item.logical_path,
                            "modified_at": item.modified_at.isoformat(),
                            "size_bytes": item.size_bytes,
                            "source_fingerprint": item.source_fingerprint,
                        }
                    )

        objects.sort(key=lambda item: item.logical_path.casefold())
        inventory.sort(key=lambda item: str(item["logical_path"]).casefold())
        return DiscoveryBatch(
            objects=objects,
            errors=errors,
            excluded_count=excluded_count,
            cursor={
                "schema_version": "1.0",
                "kind": "smb_inventory",
                "inventory_sha256": _inventory_sha256(inventory),
                "object_count": len(objects),
            },
            authoritative_inventory=True,
            deleted_paths=[],
        )

    def _source_object(
        self,
        source: DataSource,
        origin: str,
        remote_path: str,
        relative_path: str,
        attributes: object,
    ) -> SourceObject | None:
        size_bytes = getattr(attributes, "st_size", None)
        modified_timestamp = getattr(attributes, "st_mtime", None)
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes < 0:
            raise ConnectorConfigurationError("SMB inventory object size is invalid")
        if not isinstance(modified_timestamp, int | float) or isinstance(modified_timestamp, bool):
            raise ConnectorConfigurationError("SMB inventory object mtime is invalid")
        try:
            modified_at = datetime.fromtimestamp(modified_timestamp, UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise ConnectorConfigurationError("SMB inventory object mtime is invalid") from exc
        file_name = PurePosixPath(relative_path).name
        if len(file_name) > 1000:
            raise ConnectorConfigurationError("SMB inventory object file name exceeds 1000 characters")
        processing_mode = classify_path(Path(file_name))
        if (
            processing_mode == "exclude"
            or size_bytes > source.max_file_bytes
            or not _matches(relative_path, source.include_globs)
            or _matches(relative_path, source.exclude_globs)
        ):
            return None
        source_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "modified_at": modified_at.isoformat(),
                    "origin": origin,
                    "path": remote_path,
                    "size_bytes": size_bytes,
                },
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        assert source.credential_ref is not None
        return SourceObject(
            logical_path=relative_path,
            source_uri=_smb_uri_from_unc(origin, remote_path),
            file_name=file_name,
            extension=Path(file_name).suffix.casefold(),
            size_bytes=size_bytes,
            modified_at=modified_at,
            processing_mode=processing_mode,
            dataset_key=source.dataset_key,
            content_sha256=None,
            handle=SMBObjectHandle(
                origin=origin,
                remote_path=remote_path,
                expected_size_bytes=size_bytes,
                expected_modified_at=modified_at,
                credential_ref=source.credential_ref,
                source_id=source.id,
                rate_limit_per_minute=source.rate_limit_per_minute,
            ),
            source_fingerprint=source_fingerprint,
            always_materialize=True,
        )

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, SMBObjectHandle):
            raise ConnectorConfigurationError("SMB connector received an invalid source-object handle")
        handle = item.handle
        _, port = _parse_smb_origin(handle.origin)
        if item.size_bytes != handle.expected_size_bytes:
            raise ConnectorConfigurationError("SMB source-object size contract changed after discovery")
        self.rate_limiter.wait(handle.source_id, handle.rate_limit_per_minute)
        with tempfile.TemporaryDirectory(prefix="pharma-smb-materialize-") as temporary:
            snapshot = Path(temporary) / f"snapshot{item.extension}"
            try:
                with self._session(handle.origin, handle.credential_ref) as connection_cache:
                    before = smbclient.stat(
                        handle.remote_path,
                        follow_symlinks=False,
                        port=port,
                        connection_cache=connection_cache,
                    )
                    self._require_expected_attributes(before, handle)
                    copied = 0
                    with (
                        smbclient.open_file(
                            handle.remote_path,
                            mode="rb",
                            share_access="r",
                            port=port,
                            connection_cache=connection_cache,
                        ) as source,
                        snapshot.open("xb") as destination,
                    ):
                        while chunk := source.read(1024 * 1024):
                            if not isinstance(chunk, bytes):
                                raise ConnectorTransportError("SMB source object returned a non-byte chunk")
                            copied += len(chunk)
                            if copied > handle.expected_size_bytes:
                                raise ConnectorTransportError("SMB source object exceeded its discovered size")
                            destination.write(chunk)
                        destination.flush()
                        os.fsync(destination.fileno())
                    after = smbclient.stat(
                        handle.remote_path,
                        follow_symlinks=False,
                        port=port,
                        connection_cache=connection_cache,
                    )
                    self._require_expected_attributes(after, handle)
                    if copied != handle.expected_size_bytes:
                        raise ConnectorTransportError("SMB source object size did not match its inventory")
            except Exception:
                snapshot.unlink(missing_ok=True)
                raise
            yield snapshot

    def _require_expected_attributes(self, attributes: object, handle: SMBObjectHandle) -> None:
        mode = getattr(attributes, "st_mode", None)
        size = getattr(attributes, "st_size", None)
        modified_timestamp = getattr(attributes, "st_mtime", None)
        if not isinstance(mode, int) or not stat.S_ISREG(mode):
            raise ConnectorTransportError("SMB source object is no longer a regular file")
        if size != handle.expected_size_bytes or not isinstance(modified_timestamp, int | float):
            raise ConnectorTransportError("SMB source object changed after discovery")
        try:
            modified_at = datetime.fromtimestamp(modified_timestamp, UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise ConnectorTransportError("SMB source object mtime became invalid") from exc
        if modified_at != handle.expected_modified_at:
            raise ConnectorTransportError("SMB source object changed after discovery")

    def _credentials(self, credential_ref: str) -> SMBCredentialPayload:
        raw = self.credential_resolver.resolve_secret(credential_ref)
        try:
            return SMBCredentialPayload.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            raise ConnectorConfigurationError("SMB credential payload does not match the required JSON schema") from exc

    @contextmanager
    def _session(self, origin: str, credential_ref: str) -> Iterator[dict[str, Any]]:
        host, port = _parse_smb_origin(origin)
        payload = self._credentials(credential_ref)
        username = f"{payload.domain}\\{payload.username}" if payload.domain else payload.username
        connection_cache: dict[str, Any] = {}
        try:
            smbclient.register_session(
                host,
                username=username,
                password=payload.password,
                port=port,
                encrypt=self.settings.source_smb_require_encryption,
                connection_timeout=self.settings.source_smb_connect_timeout_seconds,
                connection_cache=connection_cache,
                auth_protocol=payload.auth_protocol,
                require_signing=True,
            )
            yield connection_cache
        except ConnectorTransportError:
            raise
        except (OSError, TimeoutError, SMBException, ValueError) as exc:
            raise _smb_transport_error("connection or transfer", exc) from exc
        finally:
            smbclient.reset_connection_cache(fail_on_error=False, connection_cache=connection_cache)


class SourceConnectorRegistry:
    def __init__(
        self,
        settings: Settings | None = None,
        connectors: list[SourceConnector] | None = None,
        credential_resolver: SourceCredentialResolver | None = None,
    ) -> None:
        effective_settings = settings or Settings()
        resolver = credential_resolver or EnvironmentCredentialResolver(
            effective_settings.source_credential_env_allowlist,
            effective_settings.source_credential_max_bytes,
        )
        from pharma_intel.ingest.chembl import ChEMBLSourceConnector
        from pharma_intel.ingest.pubmed import PubMedSourceConnector

        registered = connectors or [
            FolderSourceConnector(effective_settings),
            HttpManifestSourceConnector(effective_settings, resolver),
            ClinicalTrialsGovSourceConnector(effective_settings),
            PubMedSourceConnector(effective_settings),
            ChEMBLSourceConnector(effective_settings),
            S3SnapshotSourceConnector(effective_settings, resolver),
            SFTPSnapshotSourceConnector(effective_settings, resolver),
            SMBSnapshotSourceConnector(effective_settings, resolver),
        ]
        self._connectors = {connector.source_type: connector for connector in registered}
        if len(self._connectors) != len(registered):
            raise ConnectorConfigurationError("Duplicate source connector type")

    def get(self, source_type: DataSourceType) -> SourceConnector:
        connector = self._connectors.get(source_type)
        if connector is None:
            raise ConnectorConfigurationError(f"Unsupported source type: {source_type.value}")
        return connector

    def capabilities(self, source_type: DataSourceType) -> ConnectorCapabilities:
        return self.get(source_type).capabilities


def _normalize_s3_root_uri(root_uri: str, settings: Settings) -> str:
    raw = root_uri.strip()
    if not raw or any(character in raw for character in ("\x00", "\r", "\n")):
        raise ConnectorConfigurationError("S3 source URI is invalid")
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise ConnectorConfigurationError("S3 source URI is invalid") from exc
    if parsed.scheme.casefold() != "s3" or not parsed.netloc:
        raise ConnectorConfigurationError("S3 source URI must use s3://bucket/prefix")
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise ConnectorConfigurationError("S3 source URI cannot contain credentials, port, query, or fragment")
    bucket = parsed.netloc.casefold()
    _validate_s3_bucket(bucket)
    allowed_buckets = {_validate_s3_bucket(item.casefold()) for item in settings.source_s3_allowed_buckets}
    if bucket not in allowed_buckets:
        raise ConnectorConfigurationError("S3 source bucket is not present in SOURCE_S3_ALLOWED_BUCKETS")
    encoded_path = parsed.path.removeprefix("/")
    try:
        prefix = unquote(encoded_path, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ConnectorConfigurationError("S3 source prefix is not valid UTF-8") from exc
    if prefix.endswith("/"):
        prefix = prefix[:-1]
    if prefix:
        _normalize_s3_logical_path(prefix)
    normalized_prefix = quote(prefix, safe="/-._~")
    return f"s3://{bucket}/{normalized_prefix + '/' if normalized_prefix else ''}"


def _normalize_sftp_root_uri(root_uri: str, settings: Settings) -> str:
    raw = root_uri.strip()
    if not raw or any(character in raw for character in ("\x00", "\r", "\n")):
        raise ConnectorConfigurationError("SFTP source URI is invalid")
    try:
        parsed = urlsplit(raw)
        origin = _sftp_origin(parsed)
    except ValueError as exc:
        raise ConnectorConfigurationError("SFTP source URI is invalid") from exc
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConnectorConfigurationError("SFTP source URI cannot contain credentials, query, or fragment")
    allowed_origins = {_normalize_sftp_allowed_origin(item) for item in settings.source_sftp_allowed_origins}
    if origin not in allowed_origins:
        raise ConnectorConfigurationError("SFTP source origin is not present in SOURCE_SFTP_ALLOWED_ORIGINS")
    try:
        decoded_path = unquote(parsed.path, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ConnectorConfigurationError("SFTP source path is not valid UTF-8") from exc
    normalized_path = _normalize_sftp_directory_path(decoded_path)
    return f"{origin}{quote(normalized_path, safe='/-._~')}"


def _normalize_sftp_allowed_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        origin = _sftp_origin(parsed)
    except ValueError as exc:
        raise ConnectorConfigurationError("SOURCE_SFTP_ALLOWED_ORIGINS contains an invalid origin") from exc
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ConnectorConfigurationError("SOURCE_SFTP_ALLOWED_ORIGINS entries must be origins without credentials")
    return origin


def _sftp_origin(parsed: SplitResult) -> str:
    if parsed.scheme.casefold() != "sftp" or not parsed.hostname:
        raise ValueError("Invalid SFTP origin")
    raw_host = parsed.hostname.casefold()
    if raw_host.endswith(".") or any(character.isspace() for character in raw_host):
        raise ValueError("Invalid SFTP hostname")
    try:
        ip = ipaddress.ip_address(raw_host)
    except ValueError:
        try:
            host = raw_host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Invalid SFTP hostname") from exc
    else:
        host = ip.compressed
    port = parsed.port or 22
    if port < 1 or port > 65535:
        raise ValueError("Invalid SFTP port")
    rendered_host = f"[{host}]" if ":" in host else host
    return f"sftp://{rendered_host}:{port}"


def _normalize_sftp_directory_path(value: str) -> str:
    if (
        not value.startswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ConnectorConfigurationError("SFTP source path must be an absolute POSIX directory")
    without_trailing = value.rstrip("/") or "/"
    path = PurePosixPath(without_trailing)
    if path.as_posix() != without_trailing or any(part in {".", ".."} for part in path.parts):
        raise ConnectorConfigurationError("SFTP source path is not canonical")
    if len(without_trailing.encode("utf-8")) > 4000:
        raise ConnectorConfigurationError("SFTP source path exceeds the supported size")
    return "/" if without_trailing == "/" else f"{without_trailing}/"


def _parse_sftp_root_uri(root_uri: str) -> tuple[str, str, int, str]:
    parsed = urlsplit(root_uri)
    origin = _sftp_origin(parsed)
    host = parsed.hostname
    assert host is not None
    normalized_host = ipaddress.ip_address(host).compressed if _is_ip_address(host) else host.casefold()
    remote_root = unquote(parsed.path, encoding="utf-8", errors="strict")
    return origin, normalized_host, parsed.port or 22, remote_root


def _sftp_inventory_path(remote_root: str, directory: str, raw_item: object) -> tuple[str, str]:
    filename = getattr(raw_item, "filename", None)
    if (
        not isinstance(filename, str)
        or not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
    ):
        raise ConnectorConfigurationError("SFTP inventory item name is invalid")
    remote_path = posixpath.join(directory, filename)
    if remote_root == "/":
        relative_path = remote_path.removeprefix("/")
    elif remote_path.startswith(remote_root):
        relative_path = remote_path[len(remote_root) :]
    else:
        raise ConnectorConfigurationError("SFTP inventory path escaped the configured source root")
    return remote_path, _normalize_sftp_relative_path(relative_path)


def _normalize_sftp_relative_path(value: str) -> str:
    if (
        not value
        or value.startswith("/")
        or value.endswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ConnectorConfigurationError("SFTP object path is not a canonical relative POSIX path")
    path = PurePosixPath(value)
    if path.as_posix() != value or any(part in {"", ".", ".."} for part in path.parts):
        raise ConnectorConfigurationError("SFTP object path is not a canonical relative POSIX path")
    if len(value.encode("utf-8")) > 4000:
        raise ConnectorConfigurationError("SFTP object path exceeds the supported logical-path size")
    return value


def _sftp_source_uri(origin: str, remote_path: str) -> str:
    return f"{origin}{quote(remote_path, safe='/-._~')}"


def _sftp_known_hosts_path(settings: Settings) -> Path:
    raw = settings.source_sftp_known_hosts_path.strip()
    if not raw:
        raise ConnectorConfigurationError("SFTP sources require SOURCE_SFTP_KNOWN_HOSTS_PATH")
    path = Path(raw)
    if not path.is_absolute():
        raise ConnectorConfigurationError("SOURCE_SFTP_KNOWN_HOSTS_PATH must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ConnectorConfigurationError("SOURCE_SFTP_KNOWN_HOSTS_PATH is unavailable") from exc
    if not resolved.is_file():
        raise ConnectorConfigurationError("SOURCE_SFTP_KNOWN_HOSTS_PATH must reference a file")
    return resolved


def _parse_sftp_private_key(private_key_pem: str | None, passphrase: str | None) -> paramiko.PKey | None:
    if private_key_pem is None:
        return None
    for key_type in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return key_type.from_private_key(io.StringIO(private_key_pem), password=passphrase)
        except (paramiko.SSHException, ValueError):
            continue
    raise ConnectorConfigurationError("SFTP private key is invalid or its passphrase is incorrect")


def _sftp_transport_error(operation: str, _error: Exception) -> ConnectorTransportError:
    return ConnectorTransportError(f"SFTP {operation} failed")


def _normalize_smb_root_uri(root_uri: str, settings: Settings) -> str:
    raw = root_uri.strip()
    if not raw or any(character in raw for character in ("\x00", "\r", "\n")):
        raise ConnectorConfigurationError("SMB source URI is invalid")
    try:
        parsed = urlsplit(raw)
        origin = _smb_origin(parsed)
    except ValueError as exc:
        raise ConnectorConfigurationError("SMB source URI is invalid") from exc
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConnectorConfigurationError("SMB source URI cannot contain credentials, query, or fragment")
    allowed_origins = {_normalize_smb_allowed_origin(item) for item in settings.source_smb_allowed_origins}
    if origin not in allowed_origins:
        raise ConnectorConfigurationError("SMB source origin is not present in SOURCE_SMB_ALLOWED_ORIGINS")
    if _is_loopback_host(parsed.hostname or "") and not (
        settings.source_smb_allow_insecure_loopback and settings.app_env.casefold() != "production"
    ):
        raise ConnectorConfigurationError("SMB loopback sources are disabled")
    try:
        decoded_path = unquote(parsed.path, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ConnectorConfigurationError("SMB source path is not valid UTF-8") from exc
    normalized_path = _normalize_smb_directory_path(decoded_path)
    return f"{origin}{quote(normalized_path, safe='/-._~$')}"


def _normalize_smb_allowed_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        origin = _smb_origin(parsed)
    except ValueError as exc:
        raise ConnectorConfigurationError("SOURCE_SMB_ALLOWED_ORIGINS contains an invalid origin") from exc
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ConnectorConfigurationError("SOURCE_SMB_ALLOWED_ORIGINS entries must be origins without credentials")
    return origin


def _smb_origin(parsed: SplitResult) -> str:
    if parsed.scheme.casefold() != "smb" or not parsed.hostname:
        raise ValueError("Invalid SMB origin")
    raw_host = parsed.hostname.casefold()
    if raw_host.endswith(".") or any(character.isspace() for character in raw_host):
        raise ValueError("Invalid SMB hostname")
    try:
        ip = ipaddress.ip_address(raw_host)
    except ValueError:
        try:
            host = raw_host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Invalid SMB hostname") from exc
    else:
        if ip.version != 4:
            raise ValueError("IPv6 SMB origins are not supported")
        host = ip.compressed
    port = parsed.port or 445
    if port < 1 or port > 65535:
        raise ValueError("Invalid SMB port")
    return f"smb://{host}:{port}"


def _parse_smb_origin(origin: str) -> tuple[str, int]:
    parsed = urlsplit(origin)
    normalized = _smb_origin(parsed)
    if normalized != origin:
        raise ConnectorConfigurationError("SMB origin is not canonical")
    host = parsed.hostname
    assert host is not None
    return host.casefold(), parsed.port or 445


def _normalize_smb_directory_path(value: str) -> str:
    if (
        not value.startswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ConnectorConfigurationError("SMB source path must contain a share and an absolute directory")
    without_trailing = value.rstrip("/")
    path = PurePosixPath(without_trailing)
    parts = path.parts[1:]
    if (
        not without_trailing
        or len(parts) < 1
        or path.as_posix() != without_trailing
        or any(not _valid_smb_segment(part) for part in parts)
        or len(without_trailing.encode("utf-8")) > 4000
    ):
        raise ConnectorConfigurationError("SMB source path is not canonical")
    return f"{without_trailing}/"


def _valid_smb_segment(value: str) -> bool:
    return (
        bool(value)
        and value not in {".", ".."}
        and len(value.encode("utf-8")) <= 255
        and not value.endswith((" ", "."))
        and not any(character in '<>:"\\|?*' for character in value)
        and not any(ord(character) < 32 or ord(character) == 127 for character in value)
    )


def _parse_smb_root_uri(root_uri: str) -> tuple[str, str]:
    parsed = urlsplit(root_uri)
    origin = _smb_origin(parsed)
    host, _ = _parse_smb_origin(origin)
    decoded_path = unquote(parsed.path, encoding="utf-8", errors="strict").strip("/")
    parts = decoded_path.split("/")
    remote_root = "\\\\" + host + "\\" + "\\".join(parts)
    return origin, remote_root


def _smb_inventory_name(raw_item: object) -> str:
    name = getattr(raw_item, "name", None)
    if not isinstance(name, str) or not _valid_smb_segment(name):
        raise ConnectorConfigurationError("SMB inventory item name is invalid")
    return name


def _normalize_smb_relative_path(value: str) -> str:
    if (
        not value
        or value.startswith("/")
        or value.endswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ConnectorConfigurationError("SMB object path is not a canonical relative path")
    path = PurePosixPath(value)
    if path.as_posix() != value or any(not _valid_smb_segment(part) for part in path.parts):
        raise ConnectorConfigurationError("SMB object path is not a canonical relative path")
    if len(value.encode("utf-8")) > 4000:
        raise ConnectorConfigurationError("SMB object path exceeds the supported logical-path size")
    return value


def _smb_uri_from_unc(origin: str, remote_path: str) -> str:
    host, _ = _parse_smb_origin(origin)
    prefix = f"\\\\{host}\\"
    if not remote_path.casefold().startswith(prefix.casefold()):
        return f"{origin}/<invalid-path>"
    relative = remote_path[len(prefix) :].replace("\\", "/")
    return f"{origin}/{quote(relative, safe='/-._~$')}"


def _smb_inventory_error(error: Exception) -> str:
    if isinstance(error, ConnectorConfigurationError):
        return str(error)
    return f"SMB inventory item could not be read ({type(error).__name__})"


def _smb_transport_error(operation: str, _error: Exception) -> ConnectorTransportError:
    return ConnectorTransportError(f"SMB {operation} failed")


def _is_ip_address(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _parse_s3_root_uri(root_uri: str) -> tuple[str, str]:
    parsed = urlsplit(root_uri)
    bucket = parsed.netloc
    prefix = unquote(parsed.path.removeprefix("/"), encoding="utf-8", errors="strict")
    return bucket, prefix


def _validate_s3_bucket(bucket: str) -> str:
    if (
        S3_BUCKET_PATTERN.fullmatch(bucket) is None
        or ".." in bucket
        or bucket.startswith("xn--")
        or bucket.endswith("-s3alias")
    ):
        raise ConnectorConfigurationError("S3 bucket name is invalid")
    try:
        ipaddress.ip_address(bucket)
    except ValueError:
        pass
    else:
        raise ConnectorConfigurationError("S3 bucket name cannot be an IP address")
    return bucket


def _normalize_s3_logical_path(value: str) -> str:
    if (
        not value
        or value.startswith("/")
        or value.endswith("/")
        or "\\" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ConnectorConfigurationError("S3 object key is not a canonical relative POSIX path")
    path = PurePosixPath(value)
    normalized = path.as_posix()
    if normalized != value or any(part in {"", ".", ".."} for part in path.parts):
        raise ConnectorConfigurationError("S3 object key is not a canonical relative POSIX path")
    if len(value.encode("utf-8")) > 4000:
        raise ConnectorConfigurationError("S3 object key exceeds the supported logical-path size")
    return normalized


def _normalize_s3_endpoint(settings: Settings) -> str | None:
    raw = settings.source_s3_endpoint_url.strip()
    if not raw:
        return None
    if any(character in raw for character in ("\x00", "\r", "\n")):
        raise ConnectorConfigurationError("SOURCE_S3_ENDPOINT_URL is invalid")
    try:
        parsed = urlsplit(raw)
        origin = _origin(parsed)
    except ValueError as exc:
        raise ConnectorConfigurationError("SOURCE_S3_ENDPOINT_URL is invalid") from exc
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ConnectorConfigurationError("SOURCE_S3_ENDPOINT_URL must be an origin without credentials or paths")
    loopback = _is_loopback_host(parsed.hostname or "")
    if parsed.scheme.casefold() != "https" and not (
        parsed.scheme.casefold() == "http"
        and loopback
        and settings.source_s3_allow_insecure_loopback
        and settings.app_env.casefold() != "production"
    ):
        raise ConnectorConfigurationError("SOURCE_S3_ENDPOINT_URL must use HTTPS")
    return origin


def _safe_s3_inventory_path(bucket: str, raw_item: object) -> str:
    key = raw_item.get("Key") if isinstance(raw_item, dict) else None
    if isinstance(key, str):
        return f"s3://{bucket}/{quote(key[:4000], safe='/')}"
    return f"s3://{bucket}/<invalid-object>"


def _s3_transport_error(operation: str, error: BotoCoreError | ClientError) -> ConnectorTransportError:
    code = "transport_error"
    if isinstance(error, ClientError):
        raw_code = error.response.get("Error", {}).get("Code")
        if isinstance(raw_code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", raw_code):
            code = raw_code
    return ConnectorTransportError(f"S3 {operation} failed ({code})")


def _normalize_manifest_url(root_uri: str, settings: Settings) -> str:
    raw = root_uri.strip()
    if not raw or any(character in raw for character in ("\x00", "\r", "\n")):
        raise ConnectorConfigurationError("HTTP manifest URL is invalid")
    try:
        parsed = urlsplit(raw)
        origin = _origin(parsed)
    except ValueError as exc:
        raise ConnectorConfigurationError("HTTP manifest URL is invalid") from exc
    if parsed.username is not None or parsed.password is not None or parsed.fragment or parsed.query:
        raise ConnectorConfigurationError("HTTP manifest URL cannot contain credentials, query, or fragment")
    if parsed.scheme not in {"http", "https"}:
        raise ConnectorConfigurationError("HTTP manifest URL must use HTTPS")
    loopback = _is_loopback_host(parsed.hostname or "")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http"
        and loopback
        and settings.source_http_allow_insecure_loopback
        and settings.app_env.casefold() != "production"
    ):
        raise ConnectorConfigurationError("HTTP manifest URL must use HTTPS")
    allowed_origins = {_normalize_allowed_origin(item) for item in settings.source_http_allowed_origins}
    if origin not in allowed_origins:
        raise ConnectorConfigurationError("HTTP manifest origin is not present in SOURCE_HTTP_ALLOWED_ORIGINS")
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.casefold(), origin.removeprefix(f"{parsed.scheme.casefold()}://"), path, "", ""))


def _normalize_allowed_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        origin = _origin(parsed)
    except ValueError as exc:
        raise ConnectorConfigurationError("SOURCE_HTTP_ALLOWED_ORIGINS contains an invalid origin") from exc
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ConnectorConfigurationError("SOURCE_HTTP_ALLOWED_ORIGINS entries must be origins without paths")
    return origin


def _normalize_download_url(root_uri: str, download_url: str) -> str:
    if any(character in download_url for character in ("\x00", "\r", "\n")):
        raise ConnectorConfigurationError("HTTP manifest download_url is invalid")
    resolved = urljoin(root_uri, download_url)
    try:
        root = urlsplit(root_uri)
        candidate = urlsplit(resolved)
        candidate_origin = _origin(candidate)
    except ValueError as exc:
        raise ConnectorConfigurationError("HTTP manifest download_url is invalid") from exc
    if candidate.username or candidate.password or candidate.fragment:
        raise ConnectorConfigurationError("HTTP manifest download_url cannot contain credentials or fragments")
    if candidate_origin != _origin(root):
        raise ConnectorConfigurationError("HTTP manifest download_url must use the manifest origin")
    return urlunsplit((candidate.scheme, candidate.netloc, candidate.path, candidate.query, ""))


def _origin(parsed: SplitResult) -> str:
    scheme = str(parsed.scheme).casefold()
    hostname = parsed.hostname
    if scheme not in {"http", "https"} or not hostname:
        raise ValueError("Invalid URL origin")
    host = hostname.casefold().encode("idna").decode("ascii")
    port = parsed.port
    default_port = 443 if scheme == "https" else 80
    rendered_host = f"[{host}]" if ":" in host else host
    port_suffix = f":{port}" if port is not None and port != default_port else ""
    return f"{scheme}://{rendered_host}{port_suffix}"


def _is_loopback_host(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def _normalize_logical_path(value: str) -> str:
    if not value or value.startswith("/") or value.endswith("/") or "\\" in value or "\x00" in value:
        raise ConnectorConfigurationError("HTTP manifest logical_path must be a relative POSIX file path")
    path = PurePosixPath(value)
    normalized = path.as_posix()
    if normalized != value or any(part in {"", ".", ".."} for part in path.parts):
        raise ConnectorConfigurationError("HTTP manifest logical_path is not canonical")
    return normalized


def _matches(relative_path: str, patterns: list[str]) -> bool:
    normalized = relative_path.casefold()
    return any(fnmatch.fnmatchcase(normalized, pattern.replace("\\", "/").casefold()) for pattern in patterns)


def _request_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/json, application/octet-stream;q=0.9",
        "Authorization": f"Bearer {token}",
        "User-Agent": "pharma-intelligence-http-manifest/1.0",
    }


def _require_success(response: httpx.Response, resource_name: str) -> None:
    if response.status_code < 200 or response.status_code >= 300:
        raise ConnectorTransportError(f"{resource_name} request returned HTTP {response.status_code}")


def _http_transport_error(resource_name: str, error: httpx.HTTPError) -> ConnectorTransportError:
    """Preserve safe transport diagnostics without recording URLs or payloads."""
    if isinstance(error, httpx.HTTPStatusError):
        return ConnectorTransportError(f"{resource_name} request returned HTTP {error.response.status_code}")
    return ConnectorTransportError(f"{resource_name} request failed ({type(error).__name__})")


def _validate_content_length(response: httpx.Response, maximum: int) -> None:
    raw_length = response.headers.get("content-length")
    if raw_length is None:
        return
    try:
        content_length = int(raw_length)
    except ValueError as exc:
        raise ConnectorTransportError("HTTP response Content-Length is invalid") from exc
    if content_length < 0 or content_length > maximum:
        raise ConnectorTransportError("HTTP response Content-Length exceeds the declared limit")


def _read_bounded(response: httpx.Response, maximum: int) -> bytes:
    _validate_content_length(response, maximum)
    payload = bytearray()
    for chunk in response.iter_bytes(chunk_size=min(64 * 1024, maximum + 1)):
        payload.extend(chunk)
        if len(payload) > maximum:
            raise ConnectorTransportError("HTTP manifest response exceeded SOURCE_HTTP_MAX_MANIFEST_BYTES")
    return bytes(payload)


def _inventory_sha256(inventory: list[dict[str, object]]) -> str:
    return hashlib.sha256(
        json.dumps(inventory, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
