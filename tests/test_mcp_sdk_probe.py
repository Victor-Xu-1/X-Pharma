from __future__ import annotations

from typing import Any

import pytest
from mcp.types import (
    CallToolResult,
    Implementation,
    InitializeResult,
    ListToolsResult,
    ServerCapabilities,
    TextContent,
    Tool,
)

from scripts import mcp_sdk_probe


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    async def initialize(self) -> InitializeResult:
        return InitializeResult(
            protocolVersion="2025-11-25",
            capabilities=ServerCapabilities(),
            serverInfo=Implementation(name="pharma-intelligence", version="1.0"),
        )

    async def list_tools(self, cursor: str | None = None) -> ListToolsResult:
        assert cursor is None
        names = {
            "search_entities",
            "get_clinical_trial",
            "get_target_profile",
            "search_evidence",
            "estimate_usage",
            "get_usage_summary",
            "create_data_export",
            "get_data_export",
            "cancel_data_export",
            "read_data_export",
            "get_competitive_pipeline",
        }
        return ListToolsResult(
            tools=[
                Tool(
                    name=name,
                    inputSchema={
                        "type": "object",
                        "properties": ({"query": {}, "limit": {}, "cursor": {}} if name == "search_entities" else {}),
                    },
                )
                for name in names
            ]
        )

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        self.calls.append((name, arguments))
        payload: dict[str, Any]
        if name == "estimate_usage":
            payload = {"estimated_units_before_response_bytes": "1", "rate_card_revision": "revision-1"}
        elif name == "search_entities":
            assert arguments is not None
            cursor = arguments.get("cursor")
            if cursor not in {None, "valid-cursor-Z"}:
                return CallToolResult(
                    content=[TextContent(type="text", text="invalid cursor signature")],
                    isError=True,
                )
            entity_id = "target-1" if cursor is None else "target-2"
            payload = {
                "data": {
                    "items": [{"id": entity_id}],
                    "page_depth": 1 if cursor is None else 2,
                    "next_cursor": "valid-cursor-Z" if cursor is None else None,
                },
                "usage": {"settlement_id": f"settlement-search-{entity_id}"},
            }
        elif name == "get_target_profile":
            payload = {"data": {"program_count": 1}, "usage": {"settlement_id": "settlement-target"}}
        elif name == "get_competitive_pipeline":
            payload = {
                "data": {
                    "items": [
                        {
                            "target_entity_id": "target-1",
                            "target_combination_key": "target-1|target-2",
                            "targets": [
                                {"entity_id": "target-1", "role": "primary"},
                                {"entity_id": "target-2", "role": "combination"},
                            ],
                        }
                    ]
                },
                "usage": {"settlement_id": "settlement-pipeline"},
            }
        elif name == "search_evidence":
            payload = {"usage": {"settlement_id": "settlement-evidence"}}
        elif name == "get_usage_summary":
            payload = {"settlement_count": 5}
        else:
            raise AssertionError(f"unexpected tool: {name}")
        return CallToolResult(content=[], structuredContent=payload)


@pytest.mark.asyncio
async def test_python_sdk_verifies_initialize_discovery_and_billed_calls() -> None:
    session = FakeSession()

    result = await mcp_sdk_probe.verify_session(
        session,
        "mcp-acceptance-query",
        "2025-11-25",
    )

    assert result["client"] == "Python MCP SDK"
    assert result["protocol_version"] == "2025-11-25"
    assert result["tools"] == 11
    assert result["billed_calls"] == 5
    assert result["target_id"] == "target-1"
    assert result["usage_settlements"] == 5
    assert result["pagination_unique_entities"] == 2
    assert result["invalid_cursor_rejected"] is True
    assert result["recovered_after_error"] is True
    assert result["competitive_program_items"] == 1
    invoked = [name for name, _arguments in session.calls]
    assert invoked == [
        "estimate_usage",
        "search_entities",
        "search_entities",
        "search_entities",
        "get_target_profile",
        "get_competitive_pipeline",
        "search_evidence",
        "get_usage_summary",
    ]


def test_combined_client_evidence_requires_same_query_and_entity() -> None:
    inspector = {
        "client": "MCP Inspector",
        "status": "passed",
        "query_sha256": "query-hash",
        "target_id": "target-1",
        "billed_calls": 5,
        "usage_settlements": 5,
        "tool_contract_sha256": "contract-hash",
        "pagination_pages": 2,
        "pagination_unique_entities": 2,
        "pagination_entity_ids_sha256": "pagination-hash",
        "invalid_cursor_rejected": True,
        "recovered_after_error": True,
        "competitive_program_items": 1,
        "cross_domain_tool": "get_competitive_pipeline",
    }
    sdk = {
        "client": "Python MCP SDK",
        "client_version": "1.28.1",
        "protocol_version": "2025-11-25",
        "status": "passed",
        "query_sha256": "query-hash",
        "target_id": "target-1",
        "billed_calls": 5,
        "usage_settlements": 10,
        "tool_contract_sha256": "contract-hash",
        "pagination_pages": 2,
        "pagination_unique_entities": 2,
        "pagination_entity_ids_sha256": "pagination-hash",
        "invalid_cursor_rejected": True,
        "recovered_after_error": True,
        "competitive_program_items": 1,
        "cross_domain_tool": "get_competitive_pipeline",
    }

    combined = mcp_sdk_probe.combine_results(inspector, sdk)

    assert combined["schema"] == "pharma.mcp-interoperability-acceptance.v3"
    assert combined["schema_version"] == 3
    assert combined["production_claim"] is False
    assert combined["credentials_recorded"] is False
    assert combined["client_count"] == 2
    assert combined["billed_calls"] == 10
    assert combined["usage_settlements"] == 10
    assert combined["workflow_assertions"]["entity_pagination"] is True
    assert combined["workflow_assertions"]["export_lifecycle_discovered"] is True
    assert combined["workflow_assertions"]["export_execution_evidence_category"] == "mcp_async_tasks"
    assert combined["python_sdk_version"] == sdk.get("client_version")
    assert combined["protocol_version"] == sdk.get("protocol_version")
    assert combined["clients"] == [inspector, sdk]

    with pytest.raises(RuntimeError, match="same acceptance query"):
        mcp_sdk_probe.combine_results(inspector, {**sdk, "query_sha256": "different"})
    with pytest.raises(RuntimeError, match="same acceptance entity"):
        mcp_sdk_probe.combine_results(inspector, {**sdk, "target_id": "target-2"})
    with pytest.raises(RuntimeError, match="same tool contracts"):
        mcp_sdk_probe.combine_results(inspector, {**sdk, "tool_contract_sha256": "different"})
    with pytest.raises(RuntimeError, match="same paginated entities"):
        mcp_sdk_probe.combine_results(inspector, {**sdk, "pagination_entity_ids_sha256": "different"})


@pytest.mark.asyncio
async def test_python_sdk_rejects_negotiated_protocol_drift() -> None:
    with pytest.raises(RuntimeError, match="unexpected protocol version"):
        await mcp_sdk_probe.verify_session(
            FakeSession(),
            "mcp-acceptance-query",
            "2026-01-01",
        )


@pytest.mark.asyncio
async def test_python_sdk_rejects_installed_version_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_sdk_probe, "version", lambda _distribution: "9.9.9")

    with pytest.raises(RuntimeError, match="version mismatch"):
        await mcp_sdk_probe.verify(
            "http://127.0.0.1:8090/mcp",
            "token",
            "mcp-acceptance-query",
            "1.28.1",
            "2025-11-25",
        )


def test_python_sdk_tool_errors_are_bounded_and_explicit() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="denied")],
        isError=True,
    )

    with pytest.raises(RuntimeError, match="denied"):
        mcp_sdk_probe.structured_tool_result(result)
