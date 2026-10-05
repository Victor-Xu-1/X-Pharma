from __future__ import annotations

import json
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

_ALLOWED_HOSTS = frozenset(
    {
        "www.ebi.ac.uk",
        "clinicaltrials.gov",
        "pubchem.ncbi.nlm.nih.gov",
        "ir.revmed.com",
        "ir.kuraoncology.com",
    }
)
_MAX_BYTES = 1_048_576
_RATE_LOCK = threading.Lock()
_NEXT_REQUEST_AT = 0.0


class PublicResearchUnavailable(RuntimeError):
    pass


class PublicRecordNotFound(PublicResearchUnavailable):
    pass


class PublicTransport:
    def __init__(self, client: httpx.Client, *, throttle: bool = True) -> None:
        self.client = client
        self.throttle = throttle

    def read(self, url: str, params: dict[str, str], *, xml: bool = False) -> bytes:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in _ALLOWED_HOSTS
            or parsed.port
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise ValueError("Public research endpoint is outside the fixed provider allowlist")
        if self.throttle:
            _pace_requests()
        deadline = time.monotonic() + 10
        with self.client.stream("GET", url, params=params) as response:
            if response.status_code == 404:
                raise PublicRecordNotFound("Public record not found")
            if response.status_code != 200:
                raise PublicResearchUnavailable("Public provider unavailable")
            allowed = {"application/rss+xml", "application/xml", "text/xml"} if xml else {"application/json"}
            if response.headers.get("content-type", "").partition(";")[0].strip().casefold() not in allowed:
                raise ValueError("Public provider returned an unexpected media type")
            content = bytearray()
            for chunk in response.iter_bytes():
                if time.monotonic() > deadline or len(content) + len(chunk) > _MAX_BYTES:
                    raise PublicResearchUnavailable("Public response exceeded the bounded read budget")
                content.extend(chunk)
            return bytes(content)

    def json(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            payload = json.loads(self.read(url, params))
        except RecursionError as exc:
            raise ValueError("Public response exceeds the JSON nesting limit") from exc
        if not isinstance(payload, dict):
            raise ValueError("Public response must be a JSON object")
        return payload


def _pace_requests() -> None:
    global _NEXT_REQUEST_AT
    with _RATE_LOCK:
        now = time.monotonic()
        start = max(now, _NEXT_REQUEST_AT)
        _NEXT_REQUEST_AT = start + 0.25
    if start > now:
        time.sleep(start - now)
