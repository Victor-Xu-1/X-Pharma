from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.release.anti_extraction_validation import _validate_anti_extraction_baseline_evidence
from scripts.release.backup_validation import _validate_backup_restore_evidence
from scripts.release.browser_validation import _validate_browser_acceptance_evidence
from scripts.release.contracts.core import ENVIRONMENT_ID_PATTERN
from scripts.release.contracts.mcp import (
    MCP_SENDER_CONSTRAINT_CHECKS,
    MCP_SENDER_CONSTRAINT_FIELDS,
    MCP_SENDER_CONSTRAINT_REPORT,
    MCP_SENDER_CONSTRAINT_SCHEMA,
)
from scripts.release.database_validation import _validate_database_acceptance_evidence
from scripts.release.entry_validation import _validate_entry_consistency_evidence
from scripts.release.ingestion_validation import (
    _validate_ingestion_pilot_evidence,
    _validate_ingestion_readiness_evidence,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.kubernetes_validation import _validate_kubernetes_evidence
from scripts.release.mcp_commercial_validation import _validate_mcp_commercial_evidence
from scripts.release.mcp_interop_validation import _validate_mcp_interoperability_evidence
from scripts.release.mcp_task_validation import _validate_mcp_async_task_evidence
from scripts.release.observability_validation import _validate_observability_acceptance_evidence
from scripts.release.ocr_validation import _validate_ocr_acceptance_evidence
from scripts.release.parser_validation import _validate_parser_sandbox_evidence
from scripts.release.performance_validation import _validate_performance_baseline_evidence
from scripts.release.production_validation import _validate_production_gate_evidence
from scripts.release.record_validation import _validate_record_consistency_evidence
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError
from scripts.release.runtime_validation import _validate_runtime_acceptance_evidence
from scripts.release.source_validation import _validate_clean_source_evidence
from scripts.release.topology_validation import _validate_production_topology_evidence


def _validate_specialized_evidence(
    statement_path: Path,
    category: str,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None = None,
) -> None:
    if category == "source_reproducibility":
        _validate_clean_source_evidence(statement_path, statement, policy=policy)
        return
    if category == "browser":
        _validate_browser_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "performance_baseline":
        _validate_performance_baseline_evidence(statement_path, statement, policy=policy)
        return
    if category == "ingestion_readiness":
        _validate_ingestion_readiness_evidence(statement_path, statement, policy=policy)
        return
    if category == "ingestion_pilot":
        _validate_ingestion_pilot_evidence(statement_path, statement, policy=policy)
        return
    if category == "record_consistency":
        _validate_record_consistency_evidence(statement_path, statement, policy=policy)
        return
    if category == "anti_extraction_baseline":
        _validate_anti_extraction_baseline_evidence(statement_path, statement, policy=policy)
        return
    if category == "backup_restore":
        _validate_backup_restore_evidence(statement_path, statement, policy=policy)
        return
    if category == "kubernetes":
        _validate_kubernetes_evidence(statement_path, statement, policy=policy)
        return
    if category == "entry_consistency":
        _validate_entry_consistency_evidence(statement_path, statement, policy=policy)
        return
    if category == "mcp_protocol":
        _validate_mcp_interoperability_evidence(statement_path, statement, policy=policy)
        return
    if category == "mcp_async_tasks":
        _validate_mcp_async_task_evidence(statement_path, statement, policy=policy)
        return
    if category == "mcp_commercial":
        _validate_mcp_commercial_evidence(statement_path, statement, policy=policy)
        return
    if category == "database":
        _validate_database_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "operations_contract":
        _validate_observability_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "parser_sandbox":
        _validate_parser_sandbox_evidence(statement_path, statement, policy=policy)
        return
    if category == "ocr":
        _validate_ocr_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if category == "runtime":
        _validate_runtime_acceptance_evidence(statement_path, statement, policy=policy)
        return
    if policy is not None and (contract := policy.production_contracts.get(category)) is not None:
        _validate_production_gate_evidence(
            statement_path,
            category,
            statement,
            contract=contract,
            maximum_age_hours=policy.categories[category],
        )
    if category == "production_topology":
        _validate_production_topology_evidence(statement_path, statement, policy=policy)
        return
    if category != "mcp_sender_constraint":
        return
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("MCP sender-constraint evidence attachments are invalid")
    report_metadata = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == MCP_SENDER_CONSTRAINT_REPORT
    ]
    if len(report_metadata) != 1:
        raise ReleaseEvidenceError(
            f"MCP sender-constraint evidence requires exactly one {MCP_SENDER_CONSTRAINT_REPORT} attachment"
        )
    report_path = statement_path.parent / MCP_SENDER_CONSTRAINT_REPORT
    report = _load_json_object(report_path, "MCP sender-constraint report")
    environment_id = report.get("environment_id")
    if (
        set(report) != MCP_SENDER_CONSTRAINT_FIELDS
        or report.get("schema") != MCP_SENDER_CONSTRAINT_SCHEMA
        or report.get("schema_version") != 2
        or report.get("status") != "passed"
        or report.get("environment_kind") not in {"preproduction", "production"}
        or not isinstance(environment_id, str)
        or ENVIRONMENT_ID_PATTERN.fullmatch(environment_id) is None
    ):
        raise ReleaseEvidenceError("MCP sender-constraint report is not approved environment evidence")
    environment_tokens = set(re.split(r"[^a-z0-9]+", environment_id.casefold()))
    if environment_tokens.intersection({"dev", "development", "local", "test", "testing"}):
        raise ReleaseEvidenceError("MCP sender-constraint report identifies a local or development environment")
    if report.get("subject") != statement.get("subject"):
        raise ReleaseEvidenceError("MCP sender-constraint report is not bound to the release subject")
    if policy is not None:
        contract = policy.production_contracts.get(category)
        if contract is None:
            raise ReleaseEvidenceError("MCP sender-constraint production contract is missing")
        production_report = _load_json_object(
            statement_path.parent / contract.report_name,
            "MCP sender-constraint production report",
        )
        artifacts = production_report.get("artifacts")
        if (
            not isinstance(artifacts, list)
            or sum(
                1
                for artifact in artifacts
                if isinstance(artifact, dict) and artifact.get("path") == MCP_SENDER_CONSTRAINT_REPORT
            )
            != 1
        ):
            raise ReleaseEvidenceError("MCP sender-constraint report is not bound as a production artifact")
    statement_time = _parse_timestamp(statement.get("generated_at"), "MCP sender-constraint statement generated_at")
    tested_at = _parse_timestamp(report.get("tested_at"), "MCP sender-constraint tested_at")
    if tested_at > statement_time + timedelta(minutes=5) or statement_time - tested_at > timedelta(hours=24):
        raise ReleaseEvidenceError("MCP sender-constraint report is outside the allowed execution window")
    for field in ("idp_issuer_url", "resource_server_url"):
        value = report.get(field)
        parsed = urlsplit(value) if isinstance(value, str) else urlsplit("")
        hostname = parsed.hostname.casefold() if parsed.hostname else ""
        if (
            parsed.scheme != "https"
            or not hostname
            or parsed.username is not None
            or parsed.password is not None
            or hostname == "localhost"
            or hostname.endswith((".localhost", ".test", ".invalid", ".example"))
        ):
            raise ReleaseEvidenceError(f"MCP sender-constraint report has an invalid {field}")
    clients = report.get("clients")
    if not isinstance(clients, list) or len(clients) < 2:
        raise ReleaseEvidenceError("MCP sender-constraint report requires at least two clients")
    client_identities: set[tuple[str, str]] = set()
    for client in clients:
        if not isinstance(client, dict) or set(client) != {"name", "version", "dpop_supported"}:
            raise ReleaseEvidenceError("MCP sender-constraint report has an invalid client")
        name = client.get("name")
        version = client.get("version")
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 120
            or not isinstance(version, str)
            or not 1 <= len(version) <= 80
            or client.get("dpop_supported") is not True
        ):
            raise ReleaseEvidenceError("MCP sender-constraint report has an invalid client")
        client_identities.add((name, version))
    if len(client_identities) < 2:
        raise ReleaseEvidenceError("MCP sender-constraint report clients are not independent")
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != MCP_SENDER_CONSTRAINT_CHECKS
        or not all(value is True for value in checks.values())
    ):
        raise ReleaseEvidenceError("MCP sender-constraint report did not pass every required check")
    replay_store = report.get("replay_store")
    if not isinstance(replay_store, dict) or replay_store != {
        "failure_mode": "fail_closed",
        "shared": True,
        "tls": True,
    }:
        raise ReleaseEvidenceError("MCP sender-constraint replay-store evidence is incomplete")
    references = report.get("references")
    expected_references = {"gateway_change", "idp_change", "security_approval"}
    if (
        not isinstance(references, dict)
        or set(references) != expected_references
        or any(not isinstance(value, str) or not 3 <= len(value) <= 200 for value in references.values())
    ):
        raise ReleaseEvidenceError("MCP sender-constraint approval references are incomplete")
