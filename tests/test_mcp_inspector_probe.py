from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import mcp_inspector_probe


def test_inspector_runs_from_declared_cli_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = tmp_path / "inspector" / "cli" / "build" / "cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    node = tmp_path / "node"
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout='{"tools": []}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = mcp_inspector_probe._run_inspector(
        node,
        cli,
        "http://127.0.0.1:8090/mcp",
        "test-token",
        "tools/list",
    )

    assert result == {"tools": []}
    assert captured["cwd"] == cli.parent
    assert captured["timeout"] == 60
    assert captured["command"][:2] == [str(node), str(cli)]
    assert "Authorization: Bearer test-token" in captured["command"]


def test_pageable_tool_schemas_require_cursor_input() -> None:
    tools: list[dict[str, Any]] = [
        {
            "name": name,
            "inputSchema": {"type": "object", "properties": {"cursor": {"type": "string"}}},
        }
        for name in mcp_inspector_probe.PAGEABLE_CURSOR_TOOLS
    ]
    assert mcp_inspector_probe._verify_pageable_cursor_schemas(tools) == 16

    properties = tools[0]["inputSchema"]["properties"]
    assert isinstance(properties, dict)
    properties.pop("cursor")
    with pytest.raises(RuntimeError, match="omitted cursor input schema"):
        mcp_inspector_probe._verify_pageable_cursor_schemas(tools)


def test_verify_uses_isolated_query_for_entity_and_evidence_search(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    query = "mcp-acceptance-1234"
    calls: list[tuple[str | None, dict[str, Any] | None]] = []
    tool_names = mcp_inspector_probe.PAGEABLE_CURSOR_TOOLS | {
        "estimate_usage",
        "get_usage_summary",
        "create_data_export",
        "get_data_export",
        "get_clinical_trial",
        "cancel_data_export",
        "read_data_export",
        "get_target_profile",
        "get_competitive_pipeline",
    }
    valid_cursor = "valid-cursor-Z"

    def fake_run(
        _node: Path,
        _cli: Path,
        _url: str,
        _token: str,
        method: str,
        *,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        allow_tool_error: bool = False,
    ) -> dict[str, Any]:
        calls.append((tool_name, arguments))
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": name,
                        "inputSchema": {
                            "type": "object",
                            "properties": {"cursor": {"type": "string"}},
                        },
                    }
                    for name in tool_names
                ]
            }
        if tool_name == "estimate_usage":
            return {
                "structuredContent": {
                    "estimated_units_before_response_bytes": "1",
                    "rate_card_revision": "test",
                }
            }
        if tool_name == "search_entities":
            assert arguments is not None
            cursor = arguments.get("cursor")
            if cursor not in {None, valid_cursor}:
                assert allow_tool_error is True
                return {"isError": True, "content": [{"type": "text", "text": "invalid cursor signature"}]}
            entity_id = "target-id" if cursor is None else "target-id-2"
            return {
                "structuredContent": {
                    "data": {
                        "items": [{"id": entity_id}],
                        "page_depth": 1 if cursor is None else 2,
                        "next_cursor": valid_cursor if cursor is None else None,
                    },
                    "usage": {"settlement_id": f"settlement-search-{entity_id}"},
                }
            }
        if tool_name == "get_target_profile":
            return {
                "structuredContent": {
                    "data": {"program_count": 1},
                    "usage": {"settlement_id": "settlement-target"},
                }
            }
        if tool_name == "get_competitive_pipeline":
            return {
                "structuredContent": {
                    "data": {
                        "items": [
                            {
                                "target_entity_id": "target-id",
                                "target_combination_key": "target-id|target-id-2",
                                "targets": [
                                    {"entity_id": "target-id", "role": "primary"},
                                    {"entity_id": "target-id-2", "role": "combination"},
                                ],
                            }
                        ]
                    },
                    "usage": {"settlement_id": "settlement-pipeline"},
                }
            }
        if tool_name == "search_evidence":
            return {"structuredContent": {"usage": {"settlement_id": "settlement-evidence"}}}
        if tool_name == "get_usage_summary":
            return {"structuredContent": {"settlement_count": 5}}
        raise AssertionError(f"unexpected Inspector call: {method} {tool_name}")

    monkeypatch.setattr(mcp_inspector_probe, "_run_inspector", fake_run)

    result = mcp_inspector_probe.verify(
        tmp_path / "node",
        tmp_path / "cli.js",
        "http://127.0.0.1:8090/mcp",
        "token",
        query,
    )

    search_arguments = {name: arguments for name, arguments in calls if name in {"search_entities", "search_evidence"}}
    entity_arguments = search_arguments["search_entities"]
    evidence_arguments = search_arguments["search_evidence"]
    assert entity_arguments is not None
    assert evidence_arguments is not None
    assert entity_arguments["query"] == query
    assert evidence_arguments["query"] == query
    assert result["query_sha256"] == "016d3d261011600d1599fe512854b10a04f7297aa88756ec2c66cbf8f7767be8"
    assert result["billed_calls"] == 5
    assert result["pagination_pages"] == 2
    assert result["pagination_unique_entities"] == 2
    assert result["invalid_cursor_rejected"] is True
    assert result["recovered_after_error"] is True
    assert result["competitive_program_items"] == 1


@pytest.mark.parametrize("query", ["ab", "x" * 121, "valid\ninvalid", "valid\x7finvalid"])
def test_verify_rejects_invalid_acceptance_query(query: str) -> None:
    with pytest.raises(RuntimeError, match="3-120 printable"):
        mcp_inspector_probe.verify(Path("node"), Path("cli"), "http://localhost/mcp", "token", query)
