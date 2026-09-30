from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from pharma_intel.config import get_settings
from pharma_intel.mcp_health import (
    select_authorization_server,
    verify_authorization_server_metadata,
    verify_protected_resource_metadata,
    verify_unauthenticated_rejection,
)


def _validate_loopback_ready_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/health/ready"
    ):
        raise ValueError("gateway readiness URL must be an uncredentialed loopback HTTP /health/ready endpoint")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("gateway readiness URL contains an invalid port") from exc
    if port is None or not 1 <= port <= 65535:
        raise ValueError("gateway readiness URL must contain an explicit valid port")


def verify_api_readiness(url: str, *, timeout_seconds: float = 3) -> None:
    _validate_loopback_ready_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, method="GET")  # noqa: S310 - URL is restricted to loopback HTTP above.
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise RuntimeError(f"gateway readiness returned HTTP {response.status}, expected 200")
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise RuntimeError(f"gateway readiness returned HTTP {status}, expected 200") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("gateway readiness endpoint is unavailable") from exc


def verify_gateway_health(
    *,
    api_url: str = "http://127.0.0.1:8080/health/ready",
    mcp_url: str = "http://127.0.0.1:8080/mcp",
    expected_mcp_resource_url: str = "http://127.0.0.1:8090/mcp",
    expected_mcp_authorization_server_url: str = "http://127.0.0.1:8080",
    verify_mcp_authorization_server: bool = False,
    timeout_seconds: float = 3,
) -> None:
    verify_api_readiness(api_url, timeout_seconds=timeout_seconds)
    verify_unauthenticated_rejection(
        mcp_url,
        expected_resource_url=expected_mcp_resource_url,
        timeout_seconds=timeout_seconds,
    )
    authorization_servers = verify_protected_resource_metadata(
        mcp_url,
        expected_resource_url=expected_mcp_resource_url,
        expected_authorization_server_url=expected_mcp_authorization_server_url,
        timeout_seconds=timeout_seconds,
    )
    if verify_mcp_authorization_server:
        advertised_issuer = select_authorization_server(
            authorization_servers,
            expected_mcp_authorization_server_url,
        )
        verify_authorization_server_metadata(advertised_issuer, timeout_seconds=timeout_seconds)


def run() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Verify the unified Web/API and MCP gateway")
    parser.add_argument("--api-url", default="http://127.0.0.1:8080/health/ready")
    parser.add_argument("--mcp-url", default="http://127.0.0.1:8080/mcp")
    parser.add_argument("--expected-mcp-resource-url", default=settings.mcp_resource_server_url)
    parser.add_argument(
        "--expected-mcp-authorization-server-url",
        default=settings.mcp_auth_issuer_url,
    )
    parser.add_argument("--timeout-seconds", type=float, default=3)
    arguments = parser.parse_args()
    if not 0 < arguments.timeout_seconds <= 30:
        parser.error("--timeout-seconds must be greater than zero and at most 30")
    verify_mcp_authorization_server = settings.mcp_token_verifier_mode == "oidc"  # noqa: S105
    try:
        verify_gateway_health(
            api_url=arguments.api_url,
            mcp_url=arguments.mcp_url,
            expected_mcp_resource_url=arguments.expected_mcp_resource_url,
            expected_mcp_authorization_server_url=arguments.expected_mcp_authorization_server_url,
            verify_mcp_authorization_server=verify_mcp_authorization_server,
            timeout_seconds=arguments.timeout_seconds,
        )
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
