from __future__ import annotations

from typing import Any

import pytest

from scripts.mcp_contract_fingerprint import tool_contract_sha256


def _tool(name: str, *, property_type: str = "string") -> dict[str, Any]:
    return {
        "name": name,
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": property_type}},
        },
        "outputSchema": {"type": "object"},
    }


def test_tool_contract_fingerprint_is_order_independent_and_schema_sensitive() -> None:
    first = _tool("first")
    second = _tool("second")

    assert tool_contract_sha256([first, second]) == tool_contract_sha256([second, first])
    assert tool_contract_sha256([first, second]) != tool_contract_sha256(
        [first, _tool("second", property_type="integer")]
    )


@pytest.mark.parametrize(
    ("tools", "message"),
    [
        ([], "empty"),
        ([_tool("same"), _tool("same")], "duplicated name"),
        ([{"name": "missing-schema"}], "omitted input schema"),
    ],
)
def test_tool_contract_fingerprint_rejects_ambiguous_contracts(
    tools: list[dict[str, Any]],
    message: str,
) -> None:
    with pytest.raises(RuntimeError, match=message):
        tool_contract_sha256(tools)
