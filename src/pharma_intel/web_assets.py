"""Cache policy for public HTML entries and content-addressed workspace assets."""

from __future__ import annotations

import re

WORKSPACE_ENTRIES = frozenset(
    {"/", "/index.html", "/research.html", "/internal.html", "/workspace/research", "/workspace/internal"}
)
HASHED_ASSET = re.compile(r"^/assets/[A-Za-z0-9_.-]+-[A-Za-z0-9_-]{8,}\.(?:js|css|wasm|woff2?|png|jpg|jpeg|svg|webp)$")


def workspace_cache_headers_for_path(path: str) -> dict[str, str]:
    if path in WORKSPACE_ENTRIES:
        return {"Cache-Control": "no-cache, must-revalidate"}
    if HASHED_ASSET.fullmatch(path):
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    return {}
