from __future__ import annotations

import hashlib
import os
import re
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from lxml import etree  # type: ignore[import-untyped]
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

PUBMED_EUTILITIES_ROOT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
PUBMED_ESEARCH_URL = f"{PUBMED_EUTILITIES_ROOT}esearch.fcgi"
PUBMED_EFETCH_URL = f"{PUBMED_EUTILITIES_ROOT}efetch.fcgi"
PUBMED_RECORD_URL = "https://pubmed.ncbi.nlm.nih.gov"
PMID_PATTERN = re.compile(r"^[0-9]{1,12}$")
NCBI_TOOL_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


class PubMedRoutingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_term: str = Field(min_length=1, max_length=2000)
    max_records: int = Field(default=100, ge=1, le=1000)
    page_size: int = Field(default=100, ge=1, le=200)
    include_abstract: bool = False

    @field_validator("query_term")
    @classmethod
    def normalize_query_term(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized or any(character in normalized for character in ("\x00", "\r", "\n")):
            raise ValueError("query_term contains invalid characters")
        return normalized


@dataclass(frozen=True)
class PubMedObjectHandle:
    content: bytes


class _RequestRateLimiter:
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


class PubMedSourceConnector:
    """Reads bounded PubMed metadata from NCBI E-utilities into immutable snapshots."""

    source_type = DataSourceType.PUBMED
    capabilities = ConnectorCapabilities(
        connector_id="pubmed-eutilities-v1",
        incremental=True,
        replayable=True,
        credentials_required=False,
    )

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport
        self.rate_limiter = _RequestRateLimiter()

    def normalize_root_uri(self, root_uri: str) -> str:
        if root_uri.strip() != PUBMED_EUTILITIES_ROOT:
            raise ConnectorConfigurationError(f"PubMed sources must use {PUBMED_EUTILITIES_ROOT}")
        return PUBMED_EUTILITIES_ROOT

    def validate_configuration(self, source: DataSource) -> list[str]:
        errors: list[str] = []
        try:
            self.normalize_root_uri(source.root_uri)
        except ValueError as exc:
            errors.append(str(exc))
        if source.credential_ref:
            errors.append("PubMed sources do not accept connector credentials in v1")
        if source.data_classification != "public":
            errors.append("PubMed sources must use the public data classification")
        if "public:ncbi-pubmed-metadata" not in source.authorization_scopes:
            errors.append("PubMed sources require authorization scope public:ncbi-pubmed-metadata")
        if source.stable_seconds != 0:
            errors.append("PubMed sources require stable_seconds=0")
        if source.rate_limit_per_minute > 180:
            errors.append("PubMed sources without an API key cannot exceed 180 requests per minute")
        if not NCBI_TOOL_PATTERN.fullmatch(self.settings.source_ncbi_tool.strip()):
            errors.append("SOURCE_NCBI_TOOL must contain only letters, digits, dots, underscores, or hyphens")
        email = self.settings.source_ncbi_email.strip()
        if email and not EMAIL_PATTERN.fullmatch(email):
            errors.append("SOURCE_NCBI_EMAIL must be a valid email address when configured")
        try:
            rule = self._routing_rule(source)
            if rule.include_abstract and "public:ncbi-pubmed-abstracts" not in source.authorization_scopes:
                errors.append("PubMed abstract ingestion requires authorization scope public:ncbi-pubmed-abstracts")
        except ConnectorConfigurationError as exc:
            errors.append(str(exc))
        cursor = _cursor_payload(source.connector_cursor)
        if cursor is None or (
            cursor
            and (
                cursor.get("schema_version") != "1.0"
                or cursor.get("kind") != "pubmed"
                or not _is_sha256(cursor.get("inventory_sha256"))
                or not _is_non_negative_integer(cursor.get("object_count"))
                or not _is_non_negative_integer(cursor.get("reported_total_count"))
            )
        ):
            errors.append("PubMed connector cursor is invalid")
        return errors

    def discover(self, source: DataSource) -> DiscoveryBatch:
        errors = self.validate_configuration(source)
        if errors:
            raise ConnectorConfigurationError(errors[0])
        rule = self._routing_rule(source)
        search_root = self._request_xml(
            source,
            PUBMED_ESEARCH_URL,
            {
                **self._common_params(),
                "db": "pubmed",
                "term": rule.query_term,
                "usehistory": "y",
                "retmax": "0",
                "retmode": "xml",
                "sort": "pub date",
            },
            "NCBI ESearch",
            maximum_bytes=1_048_576,
        )
        if _local_name(search_root) != "eSearchResult":
            raise ConnectorTransportError("NCBI ESearch returned an unexpected XML document")
        if _first_text(search_root, "./ERROR"):
            raise ConnectorTransportError("NCBI ESearch rejected the configured PubMed query")
        reported_total = _required_integer(search_root, "./Count", "NCBI ESearch count")
        requested_count = min(reported_total, rule.max_records)
        if requested_count == 0:
            return self._batch(rule, [], reported_total)
        web_env = _first_text(search_root, "./WebEnv")
        query_key = _first_text(search_root, "./QueryKey")
        if not web_env or not query_key:
            raise ConnectorTransportError("NCBI ESearch did not return a replayable history cursor")

        objects: list[SourceObject] = []
        seen_pmids: set[str] = set()
        for page_number, retstart in enumerate(range(0, requested_count, rule.page_size), start=1):
            if page_number > self.settings.source_http_max_pages:
                raise ConnectorTransportError("PubMed source exceeded SOURCE_HTTP_MAX_PAGES")
            retmax = min(rule.page_size, requested_count - retstart)
            root = self._request_xml(
                source,
                PUBMED_EFETCH_URL,
                {
                    **self._common_params(),
                    "db": "pubmed",
                    "query_key": query_key,
                    "WebEnv": web_env,
                    "retstart": str(retstart),
                    "retmax": str(retmax),
                    "retmode": "xml",
                },
                "NCBI EFetch",
                maximum_bytes=max(1_048_576, source.max_file_bytes * retmax),
            )
            if _local_name(root) != "PubmedArticleSet":
                raise ConnectorTransportError("NCBI EFetch returned an unexpected XML document")
            records = [child for child in root if _local_name(child) in {"PubmedArticle", "PubmedBookArticle"}]
            if len(records) != retmax:
                raise ConnectorTransportError("NCBI EFetch record count did not match the requested history page")
            for record in records:
                pmid = _pubmed_pmid(record)
                if pmid in seen_pmids:
                    raise ConnectorTransportError("NCBI EFetch returned a duplicate PMID")
                seen_pmids.add(pmid)
                objects.append(self._source_object(source, record, rule.include_abstract))
        if len(objects) != requested_count:
            raise ConnectorTransportError("NCBI EFetch record count did not match the ESearch history set")
        return self._batch(rule, objects, reported_total)

    @contextmanager
    def materialize(self, item: SourceObject) -> Iterator[Path]:
        if not isinstance(item.handle, PubMedObjectHandle):
            raise ConnectorConfigurationError("PubMed connector received an invalid object handle")
        content = item.handle.content
        if len(content) != item.size_bytes or hashlib.sha256(content).hexdigest() != item.content_sha256:
            raise ConnectorTransportError("PubMed source object changed after discovery")
        with tempfile.TemporaryDirectory(prefix="pharma-pubmed-") as temporary:
            snapshot = Path(temporary) / "article.md"
            with snapshot.open("xb") as destination:
                destination.write(content)
                destination.flush()
                os.fsync(destination.fileno())
            yield snapshot

    def _batch(
        self,
        rule: PubMedRoutingRule,
        objects: list[SourceObject],
        reported_total: int,
    ) -> DiscoveryBatch:
        objects.sort(key=lambda item: item.logical_path)
        inventory = [
            {
                "content_sha256": item.content_sha256,
                "logical_path": item.logical_path,
                "modified_at": item.modified_at.isoformat(),
                "size_bytes": item.size_bytes,
            }
            for item in objects
        ]
        digest = hashlib.sha256()
        for item in inventory:
            digest.update(repr(sorted(item.items())).encode("utf-8"))
            digest.update(b"\0")
        return DiscoveryBatch(
            objects=objects,
            errors=[],
            excluded_count=0,
            cursor={
                "schema_version": "1.0",
                "kind": "pubmed",
                "query_term": rule.query_term,
                "max_records": rule.max_records,
                "include_abstract": rule.include_abstract,
                "object_count": len(objects),
                "reported_total_count": reported_total,
                "inventory_sha256": digest.hexdigest(),
                "fetched_at": datetime.now(UTC).isoformat(),
            },
            authoritative_inventory=False,
            deleted_paths=[],
        )

    def _source_object(self, source: DataSource, record: etree._Element, include_abstract: bool) -> SourceObject:
        pmid = _pubmed_pmid(record)
        content = _render_pubmed_markdown(record, include_abstract)
        if len(content) > source.max_file_bytes:
            raise ConnectorConfigurationError(f"PubMed article {pmid} exceeds max_file_bytes")
        digest = hashlib.sha256(content).hexdigest()
        return SourceObject(
            logical_path=f"articles/{pmid}.md",
            source_uri=f"{PUBMED_RECORD_URL}/{pmid}/",
            file_name=f"{pmid}.md",
            extension=".md",
            size_bytes=len(content),
            modified_at=datetime.combine(_pubmed_modified_date(record), datetime.min.time(), tzinfo=UTC),
            processing_mode="parse",
            dataset_key=source.dataset_key,
            content_sha256=digest,
            handle=PubMedObjectHandle(content=content),
            source_fingerprint=digest,
        )

    @staticmethod
    def _routing_rule(source: DataSource) -> PubMedRoutingRule:
        if len(source.routing_rules) != 1:
            raise ConnectorConfigurationError("PubMed sources require exactly one routing rule")
        try:
            return PubMedRoutingRule.model_validate(source.routing_rules[0])
        except ValidationError as exc:
            raise ConnectorConfigurationError("PubMed routing rule is invalid") from exc

    def _common_params(self) -> dict[str, str]:
        params = {"tool": self.settings.source_ncbi_tool.strip()}
        email = self.settings.source_ncbi_email.strip()
        if email:
            params["email"] = email
        return params

    def _request_xml(
        self,
        source: DataSource,
        url: str,
        params: dict[str, str],
        resource_name: str,
        *,
        maximum_bytes: int,
    ) -> etree._Element:
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
                headers={"Accept": "application/xml, text/xml", "User-Agent": SOURCE_USER_AGENT},
            ) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise _http_transport_error(resource_name, exc) from exc
        content_type = response.headers.get("content-type", "").partition(";")[0].strip().casefold()
        if content_type not in {"application/xml", "text/xml"}:
            raise ConnectorTransportError(f"{resource_name} response must use XML")
        if len(response.content) > maximum_bytes:
            raise ConnectorTransportError(f"{resource_name} response exceeded the configured safety limit")
        return _parse_xml(response.content, resource_name)


def _render_pubmed_markdown(record: etree._Element, include_abstract: bool) -> bytes:
    pmid = _pubmed_pmid(record)
    title = _element_text(_first_element(record, ".//*[local-name()='ArticleTitle']")) or f"PubMed record {pmid}"
    journal = _element_text(_first_element(record, ".//*[local-name()='Journal']/*[local-name()='Title']"))
    publication_date = _pubmed_publication_date_text(record)
    doi = ""
    for article_id in record.xpath(".//*[local-name()='ArticleId']"):
        if str(article_id.get("IdType", "")).casefold() == "doi":
            doi = _element_text(article_id)
            break
    authors = _pubmed_authors(record)
    publication_types = _unique_texts(record.xpath(".//*[local-name()='PublicationType']"))
    mesh_terms = _unique_texts(record.xpath(".//*[local-name()='MeshHeading']/*[local-name()='DescriptorName']"))
    chemicals = _unique_texts(record.xpath(".//*[local-name()='Chemical']/*[local-name()='NameOfSubstance']"))
    raw_record = etree.tostring(record, encoding="utf-8", with_tail=False)
    lines = [
        f"# {title}",
        "",
        "- Provider: NCBI PubMed",
        f"- PMID: {pmid}",
        f"- Canonical URL: {PUBMED_RECORD_URL}/{pmid}/",
        f"- Journal: {journal or 'Not supplied'}",
        f"- Publication date: {publication_date or 'Not supplied'}",
        f"- DOI: {doi or 'Not supplied'}",
        f"- Authors: {', '.join(authors) if authors else 'Not supplied'}",
        f"- Publication types: {', '.join(publication_types) if publication_types else 'Not supplied'}",
        f"- MeSH terms: {', '.join(mesh_terms) if mesh_terms else 'Not supplied'}",
        f"- Chemicals: {', '.join(chemicals) if chemicals else 'Not supplied'}",
        f"- Raw record SHA-256: {hashlib.sha256(raw_record).hexdigest()}",
        "- NCBI policy: https://www.ncbi.nlm.nih.gov/home/about/policies/",
        "",
        "## Abstract",
        "",
    ]
    if include_abstract:
        sections = record.xpath(".//*[local-name()='Abstract']/*[local-name()='AbstractText']")
        if sections:
            for section in sections:
                text = _element_text(section)
                if not text:
                    continue
                label = _clean_text(section.get("Label") or section.get("NlmCategory"))
                lines.extend([f"**{label}**: {text}" if label else text, ""])
        else:
            lines.extend(["No abstract supplied.", ""])
    else:
        lines.extend(["Omitted by source policy (include_abstract=false).", ""])
    return "\n".join(lines).encode("utf-8")


def _pubmed_pmid(record: etree._Element) -> str:
    pmid = _element_text(_first_element(record, ".//*[local-name()='PMID']"))
    if not PMID_PATTERN.fullmatch(pmid):
        raise ConnectorTransportError("PubMed record is missing a valid PMID")
    return pmid


def _pubmed_modified_date(record: etree._Element) -> date:
    for name in ("DateRevised", "DateCompleted"):
        element = _first_element(record, f".//*[local-name()='{name}']")
        if element is not None and (parsed := _date_from_parts(element)) is not None:
            return parsed
    return datetime.now(UTC).date()


def _date_from_parts(element: etree._Element) -> date | None:
    year_text = _first_text(element, "./*[local-name()='Year']")
    month_text = _first_text(element, "./*[local-name()='Month']")
    day_text = _first_text(element, "./*[local-name()='Day']")
    if not year_text.isdigit():
        return None
    month = int(month_text) if month_text.isdigit() else MONTHS.get(month_text[:3].casefold(), 1)
    day = int(day_text) if day_text.isdigit() else 1
    try:
        return date(int(year_text), month, day)
    except ValueError:
        return None


def _pubmed_publication_date_text(record: etree._Element) -> str:
    publication_date = _first_element(record, ".//*[local-name()='JournalIssue']/*[local-name()='PubDate']")
    if publication_date is None:
        return ""
    medline_date = _first_text(publication_date, "./*[local-name()='MedlineDate']")
    if medline_date:
        return medline_date
    parts = [
        _first_text(publication_date, "./*[local-name()='Year']"),
        _first_text(publication_date, "./*[local-name()='Month']"),
        _first_text(publication_date, "./*[local-name()='Day']"),
    ]
    return "-".join(part for part in parts if part)


def _pubmed_authors(record: etree._Element) -> list[str]:
    authors: list[str] = []
    for author in record.xpath(".//*[local-name()='AuthorList']/*[local-name()='Author']"):
        collective = _first_text(author, "./*[local-name()='CollectiveName']")
        if collective:
            authors.append(collective)
            continue
        display = " ".join(
            part
            for part in (
                _first_text(author, "./*[local-name()='LastName']"),
                _first_text(author, "./*[local-name()='Initials']"),
            )
            if part
        )
        if display:
            authors.append(display)
    return list(dict.fromkeys(authors))


def _unique_texts(elements: list[etree._Element]) -> list[str]:
    return list(dict.fromkeys(text for element in elements if (text := _element_text(element))))


def _parse_xml(payload: bytes, resource_name: str) -> etree._Element:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)
    try:
        return etree.fromstring(payload, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ConnectorTransportError(f"{resource_name} returned invalid XML") from exc


def _required_integer(root: etree._Element, xpath: str, field_name: str) -> int:
    raw = _first_text(root, xpath)
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConnectorTransportError(f"{field_name} is invalid") from exc
    if value < 0:
        raise ConnectorTransportError(f"{field_name} is invalid")
    return value


def _first_element(element: etree._Element, xpath: str) -> etree._Element | None:
    matches = element.xpath(xpath)
    return matches[0] if matches else None


def _first_text(element: etree._Element, xpath: str) -> str:
    return _element_text(_first_element(element, xpath))


def _element_text(element: etree._Element | None) -> str:
    return _clean_text("".join(element.itertext())) if element is not None else ""


def _clean_text(value: Any) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def _local_name(element: etree._Element) -> str:
    return str(etree.QName(element).localname)
