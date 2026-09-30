from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

from pharma_intel.config import get_settings

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
MAX_DISCOVERY_DOCUMENT_BYTES = 262_144


def _validate_loopback_mcp_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/mcp"
    ):
        raise ValueError("MCP health URL must be an uncredentialed loopback HTTP /mcp endpoint")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("MCP health URL contains an invalid port") from exc
    if port is None or not 1 <= port <= 65535:
        raise ValueError("MCP health URL must contain an explicit valid port")


def _protected_resource_metadata_url(resource_url: str) -> str:
    parsed = urlsplit(resource_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path != "/mcp"
    ):
        raise ValueError("MCP public resource URL must be an uncredentialed HTTP(S) /mcp endpoint")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("MCP public resource URL contains an invalid port") from exc
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            "/.well-known/oauth-protected-resource/mcp",
            "",
            "",
        )
    )


def _validate_authorization_server_issuer(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("MCP authorization server issuer must be an uncredentialed HTTP(S) URL")
    if parsed.scheme == "http" and parsed.hostname not in LOOPBACK_HOSTS:
        raise ValueError("MCP authorization server issuer must use HTTPS unless it is loopback")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("MCP authorization server issuer contains an invalid port") from exc


def _normalized_issuer(url: str) -> str:
    parsed = urlsplit(url)
    path = "" if parsed.path == "/" else parsed.path
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, "", ""))


def _authorization_server_metadata_urls(issuer_url: str) -> tuple[str, ...]:
    _validate_authorization_server_issuer(issuer_url)
    parsed = urlsplit(issuer_url)
    issuer_path = parsed.path.strip("/")
    inserted_suffix = f"/{issuer_path}" if issuer_path else ""
    candidates = [
        urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                f"/.well-known/oauth-authorization-server{inserted_suffix}",
                "",
                "",
            )
        ),
        urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                f"/.well-known/openid-configuration{inserted_suffix}",
                "",
                "",
            )
        ),
    ]
    if issuer_path:
        candidates.append(
            urlunsplit(
                (
                    parsed.scheme,
                    parsed.netloc,
                    f"/{issuer_path}/.well-known/openid-configuration",
                    "",
                    "",
                )
            )
        )
    return tuple(candidates)


def _read_json_document(url: str, *, label: str, timeout_seconds: float) -> dict[str, object]:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(  # noqa: S310 - callers validate configured discovery URLs before use.
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise RuntimeError(f"{label} returned HTTP {response.status}, expected 200")
            headers = getattr(response, "headers", None)
            content_length = None
            if headers is not None:
                content_length = headers.get("Content-Length")
            if isinstance(content_length, str):
                try:
                    if int(content_length) > MAX_DISCOVERY_DOCUMENT_BYTES:
                        raise RuntimeError(f"{label} exceeds the maximum allowed size")
                except ValueError as exc:
                    raise RuntimeError(f"{label} returned an invalid Content-Length") from exc
            try:
                body = response.read(MAX_DISCOVERY_DOCUMENT_BYTES + 1)
                if len(body) > MAX_DISCOVERY_DOCUMENT_BYTES:
                    raise RuntimeError(f"{label} exceeds the maximum allowed size")
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
                raise RuntimeError(f"{label} was not valid JSON") from exc
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise RuntimeError(f"{label} returned HTTP {status}, expected 200") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{label} endpoint is unavailable") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return payload


def verify_unauthenticated_rejection(
    url: str,
    *,
    expected_resource_url: str | None = None,
    timeout_seconds: float = 3,
) -> None:
    _validate_loopback_mcp_url(url)
    expected_metadata_url = _protected_resource_metadata_url(expected_resource_url or url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, method="GET")  # noqa: S310 - URL is restricted to loopback HTTP above.
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        headers = exc.headers
        exc.close()
        if status == 401:
            _validate_bearer_challenge(headers, expected_metadata_url=expected_metadata_url)
            return
        raise RuntimeError(f"MCP authentication boundary returned HTTP {status}, expected 401") from exc
    raise RuntimeError(f"MCP authentication boundary returned HTTP {status}, expected 401")


def _validate_bearer_challenge(headers: object, *, expected_metadata_url: str) -> None:
    challenge = headers.get("WWW-Authenticate") if hasattr(headers, "get") else None
    if not isinstance(challenge, str) or not re.match(r"^\s*Bearer(?:\s|$)", challenge, re.IGNORECASE):
        raise RuntimeError("MCP authentication boundary returned HTTP 401 without a WWW-Authenticate Bearer challenge")
    metadata_match = re.search(
        r'\bresource_metadata\s*=\s*(?:"([^"]+)"|([^,\s]+))',
        challenge,
        re.IGNORECASE,
    )
    if metadata_match is None:
        raise RuntimeError("MCP Bearer challenge does not advertise resource_metadata")
    advertised_metadata_url = metadata_match.group(1) or metadata_match.group(2)
    if advertised_metadata_url != expected_metadata_url:
        raise RuntimeError("MCP Bearer challenge resource_metadata does not match the configured public resource URL")


def verify_protected_resource_metadata(
    url: str,
    *,
    expected_resource_url: str | None = None,
    expected_authorization_server_url: str | None = None,
    timeout_seconds: float = 3,
) -> tuple[str, ...]:
    """Verify that an MCP endpoint publishes the discovery contract agents need."""
    _validate_loopback_mcp_url(url)
    public_resource_url = expected_resource_url or url
    _protected_resource_metadata_url(public_resource_url)
    parsed = urlsplit(url)
    metadata_url = urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            "/.well-known/oauth-protected-resource/mcp",
            "",
            "",
        )
    )
    payload = _read_json_document(
        metadata_url,
        label="MCP resource metadata",
        timeout_seconds=timeout_seconds,
    )
    resource = payload.get("resource")
    resource_url = urlsplit(resource) if isinstance(resource, str) else None
    if (
        resource_url is None
        or resource_url.scheme not in {"http", "https"}
        or not resource_url.hostname
        or resource_url.username is not None
        or resource_url.password is not None
        or resource_url.query
        or resource_url.fragment
        or resource_url.path != "/mcp"
    ):
        raise RuntimeError("MCP resource metadata contains an invalid resource URL")
    if resource != public_resource_url:
        raise RuntimeError("MCP resource metadata does not match the configured public resource URL")
    authorization_servers = payload.get("authorization_servers")
    if (
        not isinstance(authorization_servers, list)
        or not authorization_servers
        or not all(isinstance(value, str) and value for value in authorization_servers)
    ):
        raise RuntimeError("MCP resource metadata must list an authorization server")
    try:
        for authorization_server in authorization_servers:
            _validate_authorization_server_issuer(authorization_server)
    except ValueError as exc:
        raise RuntimeError("MCP resource metadata contains an invalid authorization server") from exc
    if expected_authorization_server_url is not None:
        try:
            _validate_authorization_server_issuer(expected_authorization_server_url)
        except ValueError as exc:
            raise RuntimeError("Configured MCP authorization server is invalid") from exc
        expected_issuer = _normalized_issuer(expected_authorization_server_url)
        if not any(_normalized_issuer(value) == expected_issuer for value in authorization_servers):
            raise RuntimeError("MCP resource metadata does not advertise the configured authorization server")
    scopes = payload.get("scopes_supported")
    if not isinstance(scopes, list) or "mcp:connect" not in scopes:
        raise RuntimeError("MCP resource metadata must advertise the mcp:connect scope")
    bearer_methods = payload.get("bearer_methods_supported")
    if not isinstance(bearer_methods, list) or "header" not in bearer_methods:
        raise RuntimeError("MCP resource metadata must advertise header bearer authentication")
    return tuple(authorization_servers)


def select_authorization_server(
    authorization_servers: tuple[str, ...],
    expected_authorization_server_url: str,
) -> str:
    try:
        _validate_authorization_server_issuer(expected_authorization_server_url)
        for authorization_server in authorization_servers:
            _validate_authorization_server_issuer(authorization_server)
    except ValueError as exc:
        raise RuntimeError("MCP authorization server selection contains an invalid issuer") from exc
    expected_issuer = _normalized_issuer(expected_authorization_server_url)
    for authorization_server in authorization_servers:
        if _normalized_issuer(authorization_server) == expected_issuer:
            return authorization_server
    raise RuntimeError("MCP resource metadata does not advertise the configured authorization server")


def _validate_authorization_endpoint(url: object, *, label: str) -> None:
    parsed = urlsplit(url) if isinstance(url, str) else None
    if (
        parsed is None
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (parsed.scheme == "http" and parsed.hostname not in LOOPBACK_HOSTS)
    ):
        raise RuntimeError(f"MCP authorization server metadata contains an invalid {label}")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise RuntimeError(f"MCP authorization server metadata contains an invalid {label}") from exc


def _validate_authorization_server_metadata(payload: dict[str, object], *, issuer_url: str) -> None:
    if payload.get("issuer") != issuer_url:
        raise RuntimeError("MCP authorization server metadata issuer does not match the advertised issuer")
    _validate_authorization_endpoint(payload.get("authorization_endpoint"), label="authorization endpoint")
    _validate_authorization_endpoint(payload.get("token_endpoint"), label="token endpoint")
    response_types = payload.get("response_types_supported")
    if not isinstance(response_types, list) or "code" not in response_types:
        raise RuntimeError("MCP authorization server metadata must support the authorization code response type")
    pkce_methods = payload.get("code_challenge_methods_supported")
    if not isinstance(pkce_methods, list) or "S256" not in pkce_methods:
        raise RuntimeError("MCP authorization server metadata must advertise S256 PKCE")


def verify_authorization_server_metadata(issuer_url: str, *, timeout_seconds: float = 3) -> None:
    """Verify the RFC 8414 or OIDC discovery contract required by remote MCP clients."""
    failures: list[str] = []
    for metadata_url in _authorization_server_metadata_urls(issuer_url):
        try:
            payload = _read_json_document(
                metadata_url,
                label="MCP authorization server metadata",
                timeout_seconds=timeout_seconds,
            )
            _validate_authorization_server_metadata(payload, issuer_url=issuer_url)
        except RuntimeError as exc:
            failures.append(str(exc))
            continue
        return
    raise RuntimeError(
        "MCP authorization server metadata is unavailable or incompatible with OAuth 2.1 and S256 PKCE: "
        + "; ".join(failures)
    )


def run() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Verify the MCP authentication and discovery boundary")
    parser.add_argument("--url", default="http://127.0.0.1:8090/mcp")
    parser.add_argument("--expected-resource-url", default=settings.mcp_resource_server_url)
    parser.add_argument("--timeout-seconds", type=float, default=3)
    arguments = parser.parse_args()
    if not 0 < arguments.timeout_seconds <= 30:
        parser.error("--timeout-seconds must be greater than zero and at most 30")
    verify_unauthenticated_rejection(
        arguments.url,
        expected_resource_url=arguments.expected_resource_url,
        timeout_seconds=arguments.timeout_seconds,
    )
    authorization_servers = verify_protected_resource_metadata(
        arguments.url,
        expected_resource_url=arguments.expected_resource_url,
        expected_authorization_server_url=settings.mcp_auth_issuer_url,
        timeout_seconds=arguments.timeout_seconds,
    )
    if settings.mcp_token_verifier_mode == "oidc":  # noqa: S105 - verifier mode, not a credential.
        advertised_issuer = select_authorization_server(
            authorization_servers,
            settings.mcp_auth_issuer_url,
        )
        verify_authorization_server_metadata(advertised_issuer, timeout_seconds=arguments.timeout_seconds)


if __name__ == "__main__":
    run()
