from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from scripts.release.contracts.data import (
    DATABASE_ACCEPTANCE_FIELDS,
    DATABASE_ACCEPTANCE_REPORT,
    DATABASE_ACCEPTANCE_SCHEMA,
)
from scripts.release.io import _load_json_object, _parse_timestamp
from scripts.release.records import EvidencePolicy, ReleaseEvidenceError


def _validate_database_acceptance_evidence(
    statement_path: Path,
    statement: dict[str, Any],
    *,
    policy: EvidencePolicy | None,
) -> None:
    raw_attachments = statement.get("attachments")
    if not isinstance(raw_attachments, list):
        raise ReleaseEvidenceError("database acceptance attachments are invalid")
    reports = [
        item for item in raw_attachments if isinstance(item, dict) and item.get("path") == DATABASE_ACCEPTANCE_REPORT
    ]
    if len(reports) != 1:
        raise ReleaseEvidenceError("database acceptance requires exactly one report.json attachment")
    report = _load_json_object(statement_path.parent / DATABASE_ACCEPTANCE_REPORT, "database acceptance report")
    if (
        set(report) != DATABASE_ACCEPTANCE_FIELDS
        or report.get("schema") != DATABASE_ACCEPTANCE_SCHEMA
        or report.get("schema_version") != 1
        or report.get("status") != "passed"
        or report.get("environment") != "local-wsl"
        or report.get("production_claim") is not False
        or report.get("credentials_recorded") is not False
    ):
        raise ReleaseEvidenceError("database acceptance report has an invalid local scope or status")
    statement_time = _parse_timestamp(statement.get("generated_at"), "database statement generated_at")
    report_time = _parse_timestamp(report.get("generated_at"), "database generated_at")
    maximum_age_hours = policy.categories["database"] if policy is not None else 168
    if report_time > statement_time + timedelta(minutes=5) or statement_time - report_time > timedelta(
        hours=maximum_age_hours
    ):
        raise ReleaseEvidenceError("database acceptance report is outside the allowed evidence window")
    database = report.get("database")
    if (
        not isinstance(database, dict)
        or set(database) != {"postgresql_version", "rdkit_version", "alembic_head", "migration_drift"}
        or not isinstance(database.get("postgresql_version"), str)
        or not database["postgresql_version"].startswith("18.4 ")
        or database.get("rdkit_version") != "4.8.0"
        or database.get("alembic_head") != "5d7e1a3c9b24"
        or database.get("migration_drift") is not False
    ):
        raise ReleaseEvidenceError("database authority version or migration evidence is invalid")
    rls = report.get("rls")
    if (
        not isinstance(rls, dict)
        or set(rls)
        != {
            "bypass_rls",
            "forged_context_rows",
            "no_context_rows",
            "passed",
            "runtime_role",
            "signed_context_rows",
            "signed_context_valid",
            "superuser",
        }
        or rls.get("passed") is not True
        or rls.get("runtime_role") != "pharma_runtime"
        or rls.get("superuser") is not False
        or rls.get("bypass_rls") is not False
        or rls.get("no_context_rows") != 0
        or rls.get("forged_context_rows") != 0
        or isinstance(rls.get("signed_context_rows"), bool)
        or not isinstance(rls.get("signed_context_rows"), int)
        or rls["signed_context_rows"] < 0
        or rls.get("signed_context_valid") is not True
    ):
        raise ReleaseEvidenceError("database signed tenant RLS evidence is incomplete")
    hygiene = report.get("runtime_hygiene")
    if hygiene != {"schema_version": 1, "status": "passed", "finding_count": 0, "findings": []}:
        raise ReleaseEvidenceError("database persistent runtime hygiene evidence is incomplete")
    search = report.get("search")
    cluster = search.get("cluster") if isinstance(search, dict) else None
    deliveries = search.get("deliveries") if isinstance(search, dict) else None
    if not isinstance(search, dict) or set(search) != {"cluster", "deliveries"}:
        raise ReleaseEvidenceError("database OpenSearch evidence is invalid")
    if (
        not isinstance(cluster, dict)
        or set(cluster) != {"aliases", "available", "cluster_name", "cluster_status", "error", "version"}
        or cluster.get("available") is not True
        or cluster.get("cluster_name") != "pharma-search"
        or cluster.get("cluster_status") != "green"
        or cluster.get("error") is not None
        or cluster.get("version") != "3.7.0"
    ):
        raise ReleaseEvidenceError("database OpenSearch cluster evidence is invalid")
    aliases = cluster.get("aliases")
    if not isinstance(aliases, dict) or set(aliases) != {"entities", "evidence", "knowledge"}:
        raise ReleaseEvidenceError("database OpenSearch alias inventory is invalid")
    for name, values in aliases.items():
        if (
            not isinstance(values, list)
            or len(values) != 1
            or not isinstance(values[0], str)
            or not values[0].startswith(f"pharma-{name}-v2-")
        ):
            raise ReleaseEvidenceError(f"database OpenSearch alias is invalid: {name}")
    if (
        not isinstance(deliveries, dict)
        or set(deliveries) != {"dead", "processing", "retry", "succeeded"}
        or any(deliveries.get(name) != 0 for name in ("dead", "processing", "retry"))
        or not isinstance(deliveries.get("succeeded"), int)
        or isinstance(deliveries.get("succeeded"), bool)
        or deliveries["succeeded"] < 0
    ):
        raise ReleaseEvidenceError("database OpenSearch delivery queue evidence is invalid")
    if report.get("hybrid_search") != {
        "status": "passed",
        "protocol": "OpenSearch 3.x native hybrid query and normalization pipeline",
        "index_schema_version": 2,
        "embedding_fixture": "deterministic-controlled-test-vector",
        "production_embedding_model_verified": False,
    }:
        raise ReleaseEvidenceError("database local hybrid-search evidence is incomplete")
    duration = report.get("duration_seconds")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 < duration <= 120:
        raise ReleaseEvidenceError("database acceptance duration is invalid")
