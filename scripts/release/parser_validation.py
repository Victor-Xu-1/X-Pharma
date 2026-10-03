from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.core import SHA256_PATTERN
from scripts.release.contracts.parser import (
    PARSER_ADVERSARIAL_CASE_CONTRACTS,
    PARSER_ADVERSARIAL_CORPUS_FIELDS,
    PARSER_CAPACITY_FIELDS,
    PARSER_DOCUMENT_CONTRACTS,
    PARSER_SANDBOX_FIELDS,
    PARSER_SANDBOX_REPORT,
    PARSER_SANDBOX_SCHEMA,
    PARSER_TIMEOUT_RECOVERY_FIELDS,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_parser_sandbox_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("parser sandbox attachments are invalid")
    reports = [item for item in raw_attachments if isinstance(item, dict) and item.get("path") == PARSER_SANDBOX_REPORT]
    if len(reports) != 1:
        raise ReleaseEvidenceError("parser sandbox requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / PARSER_SANDBOX_REPORT, "parser sandbox report")
    if (
        set(report) != PARSER_SANDBOX_FIELDS
        or report.get("schema") != PARSER_SANDBOX_SCHEMA
        or report.get("schema_version") != 3
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl-isolated-parser"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("parser_backend") != "service"
        or report.get("document_count") != 11
        or report.get("unauthorized_status") != 401
        or report.get("digest_mismatch_status") != 400
        or report.get("outbound_network_blocked") is not True
    ):
        raise ReleaseEvidenceError("parser sandbox report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "parser sandbox statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "parser sandbox generated_at")
    maximum_age_hours = policy.categories["parser_sandbox"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("parser sandbox report is outside the allowed evidence window")
    documents = report.get("documents")
    if not isinstance(documents, list) or len(documents) != len(PARSER_DOCUMENT_CONTRACTS):
        raise ReleaseEvidenceError("parser sandbox document inventory is incomplete")
    documents_by_suffix = {
        document.get("suffix"): document
        for document in documents
        if isinstance(document, dict) and isinstance(document.get("suffix"), str)
    }
    if set(documents_by_suffix) != set(PARSER_DOCUMENT_CONTRACTS):
        raise ReleaseEvidenceError("parser sandbox document inventory is incomplete")
    for suffix, (parser_name, parser_version) in PARSER_DOCUMENT_CONTRACTS.items():
        document = documents_by_suffix[suffix]
        metadata_keys = document.get("metadata_keys")
        digest = document.get("text_sha256")
        if (
            set(document) != {"suffix", "parser_name", "parser_version", "metadata_keys", "text_sha256"}
            or document.get("parser_name") != parser_name
            or document.get("parser_version") != parser_version
            or not isinstance(metadata_keys, list)
            or not metadata_keys
            or metadata_keys != sorted(set(metadata_keys))
            or any(not isinstance(name, str) or not name for name in metadata_keys)
            or not isinstance(digest, str)
            or SHA256_PATTERN.fullmatch(digest) is None
        ):
            raise ReleaseEvidenceError(f"parser sandbox document contract is invalid: {suffix}")
    infrastructure = report.get("infrastructure")
    expected_secret_scope = [
        "PARSER_SERVICE_HOST",
        "PARSER_SERVICE_LIMIT_CONCURRENCY",
        "PARSER_SERVICE_MAX_CONCURRENT_PARSES",
        "PARSER_SERVICE_MAX_FILE_BYTES",
        "PARSER_SERVICE_MAX_TEXT_CHARS",
        "PARSER_SERVICE_PARSER_CPU_SECONDS",
        "PARSER_SERVICE_PARSER_MEMORY_BYTES",
        "PARSER_SERVICE_PARSER_TIMEOUT_SECONDS",
        "PARSER_SERVICE_PORT",
        "PARSER_SERVICE_TOKEN",
    ]
    if (
        not isinstance(infrastructure, dict)
        or set(infrastructure)
        != {
            "capabilities_dropped",
            "memory_limit_bytes",
            "nano_cpus",
            "network_internal",
            "network_member_roles",
            "parser_secret_scope",
            "pids_limit",
            "read_only_root_filesystem",
        }
        or infrastructure.get("capabilities_dropped") != ["ALL"]
        or infrastructure.get("memory_limit_bytes") != 3 * 1024**3
        or infrastructure.get("nano_cpus") != 2_000_000_000
        or infrastructure.get("network_internal") is not True
        or infrastructure.get("network_member_roles") != ["parser", "worker"]
        or infrastructure.get("parser_secret_scope") != expected_secret_scope
        or infrastructure.get("pids_limit") != 64
        or infrastructure.get("read_only_root_filesystem") is not True
    ):
        raise ReleaseEvidenceError("parser sandbox container isolation evidence is incomplete")
    capacity = report.get("capacity")
    if (
        not isinstance(capacity, dict)
        or set(capacity) != PARSER_CAPACITY_FIELDS
        or capacity.get("schema_version") != 1
        or capacity.get("status") != "passed"
        or capacity.get("production_claim") is not False
        or capacity.get("max_concurrent_parses") != 1
        or capacity.get("held_request_status") != 200
        or capacity.get("saturated_request_status") != 429
        or capacity.get("saturated_error_code") != "parser_capacity_exhausted"
        or capacity.get("retry_after_seconds") != "1"
        or capacity.get("recovery_request_status") != 200
        or capacity.get("ready_after_status") != 200
    ):
        raise ReleaseEvidenceError("parser sandbox capacity and recovery evidence is incomplete")
    capacity_time = _parse_timestamp(capacity.get("generated_at"), "parser sandbox capacity generated_at")
    if capacity_time > report_time + timedelta(minutes=5) or report_time - capacity_time > timedelta(hours=1):
        raise ReleaseEvidenceError("parser sandbox capacity evidence is outside the report window")
    timeout_recovery = report.get("timeout_recovery")
    if (
        not isinstance(timeout_recovery, dict)
        or set(timeout_recovery) != PARSER_TIMEOUT_RECOVERY_FIELDS
        or timeout_recovery.get("schema_version") != 1
        or timeout_recovery.get("status") != "passed"
        or timeout_recovery.get("production_claim") is not False
        or timeout_recovery.get("timeout_observed") is not True
        or timeout_recovery.get("child_processes_after_timeout") != 0
        or timeout_recovery.get("recovery_parser_name") != "text"
        or not isinstance(timeout_recovery.get("recovery_text_sha256"), str)
        or SHA256_PATTERN.fullmatch(timeout_recovery["recovery_text_sha256"]) is None
    ):
        raise ReleaseEvidenceError("parser sandbox timeout cleanup and recovery evidence is incomplete")
    timeout_time = _parse_timestamp(timeout_recovery.get("generated_at"), "parser sandbox timeout generated_at")
    timeout_duration = timeout_recovery.get("duration_seconds")
    if (
        timeout_time > report_time + timedelta(minutes=5)
        or report_time - timeout_time > timedelta(hours=1)
        or not isinstance(timeout_duration, int | float)
        or isinstance(timeout_duration, bool)
        or not 0 < timeout_duration <= 30
    ):
        raise ReleaseEvidenceError("parser sandbox timeout recovery timing is invalid")
    adversarial_corpus = report.get("adversarial_corpus")
    corpus_cases = adversarial_corpus.get("cases") if isinstance(adversarial_corpus, dict) else None
    if (
        not isinstance(adversarial_corpus, dict)
        or set(adversarial_corpus) != PARSER_ADVERSARIAL_CORPUS_FIELDS
        or adversarial_corpus.get("schema_version") != 1
        or adversarial_corpus.get("status") != "passed"
        or adversarial_corpus.get("production_claim") is not False
        or adversarial_corpus.get("case_count") != len(PARSER_ADVERSARIAL_CASE_CONTRACTS)
        or adversarial_corpus.get("recovery_status") != 200
        or adversarial_corpus.get("ready_after_status") != 200
        or not isinstance(corpus_cases, list)
        or len(corpus_cases) != len(PARSER_ADVERSARIAL_CASE_CONTRACTS)
        or [(case.get("name"), case.get("suffix")) for case in corpus_cases if isinstance(case, dict)]
        != list(PARSER_ADVERSARIAL_CASE_CONTRACTS)
        or any(
            not isinstance(case, dict)
            or set(case) != {"name", "suffix", "status", "error_code"}
            or case.get("status") != 422
            or case.get("error_code") != "document_parse_rejected"
            for case in corpus_cases
        )
    ):
        raise ReleaseEvidenceError("parser sandbox adversarial corpus evidence is incomplete")
    corpus_time = _parse_timestamp(
        adversarial_corpus.get("generated_at"),
        "parser sandbox adversarial corpus generated_at",
    )
    if corpus_time > report_time + timedelta(minutes=5) or report_time - corpus_time > timedelta(hours=1):
        raise ReleaseEvidenceError("parser sandbox adversarial corpus evidence is outside the report window")
    mtls = report.get("mtls")
    if (
        not isinstance(mtls, dict)
        or set(mtls)
        != {
            "schema_version",
            "status",
            "generated_at",
            "production_claim",
            "mutual_tls",
            "valid_client_parse",
            "no_client_certificate_rejected",
            "rogue_client_rejected",
            "untrusted_server_rejected",
            "client_certificate_sha256",
            "server_certificate_sha256",
            "duration_seconds",
        }
        or mtls.get("schema_version") != 1
        or mtls.get("status") != "passed"
        or mtls.get("production_claim") is not False
        or mtls.get("mutual_tls") is not True
        or mtls.get("valid_client_parse") is not True
        or mtls.get("no_client_certificate_rejected") is not True
        or mtls.get("rogue_client_rejected") is not True
        or mtls.get("untrusted_server_rejected") is not True
    ):
        raise ReleaseEvidenceError("parser sandbox mutual TLS evidence is incomplete")
    mtls_time = _parse_timestamp(mtls.get("generated_at"), "parser sandbox mTLS generated_at")
    if mtls_time > report_time + timedelta(minutes=5) or report_time - mtls_time > timedelta(hours=1):
        raise ReleaseEvidenceError("parser sandbox mutual TLS evidence is outside the report window")
    if any(
        not isinstance(mtls.get(field), str) or SHA256_PATTERN.fullmatch(mtls[field]) is None
        for field in ("client_certificate_sha256", "server_certificate_sha256")
    ):
        raise ReleaseEvidenceError("parser sandbox certificate digests are invalid")
    mtls_duration = mtls.get("duration_seconds")
    if not isinstance(mtls_duration, int | float) or isinstance(mtls_duration, bool) or not 0 < mtls_duration <= 60:
        raise ReleaseEvidenceError("parser sandbox mutual TLS duration is invalid")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 180:
        raise ReleaseEvidenceError("parser sandbox duration is invalid")
