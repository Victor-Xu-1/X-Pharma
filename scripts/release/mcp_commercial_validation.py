from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import UNITS_PATTERN, UUID_PATTERN
from scripts.release.contracts.mcp import (
    MCP_COMMERCIAL_ASSERTIONS,
    MCP_COMMERCIAL_FIELDS,
    MCP_COMMERCIAL_REPORT,
    MCP_COMMERCIAL_RESILIENCE_ASSERTIONS,
    MCP_COMMERCIAL_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_mcp_commercial_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP commercial attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_COMMERCIAL_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("MCP commercial evidence requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / MCP_COMMERCIAL_REPORT, "MCP commercial report")
    if (
        set(report) != MCP_COMMERCIAL_FIELDS
        or report.get("schema") != MCP_COMMERCIAL_SCHEMA
        or report.get("schema_version") != "2.0"
        or report.get("status") != "passed"
        or report.get("environment") != "local-or-ci-controlled-baseline"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("protocol_version") != "2025-11-25"
    ):
        raise ReleaseEvidenceError("MCP commercial report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP commercial statement generated_at")
    started_at = _parse_timestamp(report.get("started_at"), "MCP commercial started_at")
    finished_at = _parse_timestamp(report.get("finished_at"), "MCP commercial finished_at")
    maximum_age_hours = policy.categories["mcp_commercial"] if policy is not None else 168
    if (
        started_at > finished_at
        or finished_at > statement_time + timedelta(minutes=5)
        or statement_time - finished_at > timedelta(hours=maximum_age_hours)
    ):
        raise ReleaseEvidenceError("MCP commercial report is outside the allowed evidence window")
    assertions = report.get("assertions")
    if (
        not isinstance(assertions, dict)
        or set(assertions) != MCP_COMMERCIAL_ASSERTIONS
        or not all(value is True for value in assertions.values())
    ):
        raise ReleaseEvidenceError("MCP commercial baseline assertions are incomplete")
    requests = report.get("requests")
    if not isinstance(requests, dict) or set(requests) != {
        "requested",
        "completed",
        "failed",
        "concurrency",
        "duration_seconds",
        "throughput_rps",
    }:
        raise ReleaseEvidenceError("MCP commercial request inventory is invalid")
    requested = requests.get("requested")
    concurrency = requests.get("concurrency")
    duration = requests.get("duration_seconds")
    throughput = requests.get("throughput_rps")
    if (
        not isinstance(requested, int)
        or isinstance(requested, bool)
        or not 1 <= requested <= 1000
        or requests.get("completed") != requested
        or requests.get("failed") != 0
        or not isinstance(concurrency, int)
        or isinstance(concurrency, bool)
        or not 1 <= concurrency <= min(requested, 50)
        or not isinstance(duration, int | float)
        or isinstance(duration, bool)
        or not 0 < duration <= 600
        or not isinstance(throughput, int | float)
        or isinstance(throughput, bool)
        or throughput <= 0
    ):
        raise ReleaseEvidenceError("MCP commercial request results are incomplete")
    latency = report.get("latency_ms")
    if not isinstance(latency, dict) or set(latency) != {"minimum", "p50", "p95", "p99", "maximum"}:
        raise ReleaseEvidenceError("MCP commercial latency inventory is invalid")
    latency_names = ("minimum", "p50", "p95", "p99", "maximum")
    raw_latency_values = [latency.get(name) for name in latency_names]
    if any(not isinstance(value, int | float) or isinstance(value, bool) or value < 0 for value in raw_latency_values):
        raise ReleaseEvidenceError("MCP commercial latency contract failed")
    latency_values = [float(latency[name]) for name in latency_names]
    if latency_values != sorted(latency_values) or latency_values[2] > 2000:
        raise ReleaseEvidenceError("MCP commercial latency contract failed")
    billing = report.get("billing")
    if not isinstance(billing, dict) or set(billing) != {
        "settlements_before",
        "settlements_after",
        "settlement_delta",
        "unique_settlement_ids",
        "active_reservations_after",
    }:
        raise ReleaseEvidenceError("MCP commercial billing inventory is invalid")
    if (
        not isinstance(billing.get("settlements_before"), int)
        or isinstance(billing.get("settlements_before"), bool)
        or not isinstance(billing.get("settlements_after"), int)
        or isinstance(billing.get("settlements_after"), bool)
        or billing["settlements_after"] - billing["settlements_before"] != billing.get("settlement_delta")
        or not isinstance(billing.get("settlement_delta"), int)
        or isinstance(billing.get("settlement_delta"), bool)
        or billing["settlement_delta"] < requested
        or billing.get("unique_settlement_ids") != requested
        or billing.get("active_reservations_after") != 0
    ):
        raise ReleaseEvidenceError("MCP commercial settlement evidence is inconsistent")
    if report.get("errors") != []:
        raise ReleaseEvidenceError("MCP commercial report contains request failures")
    resilience = report.get("resilience")
    if not isinstance(resilience, dict) or set(resilience) != {
        "idempotency",
        "failure_release",
        "cancellation",
        "timeout",
        "reconciliation",
        "assertions",
    }:
        raise ReleaseEvidenceError("MCP commercial resilience inventory is invalid")
    resilience_assertions = resilience.get("assertions")
    if (
        not isinstance(resilience_assertions, dict)
        or set(resilience_assertions) != MCP_COMMERCIAL_RESILIENCE_ASSERTIONS
        or not all(value is True for value in resilience_assertions.values())
    ):
        raise ReleaseEvidenceError("MCP commercial resilience assertions are incomplete")
    idempotency = resilience.get("idempotency")
    failure_release = resilience.get("failure_release")
    reconciliation = resilience.get("reconciliation")
    if (
        idempotency != {"same_settlement": True, "replay_flag": True, "argument_conflict_rejected": True}
        or not isinstance(failure_release, dict)
        or failure_release
        != {
            "domain_failure_rejected": True,
            "budget_failure_rejected": True,
            "active_reservations_after": 0,
            "reserved_units_after": "0E-8",
        }
        or not isinstance(reconciliation, dict)
        or set(reconciliation)
        != {"settlement_delta", "charged_units_delta", "consumed_units_delta", "balance_identity_holds"}
        or reconciliation.get("balance_identity_holds") is not True
        or not isinstance(reconciliation.get("settlement_delta"), int)
        or isinstance(reconciliation.get("settlement_delta"), bool)
        or not 1 <= reconciliation["settlement_delta"] <= 3
        or not isinstance(reconciliation.get("charged_units_delta"), str)
        or UNITS_PATTERN.fullmatch(reconciliation["charged_units_delta"]) is None
        or reconciliation.get("consumed_units_delta") != reconciliation["charged_units_delta"]
    ):
        raise ReleaseEvidenceError("MCP commercial durable accounting evidence is inconsistent")
    cancellation = resilience.get("cancellation")
    timeout = resilience.get("timeout")
    if (
        not isinstance(cancellation, dict)
        or cancellation.get("cancellation_requested") is not True
        or cancellation.get("outcome") not in {"cancelled", "settled"}
        or not isinstance(timeout, dict)
        or timeout.get("timeout_observed") is not True
        or timeout.get("outcome") not in {"released", "replay_settled"}
        or not isinstance(timeout.get("reserved_retries"), int)
        or isinstance(timeout.get("reserved_retries"), bool)
        or timeout["reserved_retries"] < 0
        or not isinstance(timeout.get("recovery_seconds"), int | float)
        or isinstance(timeout.get("recovery_seconds"), bool)
        or not 0 < timeout["recovery_seconds"] <= 10
    ):
        raise ReleaseEvidenceError("MCP commercial cancellation or timeout evidence is incomplete")
    if cancellation["outcome"] == "cancelled":
        if set(cancellation) != {"cancellation_requested", "outcome"}:
            raise ReleaseEvidenceError("MCP commercial cancellation evidence has invalid fields")
    elif (
        set(cancellation) != {"cancellation_requested", "outcome", "settlement_id"}
        or not isinstance(cancellation.get("settlement_id"), str)
        or UUID_PATTERN.fullmatch(cancellation["settlement_id"]) is None
    ):
        raise ReleaseEvidenceError("MCP commercial settled cancellation evidence is invalid")
    if timeout["outcome"] == "released":
        if (
            set(timeout)
            != {"timeout_observed", "outcome", "replay_rejected_as_released", "reserved_retries", "recovery_seconds"}
            or timeout.get("replay_rejected_as_released") is not True
        ):
            raise ReleaseEvidenceError("MCP commercial released timeout evidence is invalid")
    elif (
        set(timeout)
        != {
            "timeout_observed",
            "outcome",
            "settlement_id",
            "same_settlement",
            "replay_flag",
            "reserved_retries",
            "recovery_seconds",
        }
        or not isinstance(timeout.get("settlement_id"), str)
        or UUID_PATTERN.fullmatch(timeout["settlement_id"]) is None
        or timeout.get("same_settlement") is not True
        or timeout.get("replay_flag") is not True
    ):
        raise ReleaseEvidenceError("MCP commercial settled timeout evidence is invalid")
