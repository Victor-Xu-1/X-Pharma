from __future__ import annotations

from typing import Any

import httpx
import pytest
from mcp.types import (
    CallToolResult,
    Implementation,
    InitializeResult,
    ListToolsResult,
    ServerCapabilities,
    Tool,
)

from scripts import entry_consistency_probe
from scripts.mcp_streamable_contract import REQUIRED_DOMAIN_TOOLS

TEST_PASSWORD = "entry-consistency-test-password"  # noqa: S105


def _entity(name: str = "Entry consistency marker-1") -> dict[str, Any]:
    return {
        "id": "entity-1",
        "entity_type": "target",
        "name": name,
        "description": "Isolated Web and MCP consistency fixture",
        "external_ids": {"acceptance": "marker-1"},
        "attributes": {
            "acceptance_fixture": True,
            "acceptance_fixture_kind": "entry_consistency",
            "acceptance_fixture_marker": "marker-1",
        },
        "review_status": "verified",
        "canonical_entity_id": "entity-1",
        "identity_identifiers": [
            {
                "namespace": "acceptance",
                "value": "marker-1",
                "normalized_value": "marker-1",
                "trusted_namespace": False,
                "review_status": "verified",
                "source_document_id": None,
            }
        ],
        "created_at": "2026-07-18T00:00:00Z",
        "updated_at": "2026-07-18T00:00:00Z",
    }


class FakeMcpSession:
    def __init__(
        self,
        *,
        entity_name: str = "Entry consistency marker-1",
        tools: set[str] | None = None,
        engine: str = "opensearch",
        usage_override: dict[str, Any] | None = None,
    ) -> None:
        self.entity_name = entity_name
        self.calls: list[str] = []
        self.tools = set(REQUIRED_DOMAIN_TOOLS) if tools is None else tools
        self.engine = engine
        self.usage_override = usage_override or {}
        self.list_calls = 0

    async def initialize(self) -> InitializeResult:
        return InitializeResult(
            protocol_version="2025-11-25",
            capabilities=ServerCapabilities(),
            server_info=Implementation(name="test", version="1"),
        )

    async def list_tools(self, cursor: str | None = None) -> ListToolsResult:
        assert cursor is None
        self.list_calls += 1
        return ListToolsResult(tools=[Tool(name=name, input_schema={"type": "object"}) for name in sorted(self.tools)])

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        self.calls.append(name)
        entity = _entity(self.entity_name)
        if name == "get_entity":
            payload = {
                "data": entity,
                "usage": {
                    "settlement_id": "settlement-get",
                    "billing_class": "entity.read",
                    "result_count": 1,
                    "charged_units": "1.01",
                },
            }
        elif name == "search_entities":
            payload = {
                "data": {"items": [entity], "engine": self.engine},
                "usage": {
                    "settlement_id": "settlement-search",
                    "billing_class": "entity.search",
                    "result_count": 1,
                    "charged_units": "1.01",
                    **self.usage_override,
                },
            }
        else:
            raise AssertionError(f"unexpected MCP tool: {name}")
        return CallToolResult(content=[], structured_content=payload)


def _web_transport(*, published: bool = True) -> httpx.MockTransport:
    entity = _entity()
    if not published:
        entity["review_status"] = "draft"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/login":
            return httpx.Response(200, json={"role": "admin"}, headers={"set-cookie": "pharma_csrf=csrf; Path=/"})
        if request.url.path == "/api/v1/entities" and request.method == "POST":
            assert request.headers["X-CSRF-Token"] == "csrf"
            return httpx.Response(201, json=entity)
        if request.url.path == "/api/v1/entities/entity-1":
            return httpx.Response(200, json=entity)
        if request.url.path == "/api/v1/entities" and request.method == "GET":
            assert request.url.params["q"] == "marker-1"
            assert request.url.params["entity_type"] == "target"
            assert request.url.params["review_status"] == "verified"
            return httpx.Response(200, json={"items": [entity]})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_entry_consistency_compares_web_and_billed_mcp_facts() -> None:
    mcp = FakeMcpSession()
    async with httpx.AsyncClient(base_url="http://web.test", transport=_web_transport()) as web:
        result = await entry_consistency_probe.verify_clients(
            web,
            mcp,
            email="analyst@example.test",
            password=TEST_PASSWORD,
            fixture_marker="marker-1",
            expected_protocol_version="2025-11-25",
        )

    assert result["status"] == "passed"
    assert result["schema"] == "pharma.entry-consistency-acceptance.v1"
    assert result["production_claim"] is False
    assert result["credentials_recorded"] is False
    assert result["fields_compared"] == list(entry_consistency_probe.ENTITY_FIELDS)
    assert result["mcp_billed_calls"] == 2
    assert result["unique_settlements"] == 2
    assert mcp.calls == ["get_entity", "search_entities"]
    assert mcp.list_calls == 1
    assert result["streamable_http_contract_verified"] is True
    assert set(REQUIRED_DOMAIN_TOOLS) <= set(result["listed_mcp_tools"])


@pytest.mark.parametrize(
    ("mcp", "message"),
    [
        (FakeMcpSession(tools=set(REQUIRED_DOMAIN_TOOLS) - {"get_bioactivity_landscape"}), "omitted required"),
        (FakeMcpSession(tools=set(REQUIRED_DOMAIN_TOOLS) | {"build_research_bundle"}), "forbidden research"),
        (FakeMcpSession(engine="postgresql"), "OpenSearch"),
        (FakeMcpSession(usage_override={"billing_class": "target.profile"}), "entity.search"),
        (FakeMcpSession(usage_override={"result_count": 0}), "exactly one fixture"),
        (FakeMcpSession(usage_override={"charged_units": "0.00000000"}), "positive finite"),
        (FakeMcpSession(usage_override={"charged_units": "NaN"}), "positive finite"),
    ],
)
@pytest.mark.asyncio
async def test_canonical_probe_preserves_streamable_domain_and_billing_contract(
    mcp: FakeMcpSession, message: str
) -> None:
    async with httpx.AsyncClient(base_url="http://web.test", transport=_web_transport()) as web:
        with pytest.raises(RuntimeError, match=message):
            await entry_consistency_probe.verify_clients(
                web,
                mcp,
                email="analyst@example.test",
                password=TEST_PASSWORD,
                fixture_marker="marker-1",
                expected_protocol_version="2025-11-25",
            )


@pytest.mark.asyncio
async def test_entry_consistency_rejects_cross_entry_field_drift() -> None:
    async with httpx.AsyncClient(base_url="http://web.test", transport=_web_transport()) as web:
        with pytest.raises(RuntimeError, match=r"drifted canonical fields: \['name'\]"):
            await entry_consistency_probe.verify_clients(
                web,
                FakeMcpSession(entity_name="Drifted name"),
                email="analyst@example.test",
                password=TEST_PASSWORD,
                fixture_marker="marker-1",
                expected_protocol_version="2025-11-25",
            )


@pytest.mark.asyncio
async def test_entry_consistency_rejects_draft_without_a_scoped_publication_step() -> None:
    async with httpx.AsyncClient(base_url="http://web.test", transport=_web_transport(published=False)) as web:
        with pytest.raises(RuntimeError, match="published fixture"):
            await entry_consistency_probe.verify_clients(
                web,
                FakeMcpSession(),
                email="analyst@example.test",
                password=TEST_PASSWORD,
                fixture_marker="marker-1",
                expected_protocol_version="2025-11-25",
            )
