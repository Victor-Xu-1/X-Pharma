from __future__ import annotations

from typing import Any

import httpx
import pytest
from mcp.types import (
    CallToolResult,
    Implementation,
    InitializeResult,
    ServerCapabilities,
)

from scripts import entry_consistency_probe

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
        "review_status": "draft",
        "canonical_entity_id": "entity-1",
        "identity_identifiers": [
            {
                "namespace": "acceptance",
                "value": "marker-1",
                "normalized_value": "marker-1",
                "trusted_namespace": False,
                "review_status": "draft",
                "source_document_id": None,
            }
        ],
        "created_at": "2026-07-18T00:00:00Z",
        "updated_at": "2026-07-18T00:00:00Z",
    }


class FakeMcpSession:
    def __init__(self, *, entity_name: str = "Entry consistency marker-1") -> None:
        self.entity_name = entity_name
        self.calls: list[str] = []

    async def initialize(self) -> InitializeResult:
        return InitializeResult(
            protocolVersion="2025-11-25",
            capabilities=ServerCapabilities(),
            serverInfo=Implementation(name="test", version="1"),
        )

    async def list_tools(self, cursor: str | None = None) -> Any:
        raise AssertionError(f"unexpected tools/list: {cursor}")

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        self.calls.append(name)
        entity = _entity(self.entity_name)
        if name == "get_entity":
            payload = {"data": entity, "usage": {"settlement_id": "settlement-get"}}
        elif name == "search_entities":
            payload = {"data": {"items": [entity]}, "usage": {"settlement_id": "settlement-search"}}
        else:
            raise AssertionError(f"unexpected MCP tool: {name}")
        return CallToolResult(content=[], structuredContent=payload)


def _web_transport() -> httpx.MockTransport:
    entity = _entity()

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
