from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from pharma_intel.config import Settings
from pharma_intel.ingest import parser_probe
from pharma_intel.ingest.parser_client import InProcessDocumentParser


def test_parser_probe_generates_real_formats_and_non_sensitive_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        parser_backend="service",
        parser_service_url="http://parser.test",
        parser_service_token="test-parser-service-token-1234567890",  # noqa: S106
        parser_max_text_chars=1_000_000,
    )
    monkeypatch.setattr(parser_probe, "get_settings", lambda: settings)
    monkeypatch.setattr(parser_probe, "build_document_parser", lambda _: InProcessDocumentParser())
    monkeypatch.setattr(parser_probe, "_protocol_rejections", lambda _url, _token: (401, 400))

    report = parser_probe.probe()

    assert report["status"] == "passed"
    assert report["document_count"] == 11
    documents = report["documents"]
    assert isinstance(documents, list)
    assert {document["suffix"] for document in documents} == {
        ".md",
        ".html",
        ".docx",
        ".pptx",
        ".xlsx",
        ".pdf",
        ".sdf",
        ".mol",
        ".pdb",
        ".cif",
        ".mmcif",
    }
    assert all("text" not in document for document in documents)


@respx.mock
def test_parser_probe_checks_authentication_and_digest_rejection() -> None:
    route = respx.post("http://parser.test/internal/v1/parse").mock(
        side_effect=[httpx.Response(401), httpx.Response(400)]
    )

    statuses = parser_probe._protocol_rejections(
        "http://parser.test",
        "test-parser-service-token-1234567890",
    )

    assert statuses == (401, 400)
    assert route.call_count == 2
    assert route.calls[0].request.headers["authorization"] == "Bearer invalid-parser-token"
    assert route.calls[1].request.headers["x-content-sha256"] == "0" * 64


def test_parser_probe_evidence_write_is_atomic_and_non_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "parser-report.json"

    parser_probe._write_atomic(output, b'{"status":"passed"}\n')

    assert output.read_bytes() == b'{"status":"passed"}\n'
    assert output.stat().st_mode & 0o077 == 0
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        parser_probe._write_atomic(output, b"replacement")
