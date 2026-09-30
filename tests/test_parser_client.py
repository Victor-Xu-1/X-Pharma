from __future__ import annotations

import hashlib
from pathlib import Path

import httpx
import pytest
import respx

from pharma_intel.config import Settings
from pharma_intel.ingest.parser_client import (
    OcrFallbackDocumentParser,
    ParserServiceClient,
    ParserServiceUnavailable,
    _parser_ssl_context,
)
from pharma_intel.ingest.parsers import DocumentOcrRequired, DocumentParseError, ParsedDocument


def _client() -> ParserServiceClient:
    return ParserServiceClient(
        "http://parser.test",
        "test-parser-service-token-1234567890",
        connect_timeout_seconds=1,
        request_timeout_seconds=10,
        max_file_bytes=1_048_576,
        verify=True,
    )


@respx.mock
def test_parser_client_streams_exact_bytes_and_verifies_response_digests(tmp_path: Path) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("EGFR evidence", encoding="utf-8")
    source_bytes = source.read_bytes()
    text = "parsed EGFR evidence"
    route = respx.post("http://parser.test/internal/v1/parse").mock(
        return_value=httpx.Response(
            200,
            json={
                "protocol_version": 1,
                "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "metadata": {"page_count": 1},
                "parser_name": "test-parser",
                "parser_version": "1",
            },
        )
    )

    parsed = _client().parse(source, 100_000)

    assert parsed.text == text
    request = route.calls.last.request
    assert request.content == source_bytes
    assert request.headers["authorization"] == "Bearer test-parser-service-token-1234567890"
    assert request.headers["x-content-sha256"] == hashlib.sha256(source_bytes).hexdigest()
    assert request.url.params["filename"] == "evidence.md"


@respx.mock
def test_parser_client_preserves_safe_service_rejection(tmp_path: Path) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("evidence", encoding="utf-8")
    respx.post("http://parser.test/internal/v1/parse").mock(
        return_value=httpx.Response(
            422,
            json={"detail": {"code": "document_parse_rejected", "message": "Encrypted PDF is unsupported"}},
        )
    )

    with pytest.raises(DocumentParseError, match="Encrypted PDF"):
        _client().parse(source, 100_000)


@respx.mock
def test_parser_client_rejects_mismatched_response_digest(tmp_path: Path) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("evidence", encoding="utf-8")
    respx.post("http://parser.test/internal/v1/parse").mock(
        return_value=httpx.Response(
            200,
            json={
                "protocol_version": 1,
                "source_sha256": "0" * 64,
                "text": "parsed",
                "text_sha256": hashlib.sha256(b"parsed").hexdigest(),
                "metadata": {},
                "parser_name": "test",
                "parser_version": "1",
            },
        )
    )

    with pytest.raises(DocumentParseError, match="mismatched source digest"):
        _client().parse(source, 100_000)


@respx.mock
@pytest.mark.parametrize("status_code", [408, 425, 429, 500, 502, 503, 504])
def test_parser_client_marks_capacity_and_service_failures_retryable(
    tmp_path: Path,
    status_code: int,
) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("evidence", encoding="utf-8")
    respx.post("http://parser.test/internal/v1/parse").mock(
        return_value=httpx.Response(status_code, json={"detail": {"message": "temporarily unavailable"}})
    )

    with pytest.raises(ParserServiceUnavailable, match="temporarily unavailable"):
        _client().parse(source, 100_000)


@respx.mock
def test_parser_client_preserves_safe_retryable_service_error_code(tmp_path: Path) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("evidence", encoding="utf-8")
    respx.post("http://parser.test/internal/v1/parse").mock(
        return_value=httpx.Response(
            429,
            headers={"Retry-After": "30"},
            json={"detail": {"code": "parser_capacity_exhausted", "message": "capacity exhausted"}},
        )
    )

    with pytest.raises(ParserServiceUnavailable) as failure:
        _client().parse(source, 100_000)

    assert failure.value.error_code == "parser_capacity_exhausted"


@respx.mock
def test_parser_client_marks_transport_failure_retryable(tmp_path: Path) -> None:
    source = tmp_path / "evidence.md"
    source.write_text("evidence", encoding="utf-8")
    respx.post("http://parser.test/internal/v1/parse").mock(side_effect=httpx.ConnectError("offline"))

    with pytest.raises(ParserServiceUnavailable, match="service is unavailable"):
        _client().parse(source, 100_000)


def test_parser_client_rejects_partial_mtls_identity() -> None:
    settings = Settings(
        _env_file=None,
        parser_service_client_cert="/run/secrets/parser-client/tls.crt",
    )

    with pytest.raises(RuntimeError, match="must be configured together"):
        _parser_ssl_context(settings)


@respx.mock
def test_parser_client_preserves_typed_ocr_requirement(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"scan")
    respx.post("http://parser.test/internal/v1/parse").mock(
        return_value=httpx.Response(
            422,
            json={"detail": {"code": "document_ocr_required", "message": "OCR required"}},
        )
    )

    with pytest.raises(DocumentOcrRequired, match="OCR required"):
        _client().parse(source, 100_000)


def test_ocr_fallback_is_used_only_for_typed_ocr_requirement(tmp_path: Path) -> None:
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"scan")
    parsed = ParsedDocument("recognized", {}, "paddleocr", "3.5.0")

    class Primary:
        def __init__(self, failure: DocumentParseError) -> None:
            self.failure = failure

        def parse(self, _path: Path, _max_chars: int) -> ParsedDocument:
            raise self.failure

    class Ocr:
        calls = 0

        def parse(self, _path: Path, _max_chars: int) -> ParsedDocument:
            self.calls += 1
            return parsed

    ocr = Ocr()
    parser = OcrFallbackDocumentParser(Primary(DocumentOcrRequired("OCR required")), ocr)
    assert parser.parse(source, 100_000) == parsed
    assert ocr.calls == 1

    parser = OcrFallbackDocumentParser(Primary(DocumentParseError("corrupt")), ocr)
    with pytest.raises(DocumentParseError, match="corrupt"):
        parser.parse(source, 100_000)
    assert ocr.calls == 1
