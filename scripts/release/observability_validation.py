from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.platform import (
    OBSERVABILITY_ACCEPTANCE_FIELDS,
    OBSERVABILITY_ACCEPTANCE_REPORT,
    OBSERVABILITY_ACCEPTANCE_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_observability_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("observability acceptance attachments are invalid")
    reports = [
        item
        for item in raw_attachments
        if isinstance(item, dict) and item.get("path") == OBSERVABILITY_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("observability acceptance requires exactly one report.json attachment")
    report = _load_json_object(
        statement_path.parent / OBSERVABILITY_ACCEPTANCE_REPORT,
        "observability acceptance report",
    )
    if (
        set(report) != OBSERVABILITY_ACCEPTANCE_FIELDS
        or report.get("schema") != OBSERVABILITY_ACCEPTANCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("collector_protocol") != "OTLP-gRPC"
    ):
        raise ReleaseEvidenceError("observability acceptance report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "observability statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "observability generated_at")
    maximum_age_hours = policy.categories["operations_contract"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("observability acceptance report is outside the allowed evidence window")
    if report.get("observed_metrics") != [
        "pharma.mcp.commercial.calls",
        "pharma.mcp.commercial.duration",
    ]:
        raise ReleaseEvidenceError("observability commercial metric inventory is incomplete")
    if report.get("contract") != {"services": 9, "objectives": 9, "alerts": 9}:
        raise ReleaseEvidenceError("observability operations contract inventory is incomplete")
    probe = report.get("commercial_probe")
    if (
        not isinstance(probe, dict)
        or set(probe) != {"requests", "unique_settlements", "active_reservations_after", "p95_ms"}
        or probe.get("requests") != 4
        or probe.get("unique_settlements") != 4
        or probe.get("active_reservations_after") != 0
        or not isinstance(probe.get("p95_ms"), int | float)
        or isinstance(probe.get("p95_ms"), bool)
        or not 0 <= probe["p95_ms"] <= 2000
    ):
        raise ReleaseEvidenceError("observability billed OTLP probe evidence is incomplete")
