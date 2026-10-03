"""Safe anticipated failures must survive the real SDK wire boundary."""

from __future__ import annotations

from typing import Any, cast

import httpx
import pytest
from mcp.client import Client
from mcp.server.mcpserver import MCPServer

from pharma_intel import mcp_server
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


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["reserved", "released", "expired", "private-invalid-state"])
async def test_replayed_reservation_retains_only_safe_recovery_state(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    async def reservation(_ctx: mcp_server.McpContext, **_kwargs: Any) -> dict[str, Any]:
        return {"replayed": True, "state": state}

    async def forbidden_domain_read(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("Replay must never read or charge the domain again")

    monkeypatch.setattr(mcp_server, "_create_commercial_reservation", reservation)
    monkeypatch.setattr(mcp_server, "api_request", forbidden_domain_read)
    server: MCPServer[None] = MCPServer("replay-error-contract")

    @server.tool()
    async def replay() -> dict[str, Any]:
        return await mcp_server._commercial_api_request(
            cast(mcp_server.McpContext, object()),
            billing_class="entity.search",
            idempotency_key="safe-replay-contract",
            max_billable_units="100",
            requested_result_limit=1,
            request_arguments={},
            method="GET",
            path="/internal/v1/domain/entities",
        )

    async with Client(server, mode="legacy", read_timeout_seconds=5) as client:
        result = await client.call_tool("replay")

    text = " ".join(block.text for block in result.content if block.type == "text")
    assert result.is_error is True
    assert "private" not in text
    if state == "private-invalid-state":
        assert text == "Error executing tool replay"
    else:
        assert f"already {state}" in text
        assert ("REQUEST_IN_PROGRESS" if state == "reserved" else "REQUEST_TERMINAL") in text
