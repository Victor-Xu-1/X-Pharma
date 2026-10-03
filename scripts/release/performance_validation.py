from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import UNITS_PATTERN
from scripts.release.contracts.security import (
    PERFORMANCE_BASELINE_ASSERTIONS,
    PERFORMANCE_BASELINE_REPORT,
    PERFORMANCE_BASELINE_SCHEMA,
    PERFORMANCE_RACE_ASSERTIONS,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_performance_baseline_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("performance baseline attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == PERFORMANCE_BASELINE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("performance baseline requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / PERFORMANCE_BASELINE_REPORT, "performance baseline report")
    if (
        report.get("schema") != PERFORMANCE_BASELINE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("production_claim") is not False
        or report.get("environment_kind") != "local-controlled-baseline"
        or report.get("credentials_recorded") is not False
        or report.get("temporary_users_after") != 0
        or report.get("temporary_human_role") != "viewer"
    ):
        raise ReleaseEvidenceError("performance baseline report has an invalid scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "performance baseline statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "performance baseline generated_at")
    maximum_age_hours = policy.categories["performance_baseline"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("performance baseline is outside the allowed evidence window")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != PERFORMANCE_BASELINE_ASSERTIONS
        or not all(value is True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("performance baseline did not pass every mixed-load assertion")
    phases = report.get("phases")
    if not isinstance(phases, list) or len(phases) != 2:
        raise ReleaseEvidenceError("performance baseline phase inventory is incomplete")
    by_name = {phase.get("name"): phase for phase in phases if isinstance(phase, dict)}
    if set(by_name) != {"sustained", "peak"}:
        raise ReleaseEvidenceError("performance baseline phase inventory is incomplete")
    for name, phase in by_name.items():
        requested = phase.get("requested")
        completed = phase.get("completed")
        concurrency = phase.get("concurrency")
        web_completed = phase.get("web_completed")
        mcp_completed = phase.get("mcp_completed")
        if (
            not isinstance(requested, int)
            or isinstance(requested, bool)
            or requested < 2
            or completed != requested
            or phase.get("failed") != 0
            or phase.get("errors") != []
            or not isinstance(concurrency, int)
            or isinstance(concurrency, bool)
            or concurrency < 2
            or not isinstance(web_completed, int)
            or isinstance(web_completed, bool)
            or web_completed < 1
            or not isinstance(mcp_completed, int)
            or isinstance(mcp_completed, bool)
            or mcp_completed < 1
            or web_completed + mcp_completed != completed
            or phase.get("unique_mcp_settlements") != mcp_completed
        ):
            raise ReleaseEvidenceError(f"performance baseline {name} phase is incomplete")
    if by_name["peak"]["concurrency"] <= by_name["sustained"]["concurrency"]:
        raise ReleaseEvidenceError("performance baseline peak does not exceed sustained concurrency")
    aggregate = report.get("aggregate")
    if not isinstance(aggregate, dict):
        raise ReleaseEvidenceError("performance baseline aggregate is invalid")
    mcp_completed = aggregate.get("mcp_completed")
    expected_web_completed = sum(int(phase["web_completed"]) for phase in by_name.values())
    expected_mcp_completed = sum(int(phase["mcp_completed"]) for phase in by_name.values())
    charged_units = aggregate.get("charged_units_delta")
    consumed_units = aggregate.get("consumed_units_delta")
    thresholds = report.get("thresholds")
    web_latency = aggregate.get("web_latency_ms")
    mcp_latency = aggregate.get("mcp_latency_ms")
    if (
        not isinstance(mcp_completed, int)
        or isinstance(mcp_completed, bool)
        or mcp_completed < 1
        or aggregate.get("web_completed") != expected_web_completed
        or mcp_completed != expected_mcp_completed
        or aggregate.get("settlement_delta") != mcp_completed
        or not isinstance(charged_units, str)
        or UNITS_PATTERN.fullmatch(charged_units) is None
        or charged_units == "0.00000000"
        or charged_units != consumed_units
        or aggregate.get("active_reservations_after_load") != 0
        or aggregate.get("active_reservations_final") != 0
        or not isinstance(thresholds, dict)
        or not isinstance(web_latency, dict)
        or not isinstance(mcp_latency, dict)
        or not isinstance(thresholds.get("web_p95_ms"), int | float)
        or isinstance(thresholds.get("web_p95_ms"), bool)
        or not isinstance(thresholds.get("mcp_p95_ms"), int | float)
        or isinstance(thresholds.get("mcp_p95_ms"), bool)
        or not isinstance(web_latency.get("p95"), int | float)
        or isinstance(web_latency.get("p95"), bool)
        or not isinstance(mcp_latency.get("p95"), int | float)
        or isinstance(mcp_latency.get("p95"), bool)
        or web_latency["p95"] > thresholds["web_p95_ms"]
        or mcp_latency["p95"] > thresholds["mcp_p95_ms"]
    ):
        raise ReleaseEvidenceError("performance baseline metering aggregate is inconsistent")
    race = report.get("concurrent_idempotency")
    if not isinstance(race, dict):
        raise ReleaseEvidenceError("performance baseline concurrent idempotency evidence is incomplete")
    race_assertions = race.get("assertions")
    if (
        not isinstance(race_assertions, dict)
        or set(race_assertions) != PERFORMANCE_RACE_ASSERTIONS
        or not all(value is True for value in race_assertions.values())
        or race.get("settlement_delta") != 1
        or race.get("unique_settlements") != 1
        or race.get("active_reservations_after") != 0
    ):
        raise ReleaseEvidenceError("performance baseline concurrent idempotency evidence is incomplete")
    failure = report.get("failure_injection")
    failure_assertions = failure.get("assertions") if isinstance(failure, dict) else None
    if (
        not isinstance(failure_assertions, dict)
        or not failure_assertions
        or not all(value is True for value in failure_assertions.values())
    ):
        raise ReleaseEvidenceError("performance baseline failure injection evidence is incomplete")
    coverage = report.get("coverage")
    gaps = report.get("production_gaps")
    if (
        not isinstance(coverage, dict)
        or coverage.get("long_running") is not False
        or coverage.get("target_infrastructure_faults") is not False
        or coverage.get("production_approvals") is not False
        or not isinstance(gaps, list)
        or len(gaps) < 3
        or not all(isinstance(gap, str) and gap for gap in gaps)
    ):
        raise ReleaseEvidenceError("performance baseline does not preserve its production boundary")
