"""The domain inventory and positive-settlement contract for real MCP smoke."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from scripts.mcp_sdk_probe import McpSession, list_all_tools

REQUIRED_DOMAIN_TOOLS = frozenset(
    {
        "get_entity",
        "search_entities",
        "get_commercial_access",
        "estimate_usage",
        "get_usage_summary",
        "get_bioactivity_landscape",
        "compare_target_sar",
        "get_competitive_pipeline",
        "get_company_timeline",
        "search_chemical_structures",
        "create_data_export",
        "get_data_export",
        "cancel_data_export",
        "read_data_export",
    }
)


async def verify_domain_inventory(session: McpSession) -> list[str]:
    names = {tool.name for tool in await list_all_tools(session)}
    missing = REQUIRED_DOMAIN_TOOLS - names
    if missing:
        raise RuntimeError(f"MCP tools/list omitted required domain tools: {sorted(missing)}")
    if "build_research_bundle" in names:
        raise RuntimeError("MCP tools/list exposed the forbidden research-bundle tool")
    return sorted(names)


def verify_positive_settlement(usage: dict[str, Any], billing_class: str) -> None:
    if usage.get("billing_class") != billing_class:
        raise RuntimeError(f"MCP settlement did not use {billing_class}")
    count = usage.get("result_count")
    if not isinstance(count, int) or isinstance(count, bool) or count != 1:
        raise RuntimeError("MCP settlement must account for exactly one fixture result")
    raw_units = usage.get("charged_units")
    try:
        units = Decimal(raw_units) if isinstance(raw_units, str) else Decimal("NaN")
    except InvalidOperation as exc:
        raise RuntimeError("MCP settlement omitted valid charged units") from exc
    if not units.is_finite() or units <= 0:
        raise RuntimeError("MCP settlement must charge positive finite units")
