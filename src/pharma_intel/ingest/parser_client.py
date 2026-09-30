from __future__ import annotations

import hashlib
import json
import re
import ssl
import stat
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import httpx
from pydantic import ValidationError

from pharma_intel.config import Settings
from pharma_intel.ingest.parser_protocol import ParserResponse
from pharma_intel.ingest.parsers import DocumentOcrRequired, DocumentParseError, ParsedDocument, parse_document


class ParserServiceUnavailable(DocumentParseError):
    """The isolated parser cannot currently accept work and may be retried."""

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        self.error_code = error_code
        super().__init__(message)


class DocumentParser(Protocol):
    def parse(self, path: Path, max_chars: int) -> ParsedDocument: ...


class InProcessDocumentParser:
    def parse(self, path: Path, max_chars: int) -> ParsedDocument:
        return parse_document(path, max_chars)


class ParserServiceClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        connect_timeout_seconds: float,
        request_timeout_seconds: float,
        max_file_bytes: int,
        verify: bool | str | ssl.SSLContext,
        service_name: str = "isolated parser",
        emit_ocr_required: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.connect_timeout_seconds = connect_timeout_seconds
        self.request_timeout_seconds = request_timeout_seconds
        self.max_file_bytes = max_file_bytes
        self.verify = verify
        self.service_name = service_name
        self.emit_ocr_required = emit_ocr_required

    def parse(self, path: Path, max_chars: int) -> ParsedDocument:
        try:
            source_stat = path.lstat()
        except OSError as exc:
            raise DocumentParseError("Parser input is unavailable") from exc
        if not stat.S_ISREG(source_stat.st_mode) or path.is_symlink():
            raise DocumentParseError("Parser input must be a regular non-symlink file")
        if source_stat.st_size > self.max_file_bytes:
            raise DocumentParseError(f"Parser input exceeds the configured {self.max_file_bytes} byte service limit")
        source_sha256 = _sha256_file(path)
        timeout = httpx.Timeout(
            self.request_timeout_seconds,
            connect=self.connect_timeout_seconds,
            write=self.request_timeout_seconds,
            pool=self.connect_timeout_seconds,
        )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Length": str(source_stat.st_size),
            "Content-Type": "application/octet-stream",
            "X-Content-SHA256": source_sha256,
        }
        response_limit = max_chars * 4 + 4_194_304
        try:
            with httpx.Client(timeout=timeout, verify=self.verify, trust_env=False) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/internal/v1/parse",
                    params={"filename": path.name, "max_chars": max_chars},
                    headers=headers,
                    content=_file_chunks(path),
                ) as response:
                    payload = _read_limited(response, response_limit if response.status_code == 200 else 65_536)
                    status_code = response.status_code
        except (httpx.HTTPError, OSError) as exc:
            raise ParserServiceUnavailable(f"The {self.service_name} service is unavailable") from exc
        if status_code != 200:
            error_code, message = _service_error(payload, status_code, self.service_name)
            if status_code in {408, 425, 429, 500, 502, 503, 504}:
                raise ParserServiceUnavailable(message, error_code=error_code)
            if self.emit_ocr_required and status_code == 422 and error_code == "document_ocr_required":
                raise DocumentOcrRequired(message)
            raise DocumentParseError(message)
        try:
            result = ParserResponse.model_validate_json(payload)
        except ValidationError as exc:
            raise DocumentParseError("The isolated parser service returned an invalid response") from exc
        if result.source_sha256 != source_sha256:
            raise DocumentParseError("The isolated parser service returned a mismatched source digest")
        if result.text_sha256 != hashlib.sha256(result.text.encode("utf-8")).hexdigest():
            raise DocumentParseError("The isolated parser service returned a mismatched text digest")
        if not result.text.strip():
            raise DocumentParseError("The isolated parser service returned no extractable text")
        return ParsedDocument(result.text, result.metadata, result.parser_name, result.parser_version)


def _file_chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as source:
        while chunk := source.read(1_048_576):
            yield chunk


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    for chunk in _file_chunks(path):
        digest.update(chunk)
    return digest.hexdigest()


def _read_limited(response: httpx.Response, max_bytes: int) -> bytes:
    payload = bytearray()
    for chunk in response.iter_bytes():
        if len(payload) + len(chunk) > max_bytes:
            raise DocumentParseError("The isolated parser service response exceeded its protocol limit")
        payload.extend(chunk)
    return bytes(payload)


def _service_error(payload: bytes, status_code: int, service_name: str) -> tuple[str | None, str]:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, f"The {service_name} service rejected the document with HTTP {status_code}"
    detail = decoded.get("detail") if isinstance(decoded, dict) else None
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        message = detail["message"]
        candidate_code = detail.get("code")
        code = (
            candidate_code
            if isinstance(candidate_code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", candidate_code)
            else None
        )
        return code, "".join(character if character.isprintable() else "?" for character in message)[:1000]
    return None, f"The {service_name} service rejected the document with HTTP {status_code}"


class OcrFallbackDocumentParser:
    def __init__(self, primary: DocumentParser, ocr: DocumentParser) -> None:
        self.primary = primary
        self.ocr = ocr

    def parse(self, path: Path, max_chars: int) -> ParsedDocument:
        try:
            return self.primary.parse(path, max_chars)
        except DocumentOcrRequired:
            return self.ocr.parse(path, max_chars)


def build_document_parser(settings: Settings) -> DocumentParser:
    if settings.parser_backend == "in_process":
        primary: DocumentParser = InProcessDocumentParser()
    else:
        primary = ParserServiceClient(
            settings.parser_service_url,
            settings.parser_service_token,
            connect_timeout_seconds=settings.parser_service_connect_timeout_seconds,
            request_timeout_seconds=settings.parser_service_request_timeout_seconds,
            max_file_bytes=settings.parser_service_max_file_bytes,
            verify=_service_ssl_context(
                settings.parser_service_verify_certs,
                settings.parser_service_ca_certs,
                settings.parser_service_client_cert,
                settings.parser_service_client_key,
                "Parser",
            ),
        )
    if settings.ocr_backend == "disabled":
        return primary
    ocr = ParserServiceClient(
        settings.ocr_service_url,
        settings.ocr_service_token,
        connect_timeout_seconds=settings.ocr_service_connect_timeout_seconds,
        request_timeout_seconds=settings.ocr_service_request_timeout_seconds,
        max_file_bytes=settings.ocr_service_max_file_bytes,
        verify=_service_ssl_context(
            settings.ocr_service_verify_certs,
            settings.ocr_service_ca_certs,
            settings.ocr_service_client_cert,
            settings.ocr_service_client_key,
            "OCR",
        ),
        service_name="isolated OCR",
        emit_ocr_required=False,
    )
    return OcrFallbackDocumentParser(primary, ocr)


def _service_ssl_context(
    verify_certs: bool,
    ca_certs: str,
    client_cert: str,
    client_key: str,
    label: str,
) -> bool | str | ssl.SSLContext:
    certificate_paths = (client_cert, client_key)
    if any(certificate_paths) and not all(certificate_paths):
        raise RuntimeError(f"{label} mTLS client certificate and key must be configured together")
    if not all(certificate_paths):
        return ca_certs or verify_certs
    if ca_certs:
        context = ssl.create_default_context(cafile=ca_certs)
    elif verify_certs:
        context = ssl.create_default_context()
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    context.load_cert_chain(client_cert, client_key)
    return context


def _parser_ssl_context(settings: Settings) -> bool | str | ssl.SSLContext:
    return _service_ssl_context(
        settings.parser_service_verify_certs,
        settings.parser_service_ca_certs,
        settings.parser_service_client_cert,
        settings.parser_service_client_key,
        "Parser",
    )
