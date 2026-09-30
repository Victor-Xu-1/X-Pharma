from __future__ import annotations

import json
import urllib.error
import urllib.request
from contextlib import nullcontext
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from pharma_intel.mcp_health import (
    verify_authorization_server_metadata,
    verify_protected_resource_metadata,
    verify_unauthenticated_rejection,
)


class StubOpener:
    def __init__(self, result: object) -> None:
        self.result = result

    def open(self, _request: object, *, timeout: float) -> object:
        assert timeout == 2
        if isinstance(self.result, BaseException):
            raise self.result
        return nullcontext(self.result)


class SequencedOpener:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.urls: list[str] = []

    def open(self, request: urllib.request.Request, *, timeout: float) -> object:
        assert timeout == 2
        self.urls.append(request.full_url)
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return nullcontext(result)


class StubResponse:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self.body = body

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


def test_mcp_health_accepts_only_an_explicit_unauthenticated_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = Message()
    headers.add_header(
        "WWW-Authenticate",
        'Bearer error="invalid_token", resource_metadata="http://127.0.0.1:8090/.well-known/oauth-protected-resource/mcp"',
    )
    rejection = urllib.error.HTTPError("http://127.0.0.1:8090/mcp", 401, "unauthorized", headers, None)
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(rejection),
    )

    verify_unauthenticated_rejection("http://127.0.0.1:8090/mcp", timeout_seconds=2)


def test_mcp_health_rejects_a_challenge_for_a_different_public_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = Message()
    headers.add_header(
        "WWW-Authenticate",
        'Bearer error="invalid_token", resource_metadata="http://127.0.0.1:8090/.well-known/oauth-protected-resource/mcp"',
    )
    rejection = urllib.error.HTTPError("http://127.0.0.1:18191/mcp", 401, "unauthorized", headers, None)
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(rejection),
    )

    with pytest.raises(RuntimeError, match="does not match the configured public resource URL"):
        verify_unauthenticated_rejection(
            "http://127.0.0.1:18191/mcp",
            expected_resource_url="http://127.0.0.1:18191/mcp",
            timeout_seconds=2,
        )


@pytest.mark.parametrize(
    "challenge, message",
    [
        (None, "WWW-Authenticate Bearer challenge"),
        ('Basic realm="mcp"', "WWW-Authenticate Bearer challenge"),
        ('Bearer error="invalid_token"', "resource_metadata"),
    ],
)
def test_mcp_health_rejects_an_undiscoverable_401_challenge(
    challenge: str | None,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = Message()
    if challenge is not None:
        headers.add_header("WWW-Authenticate", challenge)
    rejection = urllib.error.HTTPError("http://127.0.0.1:8090/mcp", 401, "unauthorized", headers, None)
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(rejection),
    )

    with pytest.raises(RuntimeError, match=message):
        verify_unauthenticated_rejection("http://127.0.0.1:8090/mcp", timeout_seconds=2)


@pytest.mark.parametrize("status", [200, 204, 302, 403, 500])
def test_mcp_health_rejects_open_or_misconfigured_boundaries(
    status: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result: object
    if status >= 400:
        result = urllib.error.HTTPError("http://127.0.0.1:8090/mcp", status, "error", Message(), None)
    else:
        result = StubResponse(status)
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(result),
    )

    with pytest.raises(RuntimeError, match=rf"HTTP {status}, expected 401"):
        verify_unauthenticated_rejection("http://127.0.0.1:8090/mcp", timeout_seconds=2)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8090/mcp",
        "http://example.com:8090/mcp",
        "http://token@127.0.0.1:8090/mcp",
        "http://127.0.0.1:8090/health",
        "file:///mcp",
    ],
)
def test_mcp_health_rejects_non_loopback_or_credentialed_urls(url: str) -> None:
    with pytest.raises(ValueError, match="loopback HTTP"):
        verify_unauthenticated_rejection(url)


def test_mcp_health_requires_a_valid_protected_resource_metadata_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = {
        "resource": "http://127.0.0.1:8090/mcp",
        "authorization_servers": ["http://127.0.0.1:8080/"],
        "scopes_supported": ["mcp:connect"],
        "bearer_methods_supported": ["header"],
    }
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(StubResponse(200, json.dumps(metadata).encode("utf-8"))),
    )

    authorization_servers = verify_protected_resource_metadata(
        "http://127.0.0.1:8090/mcp",
        expected_authorization_server_url="http://127.0.0.1:8080",
        timeout_seconds=2,
    )

    assert authorization_servers == ("http://127.0.0.1:8080/",)


def test_mcp_health_rejects_metadata_for_a_different_public_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = {
        "resource": "http://127.0.0.1:8090/mcp",
        "authorization_servers": ["http://127.0.0.1:8080/"],
        "scopes_supported": ["mcp:connect"],
        "bearer_methods_supported": ["header"],
    }
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(StubResponse(200, json.dumps(metadata).encode("utf-8"))),
    )

    with pytest.raises(RuntimeError, match="does not match the configured public resource URL"):
        verify_protected_resource_metadata(
            "http://127.0.0.1:18191/mcp",
            expected_resource_url="http://127.0.0.1:18191/mcp",
            timeout_seconds=2,
        )


def test_mcp_health_rejects_metadata_for_a_different_authorization_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = {
        "resource": "http://127.0.0.1:8090/mcp",
        "authorization_servers": ["https://identity.other.test"],
        "scopes_supported": ["mcp:connect"],
        "bearer_methods_supported": ["header"],
    }
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(StubResponse(200, json.dumps(metadata).encode("utf-8"))),
    )

    with pytest.raises(RuntimeError, match="does not advertise the configured authorization server"):
        verify_protected_resource_metadata(
            "http://127.0.0.1:8090/mcp",
            expected_authorization_server_url="https://identity.example.test",
            timeout_seconds=2,
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"resource": "http://127.0.0.1:8090/mcp"},
        {
            "resource": "http://127.0.0.1:8090/mcp",
            "authorization_servers": ["http://127.0.0.1:8080/"],
            "scopes_supported": ["other"],
            "bearer_methods_supported": ["header"],
        },
        {
            "resource": "https:///mcp",
            "authorization_servers": ["https://identity.example.test"],
            "scopes_supported": ["mcp:connect"],
            "bearer_methods_supported": ["header"],
        },
    ],
)
def test_mcp_health_rejects_incomplete_protected_resource_metadata(
    metadata: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(StubResponse(200, json.dumps(metadata).encode("utf-8"))),
    )

    with pytest.raises(RuntimeError, match="metadata"):
        verify_protected_resource_metadata("http://127.0.0.1:8090/mcp", timeout_seconds=2)


def test_mcp_health_treats_non_root_issuer_trailing_slashes_as_significant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = {
        "resource": "http://127.0.0.1:8090/mcp",
        "authorization_servers": ["https://identity.example.test/tenant/"],
        "scopes_supported": ["mcp:connect"],
        "bearer_methods_supported": ["header"],
    }
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(StubResponse(200, json.dumps(metadata).encode("utf-8"))),
    )

    with pytest.raises(RuntimeError, match="configured authorization server"):
        verify_protected_resource_metadata(
            "http://127.0.0.1:8090/mcp",
            expected_authorization_server_url="https://identity.example.test/tenant",
            timeout_seconds=2,
        )


def test_mcp_health_rejects_oversized_discovery_documents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: StubOpener(StubResponse(200, b"x" * 300_000)),
    )

    with pytest.raises(RuntimeError, match="maximum allowed size"):
        verify_protected_resource_metadata("http://127.0.0.1:8090/mcp", timeout_seconds=2)


def test_mcp_health_discovers_path_based_oidc_metadata_in_required_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issuer = "https://identity.example.test/tenant-1"
    metadata = {
        "issuer": issuer,
        "authorization_endpoint": "https://identity.example.test/oauth/authorize",
        "token_endpoint": "https://identity.example.test/oauth/token",
        "response_types_supported": ["code"],
        "code_challenge_methods_supported": ["S256"],
    }
    first_url = "https://identity.example.test/.well-known/oauth-authorization-server/tenant-1"
    opener = SequencedOpener(
        [
            urllib.error.HTTPError(first_url, 404, "missing", Message(), None),
            StubResponse(200, json.dumps(metadata).encode("utf-8")),
        ]
    )
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: opener,
    )

    verify_authorization_server_metadata(issuer, timeout_seconds=2)

    assert opener.urls == [
        first_url,
        "https://identity.example.test/.well-known/openid-configuration/tenant-1",
    ]


@pytest.mark.parametrize(
    "metadata, message",
    [
        (
            {
                "issuer": "https://identity.example.test",
                "authorization_endpoint": "https://identity.example.test/oauth/authorize",
                "token_endpoint": "https://identity.example.test/oauth/token",
                "response_types_supported": ["code"],
            },
            "S256 PKCE",
        ),
        (
            {
                "issuer": "https://identity.other.test",
                "authorization_endpoint": "https://identity.example.test/oauth/authorize",
                "token_endpoint": "https://identity.example.test/oauth/token",
                "response_types_supported": ["code"],
                "code_challenge_methods_supported": ["S256"],
            },
            "issuer",
        ),
        (
            {
                "issuer": "https://identity.example.test",
                "authorization_endpoint": "https://identity.example.test:bad/oauth/authorize",
                "token_endpoint": "https://identity.example.test/oauth/token",
                "response_types_supported": ["code"],
                "code_challenge_methods_supported": ["S256"],
            },
            "authorization endpoint",
        ),
    ],
)
def test_mcp_health_rejects_incompatible_authorization_server_metadata(
    metadata: dict[str, object],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = StubResponse(200, json.dumps(metadata).encode("utf-8"))
    opener = SequencedOpener([response, response])
    monkeypatch.setattr(
        "pharma_intel.mcp_health.urllib.request.build_opener",
        lambda *_args: opener,
    )

    with pytest.raises(RuntimeError, match=message):
        verify_authorization_server_metadata("https://identity.example.test", timeout_seconds=2)


def test_mcp_health_verifies_the_real_http_discovery_chain() -> None:
    class DiscoveryHandler(BaseHTTPRequestHandler):
        resource_url = ""
        issuer_url = ""

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API.
            if self.path == "/mcp":
                metadata_url = self.resource_url.replace(
                    "/mcp",
                    "/.well-known/oauth-protected-resource/mcp",
                )
                self.send_response(401)
                self.send_header(
                    "WWW-Authenticate",
                    f'Bearer resource_metadata="{metadata_url}", scope="mcp:connect"',
                )
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path == "/.well-known/oauth-protected-resource/mcp":
                self._send_json(
                    {
                        "resource": self.resource_url,
                        "authorization_servers": [self.issuer_url],
                        "scopes_supported": ["mcp:connect"],
                        "bearer_methods_supported": ["header"],
                    }
                )
                return
            if self.path == "/.well-known/oauth-authorization-server/issuer":
                origin = self.issuer_url.removesuffix("/issuer")
                self._send_json(
                    {
                        "issuer": self.issuer_url,
                        "authorization_endpoint": f"{origin}/oauth/authorize",
                        "token_endpoint": f"{origin}/oauth/token",
                        "response_types_supported": ["code"],
                        "code_challenge_methods_supported": ["S256"],
                    }
                )
                return
            self.send_error(404)

        def _send_json(self, payload: dict[str, object]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), DiscoveryHandler)
    port = server.server_address[1]
    DiscoveryHandler.resource_url = f"http://127.0.0.1:{port}/mcp"
    DiscoveryHandler.issuer_url = f"http://127.0.0.1:{port}/issuer"
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        verify_unauthenticated_rejection(
            DiscoveryHandler.resource_url,
            expected_resource_url=DiscoveryHandler.resource_url,
            timeout_seconds=2,
        )
        authorization_servers = verify_protected_resource_metadata(
            DiscoveryHandler.resource_url,
            expected_resource_url=DiscoveryHandler.resource_url,
            expected_authorization_server_url=DiscoveryHandler.issuer_url,
            timeout_seconds=2,
        )
        verify_authorization_server_metadata(authorization_servers[0], timeout_seconds=2)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert authorization_servers == (DiscoveryHandler.issuer_url,)
    assert not thread.is_alive()
