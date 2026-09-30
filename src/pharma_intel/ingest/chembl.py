from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import (
    ConnectorCapabilities,
    ConnectorConfigurationError,
    ConnectorTransportError,
    DiscoveryBatch,
    SourceObject,
    _cursor_payload,
    _http_transport_error,
    _is_non_negative_integer,
    _is_sha256,
)
from pharma_intel.models import DataSource, DataSourceType
from pharma_intel.product import SOURCE_USER_AGENT

CHEMBL_API_ROOT = "https://www.ebi.ac.uk/chembl/api/data/"
CHEMBL_MECHANISM_URL = f"{CHEMBL_API_ROOT}mechanism.json"
CHEMBL_TARGET_URL = f"{CHEMBL_API_ROOT}target/{{target_chembl_id}}.json"
CHEMBL_MOLECULE_URL = f"{CHEMBL_API_ROOT}molecule.json"
CHEMBL_ID_PATTERN = re.compile(r"^CHEMBL[0-9]+$")
CHEMBL_MAX_PAGE_SIZE = 100
CHEMBL_SNAPSHOT_SCHEMA = "pharma.chembl.mechanism.v1"
CHEMBL_SNAPSHOT_TIME = datetime(1970, 1, 1, tzinfo=UTC)


class ChemblRoutingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_chembl_id: str = Field(min_length=7, max_length=32)
    max_records: int = Field(default=100, ge=1, le=1000)
    page_size: int = Field(default=100, ge=1, le=CHEMBL_MAX_PAGE_SIZE)

    @field_validator("target_chembl_id")
    @classmethod
    def normalize_target_id(cls, value: str) -> str:
        normalized = value.strip().upper()
        if CHEMBL_ID_PATTERN.fullmatch(normalized) is None:
            raise ValueError("target_chembl_id must be a valid ChEMBL identifier")
        return normalized


@dataclass(frozen=True)
class ChemblObjectHandle:
    content: bytes


class _ChemblRateLimiter:
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


class ChEMBLSourceConnector:
    """Reads bounded ChEMBL target-mechanism records into immutable snapshots."""

    source_type = DataSourceType.CHEMBL
    capabilities = ConnectorCapabilities(
        connector_id="chembl-rest-v1",
        incremental=True,
        replayable=True,
        credentials_required=False,
    )

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport
        self.rate_limiter = _ChemblRateLimiter()

    def normalize_root_uri(self, root_uri: str) -> str:
        if root_uri.strip() != CHEMBL_API_ROOT:
            raise ConnectorConfigurationError(f"ChEMBL sources must use {CHEMBL_API_ROOT}")
        return CHEMBL_API_ROOT

    def validate_configuration(self, source: DataSource) -> list[str]:
        errors: list[str] = []
        try:
            self.normalize_root_uri(source.root_uri)
        except ValueError as exc:
            errors.append(str(exc))
        if source.credential_ref:
            errors.append("ChEMBL sources do not accept connector credentials")
        if source.data_classification != "public":
            errors.append("ChEMBL sources must use the public data classification")
        if "public:chembl" not in source.authorization_scopes:
            errors.append("ChEMBL sources require authorization scope public:chembl")
        if source.stable_seconds != 0:
            errors.append("ChEMBL sources require stable_seconds=0")
        if source.rate_limit_per_minute > 60:
            errors.append("ChEMBL sources cannot exceed 60 requests per minute")
        try:
            self._routing_rule(source)
        except ConnectorConfigurationError as exc:
            errors.append(str(exc))
        cursor = _cursor_payload(source.connector_cursor)
        if cursor is None or (
            cursor
            and (
                cursor.get("schema_version") != "1.0"
                or cursor.get("kind") != "chembl_mechanism"
                or not _is_sha256(cursor.get("inventory_sha256"))
                or not _is_non_negative_integer(cursor.get("object_count"))
                or not _is_non_negative_integer(cursor.get("reported_total_count"))
            )
        ):
            errors.append("ChEMBL connector cursor is invalid")
        return errors

    def discover(self, source: DataSource) -> DiscoveryBatch:
        errors = self.validate_configuration(source)
        if errors:
            raise ConnectorConfigurationError(errors[0])
        rule = self._routing_rule(source)
        target = self._request_json(
            source,
            CHEMBL_TARGET_URL.format(target_chembl_id=rule.target_chembl_id),
            {},
            "ChEMBL target",
            maximum_bytes=1_048_576,
        )
        target_summary = _target_summary(target, rule.target_chembl_id)
        mechanisms, reported_total = self._discover_mechanisms(source, rule)
        molecule_ids = list(dict.fromkeys(str(item["molecule_chembl_id"]) for item in mechanisms))
        molecules = self._discover_molecules(source, molecule_ids)

        objects: list[SourceObject] = []
        for mechanism in mechanisms:
            mechanism_id = int(mechanism["mec_id"])
            molecule_id = str(mechanism["molecule_chembl_id"])
            molecule = molecules.get(molecule_id)
            if molecule is None:
                raise ConnectorTransportError(f"ChEMBL molecule metadata is missing {molecule_id}")
            content = _snapshot_bytes(
                target_summary=target_summary,
                molecule=_molecule_summary(molecule, molecule_id),
                mechanism=_mechanism_summary(mechanism),
                target_chembl_id=rule.target_chembl_id,
            )
            if len(content) > source.max_file_bytes:
                raise ConnectorConfigurationError(f"ChEMBL mechanism {mechanism_id} exceeds max_file_bytes")
            digest = hashlib.sha256(content).hexdigest()
            logical_path = f"mechanisms/{rule.target_chembl_id}/{mechanism_id}.json"
            objects.append(
                SourceObject(
                    logical_path=logical_path,
                    source_uri=f"{CHEMBL_MECHANISM_URL}?{urlencode({'mec_id': mechanism_id})}",
                    file_name=f"{mechanism_id}.json",
                    extension=".json",
                    size_bytes=len(content),
                    modified_at=CHEMBL_SNAPSHOT_TIME,
                    processing_mode="parse",
                    dataset_key=source.dataset_key,
                    content_sha256=digest,
                    handle=ChemblObjectHandle(content=content),
                    source_fingerprint=digest,
                )
            )
        objects.sort(key=lambda item: item.logical_path)
        inventory: list[dict[str, object]] = [
            {
                "content_sha256": item.content_sha256,
                "logical_path": item.logical_path,
                "modified_at": item.modified_at.isoformat(),
                "size_bytes": item.size_bytes,
            }
            for item in objects
        ]
        return DiscoveryBatch(
            objects=objects,
            errors=[],
            excluded_count=0,
            cursor={
                "schema_version": "1.0",
                "kind": "chembl_mechanism",
                "target_chembl_id": rule.target_chembl_id,
                "object_count": len(objects),
                "reported_total_count": reported_total,
                "inventory_sha256": _inventory_sha256(inventory),
                "fetched_at": datetime.now(UTC).isoformat(),
            },
            authoritative_inventory=False,
            deleted_paths=[],
        )

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, ChemblObjectHandle):
            raise ConnectorConfigurationError("ChEMBL connector received an invalid object handle")
        content = item.handle.content
        if len(content) != item.size_bytes or hashlib.sha256(content).hexdigest() != item.content_sha256:
            raise ConnectorTransportError("ChEMBL source object changed after discovery")
        with tempfile.TemporaryDirectory(prefix="pharma-chembl-") as temporary:
            snapshot = Path(temporary) / item.file_name
            with snapshot.open("xb") as destination:
                destination.write(content)
                destination.flush()
                os.fsync(destination.fileno())
            yield snapshot

    def _discover_mechanisms(
        self,
        source: DataSource,
        rule: ChemblRoutingRule,
    ) -> tuple[list[dict[str, Any]], int]:
        first = self._request_json(
            source,
            CHEMBL_MECHANISM_URL,
            {
                "target_chembl_id": rule.target_chembl_id,
                "limit": str(rule.page_size),
                "offset": "0",
            },
            "ChEMBL mechanism",
            maximum_bytes=max(1_048_576, source.max_file_bytes * rule.page_size),
        )
        reported_total = _page_total(first, "ChEMBL mechanism")
        requested_count = min(reported_total, rule.max_records)
        mechanisms: list[dict[str, Any]] = []
        seen_ids: set[int] = set()
        for offset in range(0, requested_count, rule.page_size):
            page = (
                first
                if offset == 0
                else self._request_json(
                    source,
                    CHEMBL_MECHANISM_URL,
                    {
                        "target_chembl_id": rule.target_chembl_id,
                        "limit": str(min(rule.page_size, requested_count - offset)),
                        "offset": str(offset),
                    },
                    "ChEMBL mechanism",
                    maximum_bytes=max(1_048_576, source.max_file_bytes * rule.page_size),
                )
            )
            records = page.get("mechanisms")
            if not isinstance(records, list):
                raise ConnectorTransportError("ChEMBL mechanism response is missing mechanisms")
            expected = min(rule.page_size, requested_count - offset)
            if len(records) != expected:
                raise ConnectorTransportError("ChEMBL mechanism record count did not match the requested page")
            for record in records:
                if not isinstance(record, dict):
                    raise ConnectorTransportError("ChEMBL mechanism record is not an object")
                mechanism_id = record.get("mec_id")
                molecule_id = str(record.get("molecule_chembl_id") or "").upper()
                target_id = str(record.get("target_chembl_id") or "").upper()
                if not isinstance(mechanism_id, int) or mechanism_id <= 0:
                    raise ConnectorTransportError("ChEMBL mechanism record has an invalid mec_id")
                if mechanism_id in seen_ids:
                    raise ConnectorTransportError("ChEMBL mechanism response contains a duplicate mec_id")
                if target_id != rule.target_chembl_id or CHEMBL_ID_PATTERN.fullmatch(molecule_id) is None:
                    raise ConnectorTransportError("ChEMBL mechanism record has an invalid target or molecule ID")
                if not str(record.get("mechanism_of_action") or "").strip():
                    raise ConnectorTransportError("ChEMBL mechanism record is missing mechanism_of_action")
                if record.get("max_phase") is None:
                    raise ConnectorTransportError("ChEMBL mechanism record is missing max_phase")
                seen_ids.add(mechanism_id)
                normalized = dict(record)
                normalized["molecule_chembl_id"] = molecule_id
                normalized["target_chembl_id"] = target_id
                mechanisms.append(normalized)
        return mechanisms, reported_total

    def _discover_molecules(self, source: DataSource, molecule_ids: list[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for offset in range(0, len(molecule_ids), CHEMBL_MAX_PAGE_SIZE):
            chunk = molecule_ids[offset : offset + CHEMBL_MAX_PAGE_SIZE]
            page = self._request_json(
                source,
                CHEMBL_MOLECULE_URL,
                {
                    "molecule_chembl_id__in": ",".join(chunk),
                    "limit": str(len(chunk)),
                    "offset": "0",
                },
                "ChEMBL molecule",
                maximum_bytes=max(1_048_576, source.max_file_bytes * len(chunk)),
            )
            molecules = page.get("molecules")
            if not isinstance(molecules, list):
                raise ConnectorTransportError("ChEMBL molecule response is missing molecules")
            for molecule in molecules:
                if not isinstance(molecule, dict):
                    raise ConnectorTransportError("ChEMBL molecule record is not an object")
                molecule_id = str(molecule.get("molecule_chembl_id") or "").upper()
                if molecule_id in result or molecule_id not in chunk:
                    raise ConnectorTransportError("ChEMBL molecule response contains an unexpected or duplicate ID")
                result[molecule_id] = molecule
        return result

    def _request_json(
        self,
        source: DataSource,
        url: str,
        params: dict[str, str],
        resource_name: str,
        *,
        maximum_bytes: int,
    ) -> dict[str, Any]:
        self.rate_limiter.wait(source.id, source.rate_limit_per_minute)
        try:
            with httpx.Client(
                timeout=httpx.Timeout(
                    connect=self.settings.source_http_connect_timeout_seconds,
                    read=self.settings.source_http_read_timeout_seconds,
                    write=self.settings.source_http_read_timeout_seconds,
                    pool=self.settings.source_http_connect_timeout_seconds,
                ),
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
                headers={
                    "Accept": "application/json",
                    "User-Agent": SOURCE_USER_AGENT,
                },
            ) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise _http_transport_error(resource_name, exc) from exc
        content_type = response.headers.get("content-type", "").partition(";")[0].strip().casefold()
        if content_type not in {"application/json", "application/vnd.api+json"}:
            raise ConnectorTransportError(f"{resource_name} response must use application/json")
        if len(response.content) > maximum_bytes:
            raise ConnectorTransportError(f"{resource_name} response exceeded the configured safety limit")
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise ConnectorTransportError(f"{resource_name} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ConnectorTransportError(f"{resource_name} response must be an object")
        return payload

    @staticmethod
    def _routing_rule(source: DataSource) -> ChemblRoutingRule:
        if len(source.routing_rules) != 1:
            raise ConnectorConfigurationError("ChEMBL sources require exactly one routing rule")
        try:
            return ChemblRoutingRule.model_validate(source.routing_rules[0])
        except ValidationError as exc:
            raise ConnectorConfigurationError("ChEMBL routing rule is invalid") from exc


def _page_total(payload: dict[str, Any], resource_name: str) -> int:
    page_meta = payload.get("page_meta")
    if not isinstance(page_meta, dict):
        raise ConnectorTransportError(f"{resource_name} response is missing page_meta")
    raw_total = page_meta.get("total_count")
    if not isinstance(raw_total, int) or isinstance(raw_total, bool) or raw_total < 0:
        raise ConnectorTransportError(f"{resource_name} response has an invalid total_count")
    return raw_total


def _target_summary(payload: dict[str, Any], expected_id: str) -> dict[str, Any]:
    target_id = str(payload.get("target_chembl_id") or "").upper()
    if target_id != expected_id:
        raise ConnectorTransportError("ChEMBL target response changed the requested target identity")
    pref_name = str(payload.get("pref_name") or "").strip()
    if not pref_name:
        raise ConnectorTransportError("ChEMBL target response is missing pref_name")
    gene_symbol: str | None = None
    uniprot_accession: str | None = None
    components = payload.get("target_components")
    if isinstance(components, list):
        component = next((item for item in components if isinstance(item, dict)), None)
        if component is not None:
            accession = str(component.get("accession") or "").strip().upper()
            uniprot_accession = accession[:20] or None
            synonyms = component.get("target_component_synonyms")
            if isinstance(synonyms, list):
                gene = next(
                    (
                        str(item.get("component_synonym") or "").strip()
                        for item in synonyms
                        if isinstance(item, dict) and item.get("syn_type") == "GENE_SYMBOL"
                    ),
                    "",
                )
                gene_symbol = gene[:80] or None
    return {
        "chembl_id": target_id,
        "pref_name": pref_name[:500],
        "target_type": str(payload.get("target_type") or "")[:120] or None,
        "organism": str(payload.get("organism") or "")[:160] or None,
        "gene_symbol": gene_symbol,
        "uniprot_accession": uniprot_accession,
    }


def _molecule_summary(payload: dict[str, Any], expected_id: str) -> dict[str, Any]:
    molecule_id = str(payload.get("molecule_chembl_id") or "").upper()
    if molecule_id != expected_id:
        raise ConnectorTransportError("ChEMBL molecule response changed the requested molecule identity")
    return {
        "chembl_id": molecule_id,
        "pref_name": str(payload.get("pref_name") or "").strip()[:500] or molecule_id,
        "molecule_type": str(payload.get("molecule_type") or "")[:120] or None,
        "max_phase": payload.get("max_phase"),
    }


def _mechanism_summary(payload: dict[str, Any]) -> dict[str, Any]:
    references = payload.get("mechanism_refs")
    safe_references = (
        [
            {
                "ref_id": str(item.get("ref_id") or "")[:240],
                "ref_type": str(item.get("ref_type") or "")[:120],
                "ref_url": str(item.get("ref_url") or "")[:2000],
            }
            for item in references
            if isinstance(item, dict)
        ]
        if isinstance(references, list)
        else []
    )
    return {
        "mec_id": payload["mec_id"],
        "target_chembl_id": str(payload["target_chembl_id"]).upper(),
        "molecule_chembl_id": str(payload["molecule_chembl_id"]).upper(),
        "action_type": str(payload.get("action_type") or "")[:120] or None,
        "mechanism_of_action": str(payload["mechanism_of_action"]).strip()[:500],
        "max_phase": payload["max_phase"],
        "direct_interaction": payload.get("direct_interaction"),
        "molecular_mechanism": payload.get("molecular_mechanism"),
        "mechanism_refs": safe_references[:20],
    }


def _snapshot_bytes(
    *,
    target_summary: dict[str, Any],
    molecule: dict[str, Any],
    mechanism: dict[str, Any],
    target_chembl_id: str,
) -> bytes:
    payload = {
        "schema_version": CHEMBL_SNAPSHOT_SCHEMA,
        "provider": "ChEMBL",
        "target": target_summary,
        "molecule": molecule,
        "mechanism": mechanism,
        "citation": {
            "locator": f"mechanism:{mechanism['mec_id']}",
            "quote": _citation_quote(mechanism),
        },
        "source": {
            "api_root": CHEMBL_API_ROOT,
            "mechanism_uri": f"{CHEMBL_MECHANISM_URL}?{urlencode({'mec_id': mechanism['mec_id']})}",
            "molecule_uri": f"{CHEMBL_API_ROOT}molecule/{molecule['chembl_id']}.json",
            "target_uri": CHEMBL_TARGET_URL.format(target_chembl_id=target_chembl_id),
            "license": "CC BY-SA 3.0",
            "license_uri": "https://www.ebi.ac.uk/chembl/",
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _citation_quote(mechanism: dict[str, Any]) -> str:
    return (
        f"mec_id={mechanism['mec_id']}; "
        f"target_chembl_id={mechanism['target_chembl_id']}; "
        f"molecule_chembl_id={mechanism['molecule_chembl_id']}; "
        f"max_phase={mechanism['max_phase']}; "
        f"mechanism_of_action={mechanism['mechanism_of_action']}"
    )[:4000]


def _inventory_sha256(inventory: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for item in inventory:
        digest.update(repr(sorted(item.items())).encode("utf-8"))
        digest.update(bytes((0,)))
    return digest.hexdigest()
