from __future__ import annotations

import hashlib
import hmac
import re
from ipaddress import IPv4Address, IPv6Address, ip_address, ip_network

from starlette.requests import Request

from pharma_intel.config import Settings

NETWORK_FINGERPRINT_HEADER = "X-Pharma-Network-Fingerprint"
FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CONFIRMATION_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
MAX_FORWARDED_FOR_BYTES = 2048
MAX_FORWARDED_FOR_ADDRESSES = 16


class CorrelationSignalError(ValueError):
    pass


def network_fingerprint(request: Request, settings: Settings) -> str:
    if request.client is None:
        raise CorrelationSignalError("MCP request network context is unavailable")
    peer = _parse_address(request.client.host)
    trusted_networks = settings.mcp_trusted_proxy_cidrs
    source = peer
    peer_is_trusted = any(peer in network for network in trusted_networks)
    if settings.app_env.lower() == "production" and not peer_is_trusted:
        raise CorrelationSignalError("MCP request did not arrive through a trusted proxy")
    if peer_is_trusted:
        forwarded = _forwarded_for_addresses(request)
        hops = settings.mcp_trusted_proxy_hops
        if len(forwarded) < hops:
            raise CorrelationSignalError("MCP trusted proxy chain is incomplete")
        if hops > 1 and any(
            not any(intermediary in network for network in trusted_networks)
            for intermediary in forwarded[-(hops - 1) :]
        ):
            raise CorrelationSignalError("MCP trusted proxy chain contains an untrusted intermediary")
        source = forwarded[-hops]
    prefix_length = (
        settings.mcp_network_ipv4_prefix_length
        if isinstance(source, IPv4Address)
        else settings.mcp_network_ipv6_prefix_length
    )
    network = ip_network(f"{source}/{prefix_length}", strict=False)
    return correlation_fingerprint(
        settings,
        "network",
        f"{network.version}:{network.network_address}/{network.prefixlen}",
    )


def credential_confirmation_fingerprint(
    settings: Settings,
    *,
    issuer: str,
    client_id: str,
    confirmation: object,
) -> str | None:
    if not isinstance(confirmation, dict):
        if settings.mcp_require_token_confirmation:
            raise CorrelationSignalError("OIDC access token confirmation claim is required")
        return None
    supported = [(name, confirmation.get(name)) for name in ("jkt", "x5t#S256") if confirmation.get(name) is not None]
    if len(supported) != 1:
        raise CorrelationSignalError("OIDC access token confirmation claim is ambiguous or unsupported")
    kind, value = supported[0]
    if not isinstance(value, str) or CONFIRMATION_PATTERN.fullmatch(value) is None:
        raise CorrelationSignalError("OIDC access token confirmation value is invalid")
    return correlation_fingerprint(settings, "credential", f"{issuer}\n{client_id}\n{kind}\n{value}")


def api_key_credential_fingerprint(settings: Settings, api_key_id: str) -> str:
    return correlation_fingerprint(settings, "api-key", api_key_id)


def validate_internal_network_fingerprint(value: str | None, settings: Settings) -> str | None:
    if value is None:
        if settings.app_env.lower() == "production":
            raise CorrelationSignalError("MCP network fingerprint is required")
        return None
    if FINGERPRINT_PATTERN.fullmatch(value) is None:
        raise CorrelationSignalError("MCP network fingerprint is invalid")
    return value


def correlation_fingerprint(settings: Settings, namespace: str, value: str) -> str:
    payload = f"pharma-correlation-v1\n{namespace}\n{value}".encode()
    return hmac.new(
        settings.effective_mcp_correlation_hmac_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


def _forwarded_for_addresses(request: Request) -> list[IPv4Address | IPv6Address]:
    raw_values = request.headers.getlist("x-forwarded-for")
    raw = ",".join(raw_values)
    if not raw or len(raw.encode("utf-8")) > MAX_FORWARDED_FOR_BYTES:
        raise CorrelationSignalError("MCP trusted proxy did not provide a valid forwarding chain")
    values = [value.strip() for value in raw.split(",")]
    if not values or len(values) > MAX_FORWARDED_FOR_ADDRESSES or any(not value for value in values):
        raise CorrelationSignalError("MCP forwarding chain exceeds the supported size")
    return [_parse_address(value) for value in values]


def _parse_address(value: str) -> IPv4Address | IPv6Address:
    try:
        return ip_address(value)
    except ValueError as exc:
        raise CorrelationSignalError("MCP request network address is invalid") from exc
