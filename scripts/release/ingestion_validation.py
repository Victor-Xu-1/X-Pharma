from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN, UUID_PATTERN
from scripts.release.contracts.ingestion import (
    AUTOMATIC_INGESTION_FIELDS,
    AUTOMATIC_INGESTION_REPORT,
    AUTOMATIC_INGESTION_SCHEMA,
    INGESTION_COUNTER_FIELDS,
    INGESTION_GOVERNANCE_FIELDS,
    INGESTION_PILOT_FIELDS,
    INGESTION_PILOT_REPORT,
    INGESTION_PILOT_SCHEMA,
    INGESTION_READINESS_CONNECTOR_IDS,
    INGESTION_READINESS_EVIDENCE_SCHEMA,
    INGESTION_READINESS_REPORT,
    INGESTION_READINESS_SCHEMA,
    INGESTION_READINESS_SERVICES,
    INGESTION_SOURCE_CONNECTORS,
    INGESTION_SOURCE_FIELDS,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_ingestion_readiness_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("ingestion readiness attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == INGESTION_READINESS_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("ingestion readiness requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / INGESTION_READINESS_REPORT, "ingestion readiness report")
    readiness = report.get("readiness")
    services = report.get("services")
    if (
        report.get("schema") != INGESTION_READINESS_EVIDENCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("real_source_automatic_ingestion_verified") is not False
        or not isinstance(readiness, dict)
        or not isinstance(services, list)
    ):
        raise ReleaseEvidenceError("ingestion readiness report has an invalid scope or status")
    service_names = {service.get("service") for service in services if isinstance(service, dict)}
    if (
        service_names != INGESTION_READINESS_SERVICES
        or len(services) != len(INGESTION_READINESS_SERVICES)
        or any(
            not isinstance(service, dict)
            or service.get("running") is not True
            or service.get("health") not in {"healthy", "not-configured"}
            for service in services
        )
    ):
        raise ReleaseEvidenceError("ingestion readiness required services are incomplete")
    inventory = readiness.get("inventory")
    connectors = readiness.get("connectors")
    runtime = readiness.get("runtime")
    checks = runtime.get("checks") if isinstance(runtime, dict) else None
    connector_ids = (
        {connector.get("connector_id") for connector in connectors if isinstance(connector, dict)}
        if isinstance(connectors, list)
        else set()
    )
    if (
        readiness.get("schema") != INGESTION_READINESS_SCHEMA
        or readiness.get("schema_version") != 1
        or readiness.get("status") not in {"ready_for_source_registration", "ready_for_ingestion"}
        or readiness.get("production_claim") is not False
        or readiness.get("real_source_automatic_ingestion_verified") is not False
        or not isinstance(inventory, dict)
        or inventory.get("blocked_source_count") != 0
        or not isinstance(connectors, list)
        or len(connectors) != len(INGESTION_READINESS_CONNECTOR_IDS)
        or connector_ids != INGESTION_READINESS_CONNECTOR_IDS
        or any(
            not isinstance(connector, dict)
            or connector.get("incremental") is not True
            or connector.get("replayable") is not True
            or connector.get("immutable_snapshot_required") is not True
            for connector in connectors
        )
        or not isinstance(checks, list)
        or any(not isinstance(check, dict) or check.get("status") != "pass" for check in checks)
    ):
        raise ReleaseEvidenceError("ingestion readiness platform controls are incomplete")
    statement_time = _parse_timestamp(statement.get("generated_at"), "ingestion readiness statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "ingestion readiness generated_at")
    maximum_age_hours = policy.categories["ingestion_readiness"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("ingestion readiness report is outside the allowed evidence window")


def _ingestion_nonnegative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_ingestion_source_inventory(
    inventory: object,
    *,
    source_id: str,
    source_type: str,
) -> None:
    if not isinstance(inventory, dict) or set(inventory) != INGESTION_SOURCE_FIELDS:
        raise ReleaseEvidenceError("pilot ingestion source inventory is invalid")
    numeric_fields = ("discovered", "stable", "oversized", "excluded", "error_count", "configuration_error_count")
    if (
        inventory.get("schema_version") != 1
        or inventory.get("source_id") != source_id
        or inventory.get("source_type") != source_type
        or inventory.get("connector_id") != INGESTION_SOURCE_CONNECTORS[source_type]
        or not isinstance(inventory.get("authoritative_inventory"), bool)
        or any(not _ingestion_nonnegative_integer(inventory.get(name)) for name in numeric_fields)
        or inventory.get("oversized") != 0
        or inventory.get("error_count") != 0
        or inventory.get("configuration_error_count") != 0
        or inventory.get("discovered", 0) < 1
        or inventory.get("stable", 0) < 1
        or inventory.get("stable", 0) > inventory.get("discovered", 0)
    ):
        raise ReleaseEvidenceError("pilot ingestion source inventory is incomplete or unhealthy")


def _validate_ingestion_counters(counters: object, *, idempotent: bool) -> None:
    if (
        not isinstance(counters, dict)
        or set(counters) != INGESTION_COUNTER_FIELDS
        or any(not _ingestion_nonnegative_integer(counters.get(name)) for name in INGESTION_COUNTER_FIELDS)
        or counters.get("failed") != 0
        or counters.get("unstable") != 0
        or (idempotent and counters.get("discovered") != 0)
        or (idempotent and counters.get("unchanged", 0) < 1)
    ):
        raise ReleaseEvidenceError("pilot ingestion run counters are invalid or not idempotent")


def _validate_ingestion_versions(versions: object, *, idempotence_field: bool) -> tuple[int, int]:
    expected_fields = {
        "current",
        "traceable",
        "malware_scanned",
        "processed",
        "governable",
        "governed",
        "projected",
        "failed",
    }
    if idempotence_field:
        expected_fields.add("idempotent_second_scan")
    if not isinstance(versions, dict) or set(versions) != expected_fields:
        raise ReleaseEvidenceError("pilot ingestion version inventory is invalid")
    current = versions.get("current")
    governable = versions.get("governable")
    if (
        not isinstance(current, int)
        or isinstance(current, bool)
        or current < 1
        or not isinstance(governable, int)
        or isinstance(governable, bool)
        or not 1 <= governable <= current
        or any(versions.get(name) != current for name in ("traceable", "malware_scanned", "processed"))
        or any(versions.get(name) != governable for name in ("governed", "projected"))
        or versions.get("failed") != 0
        or (idempotence_field and versions.get("idempotent_second_scan") is not True)
    ):
        raise ReleaseEvidenceError("pilot ingestion versions are not fully governed and traceable")
    return current, governable


def _validate_ingestion_governance(governance: object, *, governable_versions: int) -> None:
    if not isinstance(governance, dict) or set(governance) != INGESTION_GOVERNANCE_FIELDS:
        raise ReleaseEvidenceError("pilot ingestion AI governance accounting is invalid")
    configured_model = governance.get("configured_model")
    numeric_fields = INGESTION_GOVERNANCE_FIELDS - {"configured_model"}
    if (
        not isinstance(configured_model, str)
        or not 1 <= len(configured_model) <= 160
        or any(not _ingestion_nonnegative_integer(governance.get(name)) for name in numeric_fields)
    ):
        raise ReleaseEvidenceError("pilot ingestion AI governance metadata is invalid")
    extraction_runs = governance["extraction_runs"]
    staged_facts = governance["staged_facts"]
    if (
        extraction_runs < governable_versions
        or governance["successful_extraction_runs"] != extraction_runs
        or governance["configured_model_runs"] != extraction_runs
        or governance["failed_extraction_runs"] != 0
        or governance["input_tokens"] < 1
        or governance["output_tokens"] < 1
        or governance["segments"] < 1
        or governance["accounted_segments"] != governance["segments"]
        or staged_facts < 1
        or not 1 <= governance["quote_verified_facts"] <= staged_facts
    ):
        raise ReleaseEvidenceError("pilot ingestion AI governance is incomplete or unaccounted")


def _validate_ingestion_search(search: object) -> None:
    cluster = search.get("cluster") if isinstance(search, dict) else None
    deliveries = search.get("deliveries") if isinstance(search, dict) else None
    if (
        not isinstance(search, dict)
        or set(search) != {"cluster", "deliveries"}
        or not isinstance(cluster, dict)
        or set(cluster) != {"aliases", "available", "cluster_name", "cluster_status", "error", "version"}
        or cluster.get("available") is not True
        or cluster.get("cluster_name") != "pharma-search"
        or cluster.get("cluster_status") != "green"
        or cluster.get("error") is not None
        or cluster.get("version") != "3.7.0"
        or not isinstance(cluster.get("aliases"), dict)
        or set(cluster["aliases"]) != {"entities", "evidence", "knowledge"}
        or not isinstance(deliveries, dict)
        or set(deliveries) != {"dead", "processing", "retry", "succeeded"}
        or any(deliveries.get(name) != 0 for name in ("dead", "processing", "retry"))
        or not _ingestion_nonnegative_integer(deliveries.get("succeeded"))
    ):
        raise ReleaseEvidenceError("pilot ingestion OpenSearch projection evidence is invalid")
    for name, aliases in cluster["aliases"].items():
        if (
            not isinstance(aliases, list)
            or len(aliases) != 1
            or not isinstance(aliases[0], str)
            or not aliases[0].startswith(f"pharma-{name}-v2-")
        ):
            raise ReleaseEvidenceError(f"pilot ingestion OpenSearch alias is invalid: {name}")


def _validate_ingestion_pilot_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    expected_reports = {INGESTION_PILOT_REPORT, AUTOMATIC_INGESTION_REPORT}
    attachment_paths = (
        [item.get("path") for item in raw_attachments if isinstance(item, dict)]
        if isinstance(raw_attachments, list)
        else []
    )
    log_attachment = statement.get("log_attachment")
    expected_attachments = set(expected_reports)
    if log_attachment is not None:
        if not isinstance(log_attachment, str):
            raise ReleaseEvidenceError("pilot ingestion capture log attachment is invalid")
        expected_attachments.add(log_attachment)
    if (
        not isinstance(raw_attachments, list)
        or len(attachment_paths) != len(expected_attachments)
        or set(attachment_paths) != expected_attachments
    ):
        raise ReleaseEvidenceError("pilot ingestion requires exactly two governed report attachments")
    manual = _load_json_object(statement_path.parent / INGESTION_PILOT_REPORT, "pilot ingestion report")
    automatic = _load_json_object(
        statement_path.parent / AUTOMATIC_INGESTION_REPORT,
        "automatic ingestion report",
    )
    if (
        set(manual) != INGESTION_PILOT_FIELDS
        or manual.get("schema") != INGESTION_PILOT_SCHEMA
        or manual.get("schema_version") != 2
        or manual.get("status") != "passed"
        or manual.get("environment") != "local-wsl"
        or manual.get("production_claim") is not False
        or manual.get("source_content_created_by_test") is not False
        or set(automatic) != AUTOMATIC_INGESTION_FIELDS
        or automatic.get("schema") != AUTOMATIC_INGESTION_SCHEMA
        or automatic.get("schema_version") != 4
        or automatic.get("status") != "passed"
        or automatic.get("environment") != "local-wsl"
        or automatic.get("production_claim") is not False
    ):
        raise ReleaseEvidenceError("pilot ingestion reports have an invalid schema, scope or status")
    source_id = manual.get("source_id")
    source_type = manual.get("source_type")
    dataset_key = manual.get("dataset_key")
    license_id = manual.get("license_id")
    if (
        not isinstance(source_id, str)
        or UUID_PATTERN.fullmatch(source_id) is None
        or source_type not in INGESTION_SOURCE_CONNECTORS
        or not isinstance(dataset_key, str)
        or re.fullmatch(r"[A-Za-z0-9._-]{1,80}", dataset_key) is None
        or not isinstance(license_id, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,119}", license_id) is None
        or any(
            automatic.get(name) != manual.get(name)
            for name in ("source_id", "source_type", "dataset_key", "license_id")
        )
    ):
        raise ReleaseEvidenceError("pilot ingestion reports do not identify the same licensed real source")
    _validate_ingestion_source_inventory(manual.get("source_files"), source_id=source_id, source_type=source_type)
    manual_versions, manual_governable = _validate_ingestion_versions(manual.get("versions"), idempotence_field=True)
    _validate_ingestion_governance(manual.get("governance"), governable_versions=manual_governable)
    runs = manual.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise ReleaseEvidenceError("pilot ingestion report must contain exactly two manual acceptance runs")
    run_ids: set[str] = set()
    for index, run in enumerate(runs):
        run_id = run.get("id") if isinstance(run, dict) else None
        if (
            not isinstance(run, dict)
            or set(run) != {"id", "state", "counters"}
            or not isinstance(run_id, str)
            or UUID_PATTERN.fullmatch(run_id) is None
            or run_id in run_ids
            or run.get("state") != "SUCCEEDED"
        ):
            raise ReleaseEvidenceError("pilot ingestion manual run identity or state is invalid")
        _validate_ingestion_counters(run.get("counters"), idempotent=index == 1)
        run_ids.add(run_id)
    _validate_ingestion_search(manual.get("search"))

    trigger = automatic.get("trigger")
    if (
        not isinstance(trigger, dict)
        or set(trigger)
        != {
            "mode",
            "outcome",
            "manual_trigger_used",
            "source_schedule_mutated",
            "source_content_created_by_test",
            "scan_interval_seconds",
            "initial_due_in_seconds",
            "observed_elapsed_seconds",
            "baseline_versions",
            "observed_versions",
            "new_versions",
            "baseline_run_id",
            "baseline_run_created_at",
            "observed_run_created_at",
            "policy_sha256",
            "baseline_policy_runs",
            "observed_policy_runs",
        }
        or trigger.get("mode") != "temporal-scheduler"
        or trigger.get("outcome") not in {"new_version", "policy_reprocess", "unchanged"}
        or trigger.get("manual_trigger_used") is not False
        or trigger.get("source_schedule_mutated") is not False
        or trigger.get("source_content_created_by_test") is not False
        or not isinstance(trigger.get("scan_interval_seconds"), int)
        or isinstance(trigger.get("scan_interval_seconds"), bool)
        or not 10 <= trigger["scan_interval_seconds"] <= 86_400
        or not _ingestion_nonnegative_integer(trigger.get("initial_due_in_seconds"))
        or trigger["initial_due_in_seconds"] > 86_400
        or not _ingestion_nonnegative_integer(trigger.get("observed_elapsed_seconds"))
        or trigger["observed_elapsed_seconds"] > 86_400
        or not _ingestion_nonnegative_integer(trigger.get("baseline_versions"))
        or not _ingestion_nonnegative_integer(trigger.get("observed_versions"))
        or not _ingestion_nonnegative_integer(trigger.get("new_versions"))
        or trigger["observed_versions"] - trigger["baseline_versions"] != trigger["new_versions"]
        or not isinstance(trigger.get("baseline_run_id"), str)
        or UUID_PATTERN.fullmatch(trigger["baseline_run_id"]) is None
        or not isinstance(trigger.get("policy_sha256"), str)
        or SHA256_PATTERN.fullmatch(trigger["policy_sha256"]) is None
        or not _ingestion_nonnegative_integer(trigger.get("baseline_policy_runs"))
        or not _ingestion_nonnegative_integer(trigger.get("observed_policy_runs"))
        or trigger["observed_policy_runs"] < trigger["baseline_policy_runs"]
    ):
        raise ReleaseEvidenceError("automatic ingestion was not observed through an unchanged Temporal schedule")
    baseline_run_time = _parse_timestamp(
        trigger.get("baseline_run_created_at"), "automatic ingestion baseline run created_at"
    )
    observed_run_time = _parse_timestamp(
        trigger.get("observed_run_created_at"), "automatic ingestion observed run created_at"
    )
    workflow = automatic.get("workflow")
    workflow_id = workflow.get("workflow_id") if isinstance(workflow, dict) else None
    automatic_run_id = workflow.get("run_id") if isinstance(workflow, dict) else None
    if (
        not isinstance(workflow, dict)
        or set(workflow) != {"run_id", "workflow_id", "state", "counters"}
        or not isinstance(automatic_run_id, str)
        or UUID_PATTERN.fullmatch(automatic_run_id) is None
        or automatic_run_id in run_ids
        or not isinstance(workflow_id, str)
        or not workflow_id.startswith(f"source-ingest-{source_id}-")
        or workflow.get("state") != "SUCCEEDED"
    ):
        raise ReleaseEvidenceError("automatic ingestion workflow identity or state is invalid")
    if (observed_run_time, automatic_run_id) <= (baseline_run_time, trigger["baseline_run_id"]):
        raise ReleaseEvidenceError("automatic ingestion workflow is not newer than the captured scheduler watermark")
    unchanged_outcome = trigger["outcome"] == "unchanged"
    _validate_ingestion_counters(workflow.get("counters"), idempotent=unchanged_outcome)
    counters = workflow.get("counters")
    if not isinstance(counters, dict):
        raise ReleaseEvidenceError("automatic ingestion counters are invalid")
    if unchanged_outcome:
        if (
            trigger["new_versions"] != 0
            or trigger["observed_policy_runs"] != trigger["baseline_policy_runs"]
            or trigger["observed_versions"] < 1
            or counters.get("discovered") != 0
            or counters.get("unchanged", 0) < 1
        ):
            raise ReleaseEvidenceError("automatic ingestion did not prove unchanged-source idempotence")
    elif trigger["outcome"] == "policy_reprocess":
        if (
            trigger["new_versions"] != 0
            or trigger["observed_policy_runs"] <= trigger["baseline_policy_runs"]
            or counters.get("discovered", 0) < 1
        ):
            raise ReleaseEvidenceError("automatic ingestion did not prove current-policy source reprocessing")
    elif (
        trigger["new_versions"] < 1
        or trigger["observed_policy_runs"] <= trigger["baseline_policy_runs"]
        or counters.get("discovered", 0) < 1
    ):
        raise ReleaseEvidenceError("automatic ingestion did not discover and govern a new source version")
    automatic_versions, automatic_governable = _validate_ingestion_versions(
        automatic.get("versions"), idempotence_field=False
    )
    _validate_ingestion_governance(automatic.get("governance"), governable_versions=automatic_governable)
    if automatic_versions != manual_versions or automatic_governable != manual_governable:
        raise ReleaseEvidenceError("manual idempotence scans changed the automatically governed source inventory")
    if automatic.get("governance") != manual.get("governance"):
        raise ReleaseEvidenceError("manual idempotence scans changed AI governance accounting")
    _validate_ingestion_search(automatic.get("search"))

    statement_time = _parse_timestamp(statement.get("generated_at"), "pilot ingestion statement generated_at")
    manual_time = _parse_timestamp(manual.get("generated_at"), "pilot ingestion generated_at")
    automatic_time = _parse_timestamp(automatic.get("generated_at"), "automatic ingestion generated_at")
    maximum_age_hours = policy.categories["ingestion_pilot"] if policy is not None else 168
    if (
        observed_run_time > automatic_time
        or automatic_time > manual_time
        or manual_time > statement_time + timedelta(minutes=5)
        or statement_time - automatic_time > timedelta(hours=maximum_age_hours)
    ):
        raise ReleaseEvidenceError("pilot ingestion reports are outside the allowed evidence window or order")
