from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from importlib import import_module
from typing import Any

import anyio
import httpx
import pytest
from fastapi.testclient import TestClient

from pharma_intel.ingest.parser_service import ParserServiceSettings, create_app
from pharma_intel.ingest.parsers import ParsedDocument

TOKEN = "test-parser-service-token-1234567890"  # noqa: S105
Chem: Any = import_module("rdkit.Chem")


def _client() -> TestClient:
    settings = ParserServiceSettings(
        _env_file=None,
        token=TOKEN,
        max_file_bytes=1_048_576,
        max_text_chars=1_000_000,
        parser_timeout_seconds=20,
        parser_memory_bytes=1_073_741_824,
    )
    return TestClient(create_app(settings))


def _headers(payload: bytes, *, token: str = TOKEN) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
        "Content-Length": str(len(payload)),
        "X-Content-SHA256": hashlib.sha256(payload).hexdigest(),
    }


def test_parser_service_streams_and_parses_in_real_sandbox() -> None:
    payload = "中文 EGFR evidence".encode()

    response = _client().post(
        "/internal/v1/parse",
        params={"filename": "evidence.md", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["text"] == "中文 EGFR evidence"
    assert result["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["text_sha256"] == hashlib.sha256(result["text"].encode()).hexdigest()


def test_parser_service_validates_json_in_real_sandbox() -> None:
    payload = b'{"trial":{"nctId":"NCT00000001"},"z":1}'

    response = _client().post(
        "/internal/v1/parse",
        params={"filename": "NCT00000001.json", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["text"] == payload.decode()
    assert result["parser_name"] == "python-json"


def test_parser_service_parses_real_sdf_in_isolated_process() -> None:
    molecule = Chem.MolFromSmiles("CCO")
    assert molecule is not None
    molecule.SetProp("_Name", "Ethanol")
    payload = (Chem.MolToMolBlock(molecule) + "\n$$$$\n").encode()

    response = _client().post(
        "/internal/v1/parse",
        params={"filename": "ethanol.sdf", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["protocol_version"] == 2
    assert result["parser_name"] == "rdkit-sdf"
    assert result["metadata"]["record_preview"][0]["standard_inchi_key"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"


@pytest.mark.parametrize("suffix", ["xml", "nxml"])
def test_parser_service_parses_jats_xml_in_real_sandbox(suffix: str) -> None:
    payload = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink">
  <front>
    <article-meta>
      <article-id pub-id-type="pmcid">PMC1234567</article-id>
      <title-group><article-title>EGFR inhibitor evidence</article-title></title-group>
      <permissions>
        <license><license-p>This article is licensed under CC BY 4.0.</license-p>
          <ext-link xlink:href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</ext-link>
        </license>
      </permissions>
      <abstract><p>Osimertinib inhibits mutant EGFR.</p></abstract>
    </article-meta>
  </front>
  <body><sec><title>Results</title><p>Cell viability decreased.</p></sec></body>
</article>
"""

    response = _client().post(
        "/internal/v1/parse",
        params={"filename": f"evidence.{suffix}", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["parser_name"] == "lxml-jats"
    assert "EGFR inhibitor evidence" in result["text"]
    assert "Cell viability decreased." in result["text"]
    assert result["metadata"]["articles"][0]["identifiers"] == {"pmcid": "PMC1234567"}
    assert result["metadata"]["articles"][0]["license_references"] == ["https://creativecommons.org/licenses/by/4.0/"]


@pytest.mark.parametrize(
    "payload",
    [
        b"<root><p>generic XML is not a JATS article</p></root>",
        b'<!DOCTYPE article [<!ENTITY secret "blocked">]><article><body><p>&secret;</p></body></article>',
    ],
)
def test_parser_service_rejects_unsafe_or_non_jats_xml(payload: bytes) -> None:
    response = _client().post(
        "/internal/v1/parse",
        params={"filename": "evidence.xml", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "document_parse_rejected"


def test_parser_service_rejects_unauthorized_request_before_parsing() -> None:
    payload = b"evidence"

    response = _client().post(
        "/internal/v1/parse",
        params={"filename": "evidence.md", "max_chars": 100_000},
        headers=_headers(payload, token="wrong-token"),  # noqa: S106 - intentional rejection fixture.
        content=payload,
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "parser_authentication_required"


def test_parser_service_rejects_digest_mismatch() -> None:
    payload = b"evidence"
    headers = _headers(payload)
    headers["X-Content-SHA256"] = "0" * 64

    response = _client().post(
        "/internal/v1/parse",
        params={"filename": "evidence.md", "max_chars": 100_000},
        headers=headers,
        content=payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "source_digest_mismatch"


def test_parser_service_rejects_path_filename_and_unsupported_type() -> None:
    payload = b"evidence"
    client = _client()

    path_response = client.post(
        "/internal/v1/parse",
        params={"filename": "../evidence.md", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )
    unsupported_response = client.post(
        "/internal/v1/parse",
        params={"filename": "evidence.exe", "max_chars": 100_000},
        headers=_headers(payload),
        content=payload,
    )

    assert path_response.status_code == 400
    assert unsupported_response.status_code == 415


def test_parser_service_rejects_partial_tls_configuration() -> None:
    settings = ParserServiceSettings(
        _env_file=None,
        token=TOKEN,
        tls_cert_file="/run/secrets/parser/tls.crt",
    )

    with pytest.raises(RuntimeError, match="configured together"):
        settings.validate_runtime()


def test_parser_service_rejects_client_ca_without_server_identity() -> None:
    settings = ParserServiceSettings(
        _env_file=None,
        token=TOKEN,
        tls_client_ca_file="/run/secrets/parser-client/ca.crt",
    )

    with pytest.raises(RuntimeError, match="requires a TLS server certificate"):
        settings.validate_runtime()


@pytest.mark.asyncio
async def test_parser_service_rejects_excess_concurrency_without_starting_another_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def controlled_run_sync(function: Callable[..., Any], *args: Any, **kwargs: Any) -> ParsedDocument:
        nonlocal calls
        del function, args, kwargs
        calls += 1
        started.set()
        await release.wait()
        return ParsedDocument("evidence", {}, "controlled", "1")

    monkeypatch.setattr(anyio.to_thread, "run_sync", controlled_run_sync)
    app = create_app(
        ParserServiceSettings(
            _env_file=None,
            token=TOKEN,
            max_file_bytes=1_048_576,
            max_text_chars=1_000_000,
            max_concurrent_parses=1,
            capacity_wait_seconds=0.01,
        )
    )
    payload = b"evidence"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://parser.test") as client:
        first = asyncio.create_task(
            client.post(
                "/internal/v1/parse",
                params={"filename": "first.md", "max_chars": 100_000},
                headers=_headers(payload),
                content=payload,
            )
        )
        await asyncio.wait_for(started.wait(), timeout=2)
        second = await client.post(
            "/internal/v1/parse",
            params={"filename": "second.md", "max_chars": 100_000},
            headers=_headers(payload),
            content=payload,
        )
        release.set()
        first_response = await asyncio.wait_for(first, timeout=2)

    assert first_response.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "1"
    assert calls == 1
