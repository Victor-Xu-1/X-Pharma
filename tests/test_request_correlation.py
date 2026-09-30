from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import cast

import pytest
from starlette.requests import Request

from pharma_intel import mcp_server
from pharma_intel.config import Settings
from pharma_intel.mcp_server import McpContext
from pharma_intel.request_correlation import (
    NETWORK_FINGERPRINT_HEADER,
    CorrelationSignalError,
    credential_confirmation_fingerprint,
    network_fingerprint,
)

CORRELATION_SECRET = hashlib.sha256(b"request-correlation-test-key").hexdigest()


def _request(peer: str, forwarded_for: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/mcp",
            "headers": headers,
            "client": (peer, 443),
            "server": ("mcp.example.test", 443),
            "scheme": "https",
        }
    )


def _settings(**updates: object) -> Settings:
    settings = Settings(
        _env_file=None,
        internal_service_jwt_secret=hashlib.sha256(b"request-correlation-internal-test-key").hexdigest(),
        mcp_correlation_hmac_secret=CORRELATION_SECRET,  # noqa: S106
    )
    return settings.model_copy(update=updates)


def test_network_fingerprint_ignores_untrusted_forwarding_and_masks_host_bits() -> None:
    settings = _settings()

    spoofed = network_fingerprint(_request("198.51.100.14", "203.0.113.90"), settings)
    same_prefix = network_fingerprint(_request("198.51.100.200"), settings)
    different_prefix = network_fingerprint(_request("198.51.101.14"), settings)

    assert spoofed == same_prefix
    assert spoofed != different_prefix
    assert "198.51.100" not in spoofed


def test_network_fingerprint_accepts_only_the_configured_proxy_chain() -> None:
    settings = _settings(
        mcp_trusted_proxy_cidrs_config="10.20.0.0/16",
        mcp_trusted_proxy_hops=2,
    )
    proxied = network_fingerprint(_request("10.20.0.5", "198.51.100.14, 10.20.0.6"), settings)
    direct = network_fingerprint(_request("198.51.100.200"), _settings())

    assert proxied == direct
    with pytest.raises(CorrelationSignalError, match="untrusted intermediary"):
        network_fingerprint(_request("10.20.0.5", "198.51.100.14, 192.0.2.5"), settings)
    with pytest.raises(CorrelationSignalError, match="incomplete"):
        network_fingerprint(_request("10.20.0.5", "198.51.100.14"), settings)
    with pytest.raises(CorrelationSignalError, match="trusted proxy"):
        network_fingerprint(
            _request("198.51.100.14"),
            settings.model_copy(update={"app_env": "production"}),
        )


def test_credential_confirmation_requires_one_supported_thumbprint() -> None:
    settings = _settings(mcp_require_token_confirmation=True)
    fingerprint = credential_confirmation_fingerprint(
        settings,
        issuer="https://identity.example.test",
        client_id="client-1",
        confirmation={"jkt": "a" * 43},
    )

    assert fingerprint is not None and len(fingerprint) == 64
    with pytest.raises(CorrelationSignalError, match="required"):
        credential_confirmation_fingerprint(
            settings,
            issuer="https://identity.example.test",
            client_id="client-1",
            confirmation=None,
        )
    with pytest.raises(CorrelationSignalError, match="ambiguous"):
        credential_confirmation_fingerprint(
            settings,
            issuer="https://identity.example.test",
            client_id="client-1",
            confirmation={"jkt": "a" * 43, "x5t#S256": "b" * 43},
        )
    with pytest.raises(CorrelationSignalError, match="invalid"):
        credential_confirmation_fingerprint(
            settings,
            issuer="https://identity.example.test",
            client_id="client-1",
            confirmation={"jkt": "a" * 42},
        )


def test_mcp_context_emits_only_the_internal_network_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    monkeypatch.setattr(mcp_server, "settings", settings)
    ctx = cast(
        McpContext,
        SimpleNamespace(request_context=SimpleNamespace(request=_request("198.51.100.14"))),
    )

    headers = mcp_server._correlation_headers(ctx)  # noqa: SLF001

    assert set(headers) == {NETWORK_FINGERPRINT_HEADER}
    assert len(headers[NETWORK_FINGERPRINT_HEADER]) == 64


@pytest.mark.anyio
async def test_mcp_api_request_rejects_caller_override_of_internal_network_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mcp_server,
        "get_access_token",
        lambda: SimpleNamespace(token="internal-token"),  # noqa: S106
    )
    ctx = cast(
        McpContext,
        SimpleNamespace(
            request_context=SimpleNamespace(
                request=_request("198.51.100.14"),
                lifespan_context=SimpleNamespace(api_client=object()),
            )
        ),
    )

    with pytest.raises(RuntimeError, match="cannot override"):
        await mcp_server.api_request(
            ctx,
            "POST",
            "/internal/v1/commercial/reservations",
            headers={NETWORK_FINGERPRINT_HEADER.lower(): "a" * 64},
        )
