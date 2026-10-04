from __future__ import annotations

import httpx

from pharma_intel.config import Settings
from pharma_intel.ingest.connectors import ConnectorTransportError, _read_bounded, _require_success


def request_public_api_bytes(
    settings: Settings,
    client: httpx.Client,
    url: str,
    params: dict[str, str],
    resource_name: str,
    *,
    maximum_bytes: int,
    media_types: frozenset[str] = frozenset({"application/json"}),
) -> bytes:
    """Bound official API responses during consumption, not after an eager allocation."""
    limit = min(maximum_bytes, settings.source_http_max_api_response_bytes)
    with client.stream("GET", url, params=params) as response:
        _require_success(response, resource_name)
        content_type = response.headers.get("content-type", "").partition(";")[0].strip().casefold()
        if content_type not in media_types:
            raise ConnectorTransportError(f"{resource_name} response must use application/json")
        return _read_bounded(
            response,
            limit,
            error_message=f"{resource_name} response exceeded the configured safety limit",
        )
