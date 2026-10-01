from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN
from scripts.release.contracts.mcp import (
    MCP_ASYNC_TASK_ASSERTIONS,
    MCP_ASYNC_TASK_CLIENT_FIELDS,
    MCP_ASYNC_TASK_FIELDS,
    MCP_ASYNC_TASK_REPORT,
    MCP_ASYNC_TASK_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_mcp_async_task_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP async task attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_ASYNC_TASK_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("MCP async task evidence requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / MCP_ASYNC_TASK_REPORT, "MCP async task report")
    if (
        set(report) != MCP_ASYNC_TASK_FIELDS
        or report.get("schema") != MCP_ASYNC_TASK_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-postgresql-object-store"
        or report.get("production_claim") is not False
        or report.get("controlled_fixture") is not True
        or report.get("credentials_recorded") is not False
        or report.get("protocol_version") != "2025-11-25"
        or report.get("client_count") != 2
        or report.get("same_authority_record_set") is not True
    ):
        raise ReleaseEvidenceError("MCP async task report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP async task statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "MCP async task generated_at")
    maximum_age_hours = policy.categories["mcp_async_tasks"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("MCP async task report is outside the allowed evidence window")

    clients = report.get("clients")
    if not isinstance(clients, list) or len(clients) != 2 or not all(isinstance(item, dict) for item in clients):
        raise ReleaseEvidenceError("MCP async task client inventory is invalid")
    expected_clients = {"MCP Inspector", "Python MCP SDK"}
    client_names = {item.get("client") for item in clients}
    if client_names != expected_clients:
        raise ReleaseEvidenceError("MCP async task evidence omitted an independent client")
    authority_digests: set[str] = set()
    for client in clients:
        if (
            set(client) != MCP_ASYNC_TASK_CLIENT_FIELDS
            or client.get("status") != "passed"
            or client.get("tasks_created") != 2
            or client.get("completed_tasks") != 1
            or client.get("cancelled_tasks") != 1
            or client.get("result_pages") != 2
            or client.get("unique_records") != 2
            or client.get("tampered_cursor_rejected") is not True
            or client.get("recovered_after_error") is not True
            or client.get("settlement_created") is not True
            or client.get("credentials_recorded") is not False
        ):
            raise ReleaseEvidenceError("MCP async task client workflow is incomplete")
        version = client.get("client_version")
        if not isinstance(version, str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
            raise ReleaseEvidenceError("MCP async task client version is invalid")
        for field in ("entity_ids_sha256", "manifest_sha256"):
            value = client.get(field)
            if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
                raise ReleaseEvidenceError("MCP async task client digest is invalid")
        authority_digests.add(client["entity_ids_sha256"])
    if len(authority_digests) != 1:
        raise ReleaseEvidenceError("MCP async task clients returned different authority record sets")

    if report.get("database") != {
        "tasks": 4,
        "completed_tasks": 2,
        "cancelled_tasks": 2,
        "settlements": 2,
        "signed_completed_tasks": 2,
        "active_reservations_after": 0,
    }:
        raise ReleaseEvidenceError("MCP async task accounting evidence is incomplete")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != MCP_ASYNC_TASK_ASSERTIONS
        or any(value is not True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("MCP async task assertions are incomplete")
    if report.get("cleanup") != {
        "api_stopped": True,
        "mcp_stopped": True,
        "database_dropped": True,
        "temporary_object_store_destroyed": True,
    }:
        raise ReleaseEvidenceError("MCP async task isolated runtime cleanup is incomplete")
