from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.platform import (
    RUNTIME_ACCEPTANCE_FIELDS,
    RUNTIME_ACCEPTANCE_REPORT,
    RUNTIME_ACCEPTANCE_SCHEMA,
    RUNTIME_ACCEPTANCE_SCHEMA_V1,
    RUNTIME_ACCEPTANCE_SCHEMA_V2,
    RUNTIME_APPLICATION_SERVICES,
    RUNTIME_SERVICES,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_runtime_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("runtime acceptance attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == RUNTIME_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("runtime acceptance requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / RUNTIME_ACCEPTANCE_REPORT, "runtime acceptance report")
    schema = report.get("schema")
    schema_version = report.get("schema_version")
    if (
        set(report) != RUNTIME_ACCEPTANCE_FIELDS
        or not (
            (schema == RUNTIME_ACCEPTANCE_SCHEMA_V1 and schema_version == 1)
            or (schema == RUNTIME_ACCEPTANCE_SCHEMA_V2 and schema_version == 2)
            or (schema == RUNTIME_ACCEPTANCE_SCHEMA and schema_version == 3)
        )
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
        or report.get("compose_profile") != "compose+dev+telemetry"
        or report.get("main_runtime_modified") is not False
    ):
        raise ReleaseEvidenceError("runtime acceptance report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "runtime statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "runtime generated_at")
    maximum_age_hours = policy.categories["runtime"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("runtime acceptance report is outside the allowed evidence window")
    services = report.get("services")
    if not isinstance(services, list) or len(services) != len(RUNTIME_SERVICES):
        raise ReleaseEvidenceError("runtime service inventory is incomplete")
    services_by_name = {
        service.get("service"): service
        for service in services
        if isinstance(service, dict) and isinstance(service.get("service"), str)
    }
    if set(services_by_name) != set(RUNTIME_SERVICES):
        raise ReleaseEvidenceError("runtime service inventory is incomplete")
    for name, service in services_by_name.items():
        expected_health = {"healthy", "none"} if name == "otel-collector" else {"healthy"}
        if (
            set(service) != {"service", "state", "health", "image_id"}
            or service.get("state") != "running"
            or service.get("health") not in expected_health
            or not isinstance(service.get("image_id"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", service["image_id"]) is None
        ):
            raise ReleaseEvidenceError(f"runtime service is not healthy: {name}")
    subject = statement.get("subject")
    targets = subject.get("targets") if isinstance(subject, dict) else None
    api_target = targets.get("api") if isinstance(targets, dict) else None
    postgres_target = targets.get("postgres") if isinstance(targets, dict) else None
    if (
        not isinstance(api_target, str)
        or "@" not in api_target
        or not isinstance(postgres_target, str)
        or "@" not in postgres_target
    ):
        raise ReleaseEvidenceError("runtime statement image subjects are invalid")
    expected_api_image = api_target.rsplit("@", maxsplit=1)[1]
    expected_postgres_image = postgres_target.rsplit("@", maxsplit=1)[1]
    if (
        any(services_by_name[name].get("image_id") != expected_api_image for name in RUNTIME_APPLICATION_SERVICES)
        or services_by_name["postgres"].get("image_id") != expected_postgres_image
    ):
        raise ReleaseEvidenceError("runtime containers do not run the security-scanned release images")
    legacy_entrypoints: dict[str, Any] = {
        "web": {"url": "http://127.0.0.1:18380", "liveness": "passed", "readiness": "passed"},
        "mcp": {"url": "http://127.0.0.1:18390/mcp", "unauthenticated_status": 401},
        "parser": {"backend": "service", "readiness": "passed"},
    }
    workbench_result = {
        "get_status": 200,
        "head_status": 200,
        "content_type": "text/html",
        "security_headers": "passed",
        "spa_shell": "passed",
    }
    current_entrypoints: dict[str, Any] = {
        **legacy_entrypoints,
        "web": {
            **legacy_entrypoints["web"],
            "workbenches": {
                "research": {"path": "/workspace/research", **workbench_result},
                "internal": {"path": "/workspace/internal", **workbench_result},
            },
        },
    }
    entrypoints = report.get("entrypoints")
    if schema_version == 1:
        if entrypoints != legacy_entrypoints:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
    elif schema_version == 2:
        if entrypoints != current_entrypoints:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
    else:
        if not isinstance(entrypoints, dict) or set(entrypoints) != {"web", "mcp", "parser"}:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
        web = entrypoints.get("web")
        if not isinstance(web, dict) or set(web) != {"url", "liveness", "readiness", "workbenches"}:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
        workbenches = web.get("workbenches")
        if not isinstance(workbenches, dict) or set(workbenches) != {"research", "internal"}:
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
        document_hashes: set[str] = set()
        for workbench in ("research", "internal"):
            evidence = workbenches.get(workbench)
            expected = {
                "path": f"/workspace/{workbench}",
                **workbench_result,
                "entry_document": f"{workbench}.html",
                "workbench_marker": workbench,
            }
            if not isinstance(evidence, dict) or set(evidence) != {*expected, "document_sha256"}:
                raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
            if any(evidence.get(key) != value for key, value in expected.items()):
                raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
            document_hash = evidence.get("document_sha256")
            if not isinstance(document_hash, str) or re.fullmatch(r"[0-9a-f]{64}", document_hash) is None:
                raise ReleaseEvidenceError("runtime entrypoint document digest is invalid")
            document_hashes.add(document_hash)
        if len(document_hashes) != 2:
            raise ReleaseEvidenceError("runtime workbench documents are not distinct")
        if {key: value for key, value in entrypoints.items() if key != "web"} != {
            "mcp": legacy_entrypoints["mcp"],
            "parser": legacy_entrypoints["parser"],
        } or any(web.get(key) != legacy_entrypoints["web"][key] for key in ("url", "liveness", "readiness")):
            raise ReleaseEvidenceError("runtime entrypoint boundary evidence is incomplete")
    database = report.get("database")
    if (
        not isinstance(database, dict)
        or set(database) != {"alembic_head", "postgresql_version", "rdkit_version"}
        or database.get("alembic_head") != "5d7e1a3c9b24"
        or not isinstance(database.get("postgresql_version"), str)
        or not database["postgresql_version"].startswith("18.4 ")
        or database.get("rdkit_version") != "4.8.0"
    ):
        raise ReleaseEvidenceError("runtime database authority evidence is invalid")
    search = report.get("search")
    cluster = search.get("cluster") if isinstance(search, dict) else None
    deliveries = search.get("deliveries") if isinstance(search, dict) else None
    if (
        not isinstance(search, dict)
        or set(search) != {"cluster", "deliveries"}
        or not isinstance(cluster, dict)
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
        or not isinstance(deliveries.get("succeeded"), int)
        or isinstance(deliveries.get("succeeded"), bool)
        or deliveries["succeeded"] < 0
    ):
        raise ReleaseEvidenceError("runtime OpenSearch projection evidence is invalid")
    if report.get("runtime_hygiene") != {
        "schema_version": 1,
        "status": "passed",
        "finding_count": 0,
        "findings": [],
    }:
        raise ReleaseEvidenceError("runtime persistent data hygiene evidence is incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 180:
        raise ReleaseEvidenceError("runtime acceptance duration is invalid")
