from __future__ import annotations

import json
import os
import uuid

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent


@pytest.mark.integration
@pytest.mark.anyio
async def test_streamable_http_lists_and_calls_domain_tools() -> None:
    mcp_url = os.getenv("TEST_MCP_URL")
    access_token = os.getenv("TEST_MCP_ACCESS_TOKEN")
    if not mcp_url or not access_token:
        pytest.skip("TEST_MCP_URL and TEST_MCP_ACCESS_TOKEN are not configured")

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=httpx.Timeout(30),
        follow_redirects=True,
        trust_env=False,
    ) as http_client:
        async with streamable_http_client(mcp_url, http_client=http_client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                assert initialization.protocolVersion == "2025-11-25"
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                result = await session.call_tool(
                    "search_entities",
                    {
                        "query": "EGFR",
                        "limit": 5,
                        "idempotency_key": f"integration-{uuid.uuid4()}",
                        "max_billable_units": "100",
                    },
                )

    assert "get_commercial_access" in names
    assert "estimate_usage" in names
    assert "get_usage_summary" in names
    assert "build_research_bundle" not in names
    assert "get_bioactivity_landscape" in names
    assert "compare_target_sar" in names
    assert "get_competitive_pipeline" in names
    assert "get_company_timeline" in names
    assert "search_chemical_structures" in names
    assert {"create_data_export", "get_data_export", "cancel_data_export", "read_data_export"} <= names
    assert result.isError is False
    payload = result.structuredContent
    if payload is None:
        assert result.content
        first = result.content[0]
        assert isinstance(first, TextContent)
        payload = json.loads(first.text)
    data = payload["data"]
    usage = payload["usage"]
    assert data["engine"] == "opensearch"
    assert data["items"][0]["name"] == "Epidermal growth factor receptor"
    assert data["items"][0]["external_ids"]["uniprot"] == "P00533"
    assert usage["billing_class"] == "entity.search"
    assert usage["result_count"] == 1
    assert usage["charged_units"] != "0.00000000"
    assert usage["settlement_id"]
