from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from scripts.mcp_contract_fingerprint import tool_contract_sha256

PAGEABLE_CURSOR_TOOLS = frozenset(
    {
        "search_entities",
        "resolve_entity",
        "search_evidence",
        "get_bioactivity_landscape",
        "compare_target_sar",
        "get_competitive_pipeline",
        "search_structures",
        "search_chemical_structures",
        "get_clinical_trials",
        "get_patent_landscape",
        "get_deals",
        "get_company_timeline",
        "get_regulatory_events",
        "get_epidemiology_observations",
        "get_news_events",
        "search_knowledge_pages",
    }
)


def _run_inspector(
    node: Path,
    cli: Path,
    url: str,
    token: str,
    method: str,
    *,
    tool_name: str | None = None,
    arguments: dict[str, Any] | None = None,
    allow_tool_error: bool = False,
) -> dict[str, Any]:
    command = [
        str(node),
        str(cli),
        "--cli",
        url,
        "--transport",
        "http",
        "--method",
        method,
    ]
    if tool_name:
        command.extend(["--tool-name", tool_name])
    if arguments:
        command.append("--tool-arg")
        command.extend(f"{key}={json.dumps(value, separators=(',', ':'))}" for key, value in arguments.items())
    command.extend(["--header", f"Authorization: Bearer {token}"])
    environment = os.environ.copy()
    environment["PATH"] = f"{node.parent}{os.pathsep}{environment.get('PATH', '')}"
    completed = subprocess.run(  # noqa: S603
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
        cwd=cli.parent,
    )
    if completed.returncode:
        detail = f"{completed.stdout}\n{completed.stderr}".replace(token, "[REDACTED]").strip()
        raise RuntimeError(f"Inspector {method} failed: {detail}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("Inspector returned a non-object JSON response")
    if payload.get("isError") and not allow_tool_error:
        raise RuntimeError(f"Inspector tool returned an error: {_safe_error(payload)}")
    return payload


def _safe_error(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        return str(content[0].get("text", "unknown tool error"))[:1000]
    return "unknown tool error"


def _is_cursor_rejection(detail: str) -> bool:
    normalized = detail.lower()
    return "cursor" in normalized or (
        "403 forbidden" in normalized and "/internal/v1/commercial/reservations" in normalized
    )


def _structured(payload: dict[str, Any]) -> dict[str, Any]:
    structured = payload.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = payload.get("content")
    if not isinstance(content, list) or not content or not isinstance(content[0], dict):
        raise RuntimeError("Inspector response has no structured or text content")
    text = content[0].get("text")
    if not isinstance(text, str):
        raise RuntimeError("Inspector response text is missing")
    decoded = json.loads(text)
    if not isinstance(decoded, dict):
        raise RuntimeError("Inspector text content is not an object")
    return decoded


def _verify_pageable_cursor_schemas(tools: list[Any]) -> int:
    schemas = {
        item.get("name"): item.get("inputSchema")
        for item in tools
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    missing_tools = PAGEABLE_CURSOR_TOOLS - schemas.keys()
    if missing_tools:
        raise RuntimeError(f"Inspector tools/list omitted pageable tools: {sorted(missing_tools)}")
    missing_cursor = []
    for name in sorted(PAGEABLE_CURSOR_TOOLS):
        schema = schemas[name]
        properties = schema.get("properties") if isinstance(schema, dict) else None
        if not isinstance(properties, dict) or "cursor" not in properties:
            missing_cursor.append(name)
    if missing_cursor:
        raise RuntimeError(f"Pageable tools omitted cursor input schema: {missing_cursor}")
    return len(PAGEABLE_CURSOR_TOOLS)


def _validate_query(query: str) -> str:
    if not 3 <= len(query) <= 120 or not query.isprintable():
        raise RuntimeError("Inspector acceptance query must contain 3-120 printable characters")
    return query


def _tamper_cursor(cursor: str) -> str:
    if not cursor:
        raise RuntimeError("Inspector first search page omitted its continuation cursor")
    replacement = "A" if cursor[-1] != "A" else "B"
    return f"{cursor[:-1]}{replacement}"


def _settlement_id(payload: dict[str, Any], operation: str) -> str:
    usage = payload.get("usage")
    settlement_id = usage.get("settlement_id") if isinstance(usage, dict) else None
    if not isinstance(settlement_id, str) or not settlement_id:
        raise RuntimeError(f"Inspector {operation} omitted its settlement")
    return settlement_id


def verify(node: Path, cli: Path, url: str, token: str, query: str) -> dict[str, Any]:
    query = _validate_query(query)
    listed = _run_inspector(node, cli, url, token, "tools/list")
    tools = listed.get("tools")
    if not isinstance(tools, list):
        raise RuntimeError("Inspector tools/list omitted tools")
    if not all(isinstance(item, dict) for item in tools):
        raise RuntimeError("Inspector tools/list returned an invalid tool contract")
    tool_contract = tool_contract_sha256(tools)
    names = {item.get("name") for item in tools if isinstance(item, dict)}
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
        raise RuntimeError(f"Inspector tools/list omitted: {sorted(missing)}")
    pageable_cursor_tools = _verify_pageable_cursor_schemas(tools)

    estimate = _structured(
        _run_inspector(
            node,
            cli,
            url,
            token,
            "tools/call",
            tool_name="estimate_usage",
            arguments={"billing_class": "entity.search", "requested_result_limit": 5},
        )
    )
    if not estimate.get("estimated_units_before_response_bytes") or not estimate.get("rate_card_revision"):
        raise RuntimeError("Inspector estimate response is incomplete")

    search = _structured(
        _run_inspector(
            node,
            cli,
            url,
            token,
            "tools/call",
            tool_name="search_entities",
            arguments={
                "query": query,
                "limit": 1,
                "idempotency_key": f"inspector-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    data = search.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Inspector billed search omitted data or settlement")
    settlements = [_settlement_id(search, "first entity search page")]
    items = data.get("items")
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise RuntimeError("Inspector billed search returned no acceptance candidate")
    target_id = items[0].get("id")
    if not isinstance(target_id, str) or not target_id:
        raise RuntimeError("Inspector billed search omitted stable entity ID")

    next_cursor = data.get("next_cursor")
    if not isinstance(next_cursor, str) or not next_cursor:
        raise RuntimeError("Inspector first entity search page omitted its continuation cursor")
    rejected = _run_inspector(
        node,
        cli,
        url,
        token,
        "tools/call",
        tool_name="search_entities",
        arguments={
            "query": query,
            "limit": 1,
            "cursor": _tamper_cursor(next_cursor),
            "idempotency_key": f"inspector-{uuid.uuid4().hex}",
            "max_billable_units": "100",
        },
        allow_tool_error=True,
    )
    rejection_detail = _safe_error(rejected)
    if rejected.get("isError") is not True or not _is_cursor_rejection(rejection_detail):
        raise RuntimeError(f"Inspector did not explicitly reject the tampered entity cursor: {rejection_detail}")

    second = _structured(
        _run_inspector(
            node,
            cli,
            url,
            token,
            "tools/call",
            tool_name="search_entities",
            arguments={
                "query": query,
                "limit": 1,
                "cursor": next_cursor,
                "idempotency_key": f"inspector-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    second_data = second.get("data")
    if not isinstance(second_data, dict) or second_data.get("page_depth") != 2:
        raise RuntimeError("Inspector did not recover with the valid second entity page")
    second_items = second_data.get("items")
    if not isinstance(second_items, list) or len(second_items) != 1 or not isinstance(second_items[0], dict):
        raise RuntimeError("Inspector valid second entity page returned an invalid result")
    second_target_id = second_items[0].get("id")
    if not isinstance(second_target_id, str) or not second_target_id or second_target_id == target_id:
        raise RuntimeError("Inspector entity pagination repeated or omitted the second stable entity")
    if second_data.get("next_cursor") is not None:
        raise RuntimeError("Inspector two-entity fixture unexpectedly exposed a third entity page")
    settlements.append(_settlement_id(second, "second entity search page"))
    pagination_digest = hashlib.sha256("\n".join(sorted((target_id, second_target_id))).encode()).hexdigest()

    target = _structured(
        _run_inspector(
            node,
            cli,
            url,
            token,
            "tools/call",
            tool_name="get_target_profile",
            arguments={
                "target_entity_id": target_id,
                "idempotency_key": f"inspector-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    settlements.append(_settlement_id(target, "target profile"))
    target_data = target.get("data")
    if not isinstance(target_data, dict) or int(target_data.get("program_count", 0)) < 1:
        raise RuntimeError("Inspector target profile omitted the seeded competitive program")

    pipeline = _structured(
        _run_inspector(
            node,
            cli,
            url,
            token,
            "tools/call",
            tool_name="get_competitive_pipeline",
            arguments={
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
                "idempotency_key": f"inspector-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    settlements.append(_settlement_id(pipeline, "competitive pipeline"))
    pipeline_data = pipeline.get("data")
    pipeline_items = pipeline_data.get("items") if isinstance(pipeline_data, dict) else None
    if not isinstance(pipeline_items, list) or not pipeline_items or not isinstance(pipeline_items[0], dict):
        raise RuntimeError("Inspector competitive pipeline returned no seeded program")
    pipeline_item = pipeline_items[0]
    targets = pipeline_item.get("targets")
    if not isinstance(targets, list) or len(targets) != 2 or not all(isinstance(item, dict) for item in targets):
        raise RuntimeError("Inspector competitive pipeline omitted the authoritative target combination")
    returned_target_ids = {item.get("entity_id") for item in targets}
    if returned_target_ids != {target_id, second_target_id}:
        raise RuntimeError("Inspector competitive pipeline returned an inconsistent target combination")
    if {item.get("role") for item in targets} != {"primary", "combination"}:
        raise RuntimeError("Inspector competitive pipeline omitted target roles")
    expected_combination_key = "|".join(sorted((target_id, second_target_id)))
    if pipeline_item.get("target_combination_key") != expected_combination_key:
        raise RuntimeError("Inspector competitive pipeline returned an unstable target combination key")

    evidence = _structured(
        _run_inspector(
            node,
            cli,
            url,
            token,
            "tools/call",
            tool_name="search_evidence",
            arguments={
                "query": query,
                "limit": 5,
                "idempotency_key": f"inspector-{uuid.uuid4().hex}",
                "max_billable_units": "100",
            },
        )
    )
    settlements.append(_settlement_id(evidence, "evidence search"))
    if len(set(settlements)) != 5:
        raise RuntimeError("Inspector billed workflow did not create five unique settlements")

    summary = _structured(_run_inspector(node, cli, url, token, "tools/call", tool_name="get_usage_summary"))
    if int(summary.get("settlement_count", 0)) < 5:
        raise RuntimeError("Inspector usage summary did not include completed calls")
    return {
        "client": "MCP Inspector",
        "tools": len(names),
        "billed_calls": 5,
        "pageable_cursor_tools": pageable_cursor_tools,
        "tool_contract_sha256": tool_contract,
        "target_id": target_id,
        "pagination_pages": 2,
        "pagination_unique_entities": 2,
        "pagination_entity_ids_sha256": pagination_digest,
        "invalid_cursor_rejected": True,
        "recovered_after_error": True,
        "competitive_program_items": len(pipeline_items),
        "cross_domain_tool": "get_competitive_pipeline",
        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
        "usage_settlements": summary["settlement_count"],
        "status": "passed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--query", required=True)
    args = parser.parse_args()
    token = os.environ.get("TEST_MCP_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("TEST_MCP_ACCESS_TOKEN is required")
    print(json.dumps(verify(args.node, args.cli, args.url, token, args.query), sort_keys=True))


if __name__ == "__main__":
    main()
