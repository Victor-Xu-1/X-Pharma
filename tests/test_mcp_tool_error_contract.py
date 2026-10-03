"""Safe anticipated failures must survive the real SDK wire boundary."""

from __future__ import annotations

import httpx
import pytest
from mcp.client import Client
from mcp.server.mcpserver import MCPServer

from pharma_intel.mcp_server import _safe_commercial_http_error


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (401, "AUTHENTICATION_REQUIRED"),
        (402, "INSUFFICIENT_CREDIT"),
        (403, "INVALID_CURSOR"),
        (409, "REQUEST_CONFLICT"),
        (429, "RATE_LIMITED"),
        (502, "UPSTREAM_UNAVAILABLE"),
    ],
)
async def test_allowlisted_commercial_error_survives_sdk_tool_call(status: int, expected_code: str) -> None:
    request = httpx.Request("POST", "http://private-api.invalid/commercial")
    response = httpx.Response(status, request=request, json={"code": "INVALID_CURSOR", "detail": "private payload"})
    error = _safe_commercial_http_error(
        httpx.HTTPStatusError("private provider failure", request=request, response=response)
    )
    server: MCPServer[None] = MCPServer("safe-error-contract")

    @server.tool()
    async def reject() -> str:
        raise error

    async with Client(server, mode="legacy", read_timeout_seconds=5) as client:
        result = await client.call_tool("reject")

    text = " ".join(block.text for block in result.content if block.type == "text")
    assert result.is_error is True
    assert expected_code in text
    assert "private" not in text


@pytest.mark.anyio
async def test_unexpected_tool_failure_stays_masked_by_sdk() -> None:
    server: MCPServer[None] = MCPServer("unexpected-error-contract")

    @server.tool()
    async def crash() -> str:
        raise RuntimeError("private backend payload must not reach the caller")

    async with Client(server, mode="legacy", read_timeout_seconds=5) as client:
        result = await client.call_tool("crash")

    text = " ".join(block.text for block in result.content if block.type == "text")
    assert result.is_error is True
    assert "Error executing tool crash" in text
    assert "private" not in text
