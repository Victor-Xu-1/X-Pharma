from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pharma_intel.config import Settings
from pharma_intel.ingest.clinicaltrials_sync import advance_date_window, prepare_date_window
from pharma_intel.ingest.connectors import (
    ConnectorCapabilities,
    ConnectorConfigurationError,
    ConnectorTransportError,
    DiscoveryBatch,
    SourceObject,
    _cursor_payload,
    _http_transport_error,
    _inventory_sha256,
    _is_non_negative_integer,
    _is_sha256,
    _require_success,
    _SourceRateLimiter,
)
from pharma_intel.ingest.public_sync import DateWindowSyncRule, PublicSyncState, read_sync_state
from pharma_intel.models import DataSource, DataSourceType
from pharma_intel.product import SOURCE_USER_AGENT

CLINICALTRIALS_GOV_STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"
CLINICALTRIALS_GOV_STUDY_URL = "https://clinicaltrials.gov/study"
CLINICALTRIALS_GOV_NCT_ID = re.compile(r"^NCT[0-9]{8}$")
ClinicalTrialsGovSort = Literal[
    "LastUpdatePostDate:asc",
    "LastUpdatePostDate:desc",
    "StudyFirstPostDate:asc",
    "StudyFirstPostDate:desc",
]


class ClinicalTrialsGovRoutingRule(DateWindowSyncRule):
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
            rule = self._routing_rule(source)
            if rule.sync_mode == "continuous":
                read_sync_state(_cursor_payload(source.connector_cursor) or {}, rule, "clinicaltrials_gov")
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
        if rule.sync_mode == "continuous":
            return self._discover_continuous(source, rule)
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

    def _discover_continuous(self, source: DataSource, rule: ClinicalTrialsGovRoutingRule) -> DiscoveryBatch:
        now = datetime.now(UTC)
        previous = read_sync_state(source.connector_cursor or {}, rule, "clinicaltrials_gov")
        state = prepare_date_window(rule, previous, now)
        page_token = state.page_token
        seen_tokens = {page_token} if page_token is not None else set()
        objects: list[SourceObject] = []
        seen_paths: set[str] = set()
        total_count: int | None = None
        for _ in range(self.settings.source_http_max_pages):
            page_size = min(rule.page_size, rule.max_records - len(objects))
            page = self._fetch_page(source, rule, page_token=page_token, page_size=page_size, window=state)
            if len(page.studies) > page_size or (not page.studies and page.nextPageToken is not None):
                raise ConnectorTransportError("ClinicalTrials.gov returned an invalid pagination count")
            total_count = page.totalCount if page.totalCount is not None else total_count
            for study in page.studies:
                item = self._source_object(source, study)
                if item.logical_path in seen_paths:
                    raise ConnectorTransportError("ClinicalTrials.gov returned a duplicate NCT identifier")
                seen_paths.add(item.logical_path)
                objects.append(item)
            next_token = page.nextPageToken
            if next_token is not None and next_token in seen_tokens:
                raise ConnectorTransportError("ClinicalTrials.gov pagination token repeated")
            if next_token is not None:
                seen_tokens.add(next_token)
            page_token = next_token
            if page_token is None or len(objects) >= rule.max_records:
                break
        state = advance_date_window(rule, state, page_token, len(objects), now)
        state = PublicSyncState.model_validate(state.model_dump())
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
                "kind": "clinicaltrials_gov",
                "query_term": rule.query_term,
                "max_records": rule.max_records,
                "sort": rule.sort,
                "object_count": len(objects),
                "reported_total_count": total_count,
                "inventory_sha256": _inventory_sha256(inventory),
                "fetched_at": now.isoformat(),
                "sync_state": state.model_dump(mode="json"),
            },
            authoritative_inventory=False,
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
        window: PublicSyncState | None = None,
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
        if window is not None:
            params["filter.advanced"] = f"AREA[LastUpdatePostDate]RANGE[{window.window_start},{window.window_end}]"
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
