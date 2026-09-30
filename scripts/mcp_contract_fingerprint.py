from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any


def tool_contract_sha256(tools: Iterable[Mapping[str, Any]]) -> str:
    """Return an order-independent fingerprint of callable MCP tool contracts."""
    normalized: list[dict[str, Any]] = []
    names: set[str] = set()
    for tool in tools:
        name = tool.get("name")
        input_schema = tool.get("inputSchema")
        output_schema = tool.get("outputSchema")
        if not isinstance(name, str) or not name:
            raise RuntimeError("MCP tool contract omitted a valid name")
        if name in names:
            raise RuntimeError(f"MCP tool contract duplicated name: {name}")
        if not isinstance(input_schema, dict):
            raise RuntimeError(f"MCP tool contract omitted input schema: {name}")
        if output_schema is not None and not isinstance(output_schema, dict):
            raise RuntimeError(f"MCP tool contract returned an invalid output schema: {name}")
        names.add(name)
        normalized.append(
            {
                "name": name,
                "inputSchema": input_schema,
                "outputSchema": output_schema,
            }
        )
    if not normalized:
        raise RuntimeError("MCP tool contract is empty")
    encoded = json.dumps(
        sorted(normalized, key=lambda tool: tool["name"]),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()
