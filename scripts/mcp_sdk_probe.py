from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import uuid
from importlib.metadata import version
from typing import Any, Protocol, cast

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, Implementation, InitializeResult, ListToolsResult

from pharma_intel.product import PRODUCT_NAME, PRODUCT_VERSION
from scripts.mcp_contract_fingerprint import tool_contract_sha256


class McpSession(Protocol):
    async def initialize(self) -> InitializeResult: ...

    async def list_tools(self, cursor: str | None = None) -> ListToolsResult: ...

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult: ...


class ClientSessionAdapter:
    """Expose the subset used by acceptance checks without SDK overload leakage."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def initialize(self) -> InitializeResult:
        return await self._session.initialize()

    async def list_tools(self, cursor: str | None = None) -> ListToolsResult:
        return await self._session.list_tools(cursor)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> CallToolResult:
        return await self._session.call_tool(name, arguments)


def _validate_query(query: str) -> str:
    if not 3 <= len(query) <= 120 or not query.isprintable():
        raise RuntimeError("Python SDK acceptance query must contain 3-120 printable characters")
    return query


def structured_tool_result(result: CallToolResult) -> dict[str, Any]:
    if result.isError:
        detail = "unknown tool error"
        if result.content and hasattr(result.content[0], "text"):
            detail = str(result.content[0].text)[:1000]
        raise RuntimeError(f"Python SDK tool returned an error: {detail}")
    if isinstance(result.structuredContent, dict):
        return result.structuredContent
    if not result.content or not hasattr(result.content[0], "text"):
        raise RuntimeError("Python SDK response has no structured or text content")
    decoded = json.loads(str(result.content[0].text))
    if not isinstance(decoded, dict):
        raise RuntimeError("Python SDK text content is not an object")
    return cast(dict[str, Any], decoded)


def expected_tool_error(result: CallToolResult, operation: str) -> str:
    if result.isError is not True:
        raise RuntimeError(f"Python SDK {operation} unexpectedly succeeded")
    detail = "unknown tool error"
    if result.content and hasattr(result.content[0], "text"):
        detail = str(result.content[0].text)[:1000]
    normalized = detail.lower()
    cursor_rejection = "cursor" in normalized or (
        "403 forbidden" in normalized and "/internal/v1/commercial/reservations" in normalized
    )
    if not cursor_rejection:
        raise RuntimeError(f"Python SDK {operation} returned an unrelated error: {detail}")
    return detail


def _tamper_cursor(cursor: str) -> str:
    if not cursor:
        raise RuntimeError("Python SDK first search page omitted its continuation cursor")
    replacement = "A" if cursor[-1] != "A" else "B"
    return f"{cursor[:-1]}{replacement}"


def _settlement_id(payload: dict[str, Any], operation: str) -> str:
    usage = payload.get("usage")
    settlement_id = usage.get("settlement_id") if isinstance(usage, dict) else None
    if not isinstance(settlement_id, str) or not settlement_id:
        raise RuntimeError(f"Python SDK {operation} omitted its settlement")
    return settlement_id


async def _all_tools(session: McpSession) -> list[Any]:
    tools: list[Any] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for _ in range(20):
        page = await session.list_tools(cursor=cursor)
        tools.extend(page.tools)
        cursor = page.nextCursor
        if cursor is None:
            return tools
        if cursor in seen_cursors:
            raise RuntimeError("Python SDK tools/list returned a repeated cursor")
        seen_cursors.add(cursor)
    raise RuntimeError("Python SDK tools/list exceeded the page limit")


async def verify_session(
    session: McpSession,
    query: str,
    expected_protocol_version: str,
) -> dict[str, Any]:
    query = _validate_query(query)
    initialized = await session.initialize()
    server_info = initialized.serverInfo
    if not server_info.name or not initialized.protocolVersion:
        raise RuntimeError("Python SDK initialize response omitted server or protocol metadata")
    if server_info.name != PRODUCT_NAME or server_info.version != PRODUCT_VERSION:
        raise RuntimeError("Python SDK initialized an unexpected X-Pharma product identity")
    if initialized.protocolVersion != expected_protocol_version:
        raise RuntimeError(
            "Python SDK negotiated an unexpected protocol version: "
            f"{initialized.protocolVersion} != {expected_protocol_version}"
        )

    tools = await _all_tools(session)
    tool_contract = tool_contract_sha256(
        [
            {
                "name": tool.name,
                "inputSchema": tool.inputSchema,
                "outputSchema": tool.outputSchema,
            }
            for tool in tools
        ]
    )
    names = {tool.name for tool in tools}
    if len(names) != len(tools):
        raise RuntimeError("Python SDK tools/list returned duplicate tool names")
    required = {
        "search_entities",
        "get_clinical_trial",
        "get_target_profile",
        "search_evidence",
        "get_competitive_pipeline",
        "estimate_usage",
        "get_usage_summary",
        "create_data_export",
        "get_data_export",
        "cancel_data_export",
        "read_data_export",
    }
    missing = required - names
    if missing:
        raise RuntimeError(f"Python SDK tools/list omitted: {sorted(missing)}")
    search_tool = next(tool for tool in tools if tool.name == "search_entities")
    properties = search_tool.inputSchema.get("properties")
    if not isinstance(properties, dict) or not {"query", "limit", "cursor"} <= properties.keys():
        raise RuntimeError("Python SDK search_entities schema is incomplete")

    estimate = structured_tool_result(
        await session.call_tool(
            "estimate_usage",
            {"billing_class": "entity.search", "requested_result_limit": 5},
        )
    )
    if not estimate.get("estimated_units_before_response_bytes") or not estimate.get("rate_card_revision"):
        raise RuntimeError("Python SDK estimate response is incomplete")

    settlements: list[str] = []
    search = structured_tool_result(
        await session.call_tool(
            "search_entities",
            {
                "query": query,
                "limit": 1,
                "idempotency_key": f"python-sdk-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    data = search.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Python SDK billed search omitted data or settlement")
    settlements.append(_settlement_id(search, "first entity search page"))
    items = data.get("items")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise RuntimeError("Python SDK billed search returned no acceptance candidate")
    target_id = items[0].get("id")
    if not isinstance(target_id, str) or not target_id:
        raise RuntimeError("Python SDK billed search omitted stable entity ID")

    next_cursor = data.get("next_cursor")
    if not isinstance(next_cursor, str) or not next_cursor:
        raise RuntimeError("Python SDK first entity search page omitted its continuation cursor")
    expected_tool_error(
        await session.call_tool(
            "search_entities",
            {
                "query": query,
                "limit": 1,
                "cursor": _tamper_cursor(next_cursor),
                "idempotency_key": f"python-sdk-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        ),
        "tampered cursor check",
    )
    second = structured_tool_result(
        await session.call_tool(
            "search_entities",
            {
                "query": query,
                "limit": 1,
                "cursor": next_cursor,
                "idempotency_key": f"python-sdk-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    second_data = second.get("data")
    if not isinstance(second_data, dict) or second_data.get("page_depth") != 2:
        raise RuntimeError("Python SDK did not recover with the valid second entity page")
    second_items = second_data.get("items")
    if not isinstance(second_items, list) or len(second_items) != 1 or not isinstance(second_items[0], dict):
        raise RuntimeError("Python SDK valid second entity page returned an invalid result")
    second_target_id = second_items[0].get("id")
    if not isinstance(second_target_id, str) or not second_target_id or second_target_id == target_id:
        raise RuntimeError("Python SDK entity pagination repeated or omitted the second stable entity")
    if second_data.get("next_cursor") is not None:
        raise RuntimeError("Python SDK two-entity fixture unexpectedly exposed a third entity page")
    settlements.append(_settlement_id(second, "second entity search page"))
    pagination_digest = hashlib.sha256("\n".join(sorted((target_id, second_target_id))).encode()).hexdigest()

    target = structured_tool_result(
        await session.call_tool(
            "get_target_profile",
            {
                "target_entity_id": target_id,
                "idempotency_key": f"python-sdk-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    settlements.append(_settlement_id(target, "target profile"))
    target_data = target.get("data")
    if not isinstance(target_data, dict) or int(target_data.get("program_count", 0)) < 1:
        raise RuntimeError("Python SDK target profile omitted the seeded competitive program")

    pipeline = structured_tool_result(
        await session.call_tool(
            "get_competitive_pipeline",
            {
                "target_entity_id": target_id,
                "limit": 5,
                "global_phase": "phase_2",
                "china_phase": "phase_1",
                "development_rights_region": "Global",
                "commercialization_rights_region": "Greater China",
                "program_tag": "first_in_class",
                "milestone_type": "first_patient_in",
                "milestone_from": "2026-06-01T00:00:00Z",
                "milestone_to": "2026-06-30T23:59:59Z",
                "idempotency_key": f"python-sdk-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    settlements.append(_settlement_id(pipeline, "competitive pipeline"))
    pipeline_data = pipeline.get("data")
    pipeline_items = pipeline_data.get("items") if isinstance(pipeline_data, dict) else None
    if not isinstance(pipeline_items, list) or not pipeline_items or not isinstance(pipeline_items[0], dict):
        raise RuntimeError("Python SDK competitive pipeline returned no seeded program")
    pipeline_item = pipeline_items[0]
    targets = pipeline_item.get("targets")
    if not isinstance(targets, list) or len(targets) != 2 or not all(isinstance(item, dict) for item in targets):
        raise RuntimeError("Python SDK competitive pipeline omitted the authoritative target combination")
    returned_target_ids = {item.get("entity_id") for item in targets}
    if returned_target_ids != {target_id, second_target_id}:
        raise RuntimeError("Python SDK competitive pipeline returned an inconsistent target combination")
    if {item.get("role") for item in targets} != {"primary", "combination"}:
        raise RuntimeError("Python SDK competitive pipeline omitted target roles")
    expected_combination_key = "|".join(sorted((target_id, second_target_id)))
    if pipeline_item.get("target_combination_key") != expected_combination_key:
        raise RuntimeError("Python SDK competitive pipeline returned an unstable target combination key")

    evidence = structured_tool_result(
        await session.call_tool(
            "search_evidence",
            {
                "query": query,
                "limit": 5,
                "idempotency_key": f"python-sdk-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    settlements.append(_settlement_id(evidence, "evidence search"))
    if len(set(settlements)) != 5:
        raise RuntimeError("Python SDK billed calls did not create unique settlements")

    summary = structured_tool_result(await session.call_tool("get_usage_summary"))
    if int(summary.get("settlement_count", 0)) < 5:
        raise RuntimeError("Python SDK usage summary did not include completed calls")
    return {
        "client": "Python MCP SDK",
        "client_version": version("mcp"),
        "server_name": server_info.name,
        "server_version": server_info.version,
        "protocol_version": initialized.protocolVersion,
        "tools": len(names),
        "tool_contract_sha256": tool_contract,
        "billed_calls": 5,
        "target_id": target_id,
        "pagination_pages": 2,
        "pagination_unique_entities": 2,
        "pagination_entity_ids_sha256": pagination_digest,
        "invalid_cursor_rejected": True,
        "recovered_after_error": True,
        "competitive_program_items": len(pipeline_items),
        "cross_domain_tool": "get_competitive_pipeline",
        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
        "usage_settlements": int(summary["settlement_count"]),
        "status": "passed",
    }


def combine_results(inspector: dict[str, Any], sdk: dict[str, Any]) -> dict[str, Any]:
    if inspector.get("status") != "passed" or sdk.get("status") != "passed":
        raise RuntimeError("Both MCP clients must pass before evidence can be combined")
    if inspector.get("query_sha256") != sdk.get("query_sha256"):
        raise RuntimeError("MCP clients did not execute the same acceptance query")
    if inspector.get("target_id") != sdk.get("target_id"):
        raise RuntimeError("MCP clients did not resolve the same acceptance entity")
    if inspector.get("tool_contract_sha256") != sdk.get("tool_contract_sha256"):
        raise RuntimeError("MCP clients did not discover the same tool contracts")
    if inspector.get("pagination_entity_ids_sha256") != sdk.get("pagination_entity_ids_sha256"):
        raise RuntimeError("MCP clients did not traverse the same paginated entities")
    workflow_assertions = {
        "capability_discovery": True,
        "cost_estimation": True,
        "entity_pagination": True,
        "tampered_cursor_rejection": True,
        "error_recovery": True,
        "target_profile": True,
        "competitive_pipeline": True,
        "evidence_search": True,
        "usage_accounting": True,
        "export_lifecycle_discovered": True,
        "export_execution_evidence_category": "mcp_async_tasks",
    }
    return {
        **inspector,
        "schema": "pharma.mcp-interoperability-acceptance.v3",
        "schema_version": 3,
        "environment": "local-wsl-controlled-fixture",
        "production_claim": False,
        "credentials_recorded": False,
        "client": "MCP Inspector + Python MCP SDK",
        "client_count": 2,
        "clients": [inspector, sdk],
        "python_sdk_version": sdk.get("client_version"),
        "protocol_version": sdk.get("protocol_version"),
        "billed_calls": int(inspector.get("billed_calls", 0)) + int(sdk.get("billed_calls", 0)),
        "workflow_assertions": workflow_assertions,
        "usage_settlements": max(
            int(inspector.get("usage_settlements", 0)),
            int(sdk.get("usage_settlements", 0)),
        ),
        "status": "passed",
    }


async def verify(
    url: str,
    token: str,
    query: str,
    expected_sdk_version: str,
    expected_protocol_version: str,
) -> dict[str, Any]:
    installed_sdk_version = version("mcp")
    if installed_sdk_version != expected_sdk_version:
        raise RuntimeError(f"Python MCP SDK version mismatch: {installed_sdk_version} != {expected_sdk_version}")
    headers = {"Authorization": f"Bearer {token}"}
    timeout = httpx.Timeout(60, connect=10)
    async with httpx.AsyncClient(headers=headers, timeout=timeout, trust_env=False) as http_client:
        async with streamable_http_client(url, http_client=http_client) as (read_stream, write_stream, _session_id):
            client_info = Implementation(name="pharma-python-sdk-acceptance", version=version("mcp"))
            async with ClientSession(read_stream, write_stream, client_info=client_info) as session:
                return await verify_session(
                    ClientSessionAdapter(session),
                    query,
                    expected_protocol_version,
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--expected-sdk-version", required=True)
    parser.add_argument("--expected-protocol-version", required=True)
    parser.add_argument("--inspector-result-json", default="")
    args = parser.parse_args()
    token = os.environ.get("TEST_MCP_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("TEST_MCP_ACCESS_TOKEN is required")
    sdk_result = asyncio.run(
        verify(
            args.url,
            token,
            args.query,
            args.expected_sdk_version,
            args.expected_protocol_version,
        )
    )
    result = sdk_result
    if args.inspector_result_json:
        inspector = json.loads(args.inspector_result_json)
        if not isinstance(inspector, dict):
            raise RuntimeError("Inspector result must be a JSON object")
        result = combine_results(inspector, sdk_result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
