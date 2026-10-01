from __future__ import annotations

import hashlib
import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import case, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.models import (
    AuditEvent,
    ExtractionRun,
    IngestionRun,
    OutboxEvent,
    ProjectionDelivery,
    RunState,
    StagedFact,
)
from pharma_intel.operations_contract import load_operations_contract
from pharma_intel.platform.service_health import service_statuses

MAX_EVIDENCE_BYTES = 16 * 1024 * 1024
STALE_INGESTION_SECONDS = 300
EVIDENCE_CONTRACTS = {
    "backup_restore": ("backup_restore/report.json", "pharma.local-backup-restore-acceptance.v1", {"passed"}),
    "release_candidate": ("candidate-summary.json", None, {"eligible"}),
    "production_topology": (
        "production_topology/report.json",
        "pharma.production-topology-live-probe.v1",
        {"passed"},
    ),
}


class PlatformOperationsError(RuntimeError):
    pass


def _bounded_json(path: Path, root: Path) -> tuple[dict[str, Any], str]:
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(resolved_root):
        raise PlatformOperationsError("Platform evidence escaped the configured root")
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= MAX_EVIDENCE_BYTES:
        raise PlatformOperationsError("Platform evidence must be a bounded regular file")
    try:
        payload = path.read_bytes()
        value = json.loads(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlatformOperationsError("Platform evidence is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise PlatformOperationsError("Platform evidence must be a JSON object")
    return value, hashlib.sha256(payload).hexdigest()


def _evidence_entries(root: Path | None) -> list[dict[str, Any]]:
    if root is None:
        return [
            {
                "category": category,
                "status": "not_configured",
                "artifact": relative,
                "sha256": None,
                "observed_at": None,
                "detail": "Evidence mount is not configured for this environment",
            }
            for category, (relative, _, _) in EVIDENCE_CONTRACTS.items()
        ]
    if root.is_symlink() or not root.is_dir():
        return [
            {
                "category": category,
                "status": "invalid",
                "artifact": relative,
                "sha256": None,
                "observed_at": None,
                "detail": "Configured evidence root is unavailable or unsafe",
            }
            for category, (relative, _, _) in EVIDENCE_CONTRACTS.items()
        ]
    entries: list[dict[str, Any]] = []
    for category, (relative, expected_schema, passed_statuses) in EVIDENCE_CONTRACTS.items():
        path = root / relative
        if not path.exists():
            entries.append(
                {
                    "category": category,
                    "status": "missing",
                    "artifact": relative,
                    "sha256": None,
                    "observed_at": None,
                    "detail": "No machine-generated evidence is mounted",
                }
            )
            continue
        try:
            document, digest = _bounded_json(path, root)
            report_status = document.get("status")
            schema_valid = expected_schema is None or document.get("schema") == expected_schema
            valid = document.get("schema_version") == 1 and schema_valid and isinstance(report_status, str)
            status = "passed" if valid and report_status in passed_statuses else "failed" if valid else "invalid"
            observed_at = document.get("generated_at") or document.get("tested_at")
            entries.append(
                {
                    "category": category,
                    "status": status,
                    "artifact": relative,
                    "sha256": digest,
                    "observed_at": observed_at if isinstance(observed_at, str) else None,
                    "detail": f"Machine report status: {report_status}" if valid else "Evidence contract is invalid",
                }
            )
        except (OSError, PlatformOperationsError):
            entries.append(
                {
                    "category": category,
                    "status": "invalid",
                    "artifact": relative,
                    "sha256": None,
                    "observed_at": None,
                    "detail": "Evidence cannot be read safely",
                }
            )
    return entries


def _counts_by_state(session: Session, model: type[Any], state_column: Any, tenant_id: str) -> dict[str, int]:
    rows = session.execute(
        select(state_column, func.count()).where(model.tenant_id == tenant_id).group_by(state_column)
    ).all()
    return {str(state.value if hasattr(state, "value") else state): int(count) for state, count in rows}


def _migration_state(session: Session) -> dict[str, Any]:
    expected: str | None = None
    current: str | None = None
    try:
        configuration = Config("alembic.ini")
        expected = ScriptDirectory.from_config(configuration).get_current_head()
    except Exception:  # Alembic converts malformed script state into several exception families.
        expected = None
    try:
        current = session.scalar(text("SELECT version_num FROM alembic_version"))
    except SQLAlchemyError:
        current = None
    return {
        "current_revision": current,
        "expected_revision": expected,
        "status": (
            "current" if current and current == expected else "unknown" if not current or not expected else "behind"
        ),
    }


class PlatformOperationsService:
    def __init__(self, session: Session, *, tenant_id: str, settings: Settings) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.settings = settings

    def snapshot(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        contract_path = self.settings.platform_operations_contract_path
        try:
            contract = load_operations_contract(contract_path)
        except Exception as exc:
            raise PlatformOperationsError("Platform operations contract is unavailable") from exc

        ingestion_counts = _counts_by_state(self.session, IngestionRun, IngestionRun.state, self.tenant_id)
        stale_boundary = now - timedelta(seconds=STALE_INGESTION_SECONDS)
        stale_ingestion = int(
            self.session.scalar(
                select(func.count())
                .select_from(IngestionRun)
                .where(
                    IngestionRun.tenant_id == self.tenant_id,
                    IngestionRun.state == RunState.RUNNING,
                    func.coalesce(IngestionRun.heartbeat_at, IngestionRun.started_at) < stale_boundary,
                )
            )
            or 0
        )
        outbox_counts = _counts_by_state(self.session, OutboxEvent, OutboxEvent.state, self.tenant_id)
        delivery_rows = self.session.execute(
            select(ProjectionDelivery.consumer_name, ProjectionDelivery.state, func.count())
            .where(ProjectionDelivery.tenant_id == self.tenant_id)
            .group_by(ProjectionDelivery.consumer_name, ProjectionDelivery.state)
        ).all()
        delivery_counts: dict[str, dict[str, int]] = {}
        for consumer, state, count in delivery_rows:
            delivery_counts.setdefault(consumer, {})[state.value] = int(count)
        governance_counts = _counts_by_state(self.session, StagedFact, StagedFact.status, self.tenant_id)

        since = now - timedelta(hours=24)
        model_usage = self.session.execute(
            select(
                func.count(ExtractionRun.id),
                func.coalesce(func.sum(ExtractionRun.input_tokens), 0),
                func.coalesce(func.sum(ExtractionRun.output_tokens), 0),
                func.coalesce(func.sum(ExtractionRun.estimated_cost), 0),
                func.sum(case((ExtractionRun.status == RunState.FAILED, 1), else_=0)),
            ).where(ExtractionRun.tenant_id == self.tenant_id, ExtractionRun.created_at >= since)
        ).one()

        recent_events = self.session.scalars(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == self.tenant_id)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
            .limit(20)
        ).all()
        services = service_statuses(
            contract,
            stale_ingestion_runs=stale_ingestion,
            delivery_counts=delivery_counts,
            settings=self.settings,
        )
        return {
            "generated_at": now,
            "environment": self.settings.app_env,
            "services": services,
            "queues": {
                "ingestion": {**ingestion_counts, "stale": stale_ingestion},
                "outbox": outbox_counts,
                "deliveries": delivery_counts,
                "governance": governance_counts,
            },
            "workflow": {
                "engine": "temporal",
                "enabled": self.settings.temporal_enabled,
                "namespace": self.settings.temporal_namespace,
                "task_queue": self.settings.temporal_task_queue,
                "max_concurrent_activities": self.settings.temporal_max_concurrent_activities,
            },
            "model_budget": {
                "window": "24h",
                "run_count": int(model_usage[0]),
                "input_tokens": int(model_usage[1]),
                "output_tokens": int(model_usage[2]),
                "estimated_cost": format(model_usage[3], "f"),
                "failed_runs": int(model_usage[4] or 0),
                "max_document_cost": format(self.settings.ai_max_document_cost, "f"),
                "provider": "remote_api" if self.settings.ai_governance_enabled else "disabled",
                "model": self.settings.ai_model,
            },
            "slos": [
                {
                    "id": objective.id,
                    "service": objective.service,
                    "metric": objective.indicator.metric,
                    "measurement": objective.indicator.measurement,
                    "target": objective.target,
                    "window": objective.window,
                    "evaluation_status": "external_evidence_required",
                    "error_budget_policy": objective.error_budget_policy,
                }
                for objective in contract.objectives
            ],
            "alerts": [
                {
                    "id": alert.id,
                    "objective": alert.objective,
                    "severity": alert.severity,
                    "threshold": alert.threshold,
                    "lookback": alert.lookback,
                    "runbook": alert.runbook,
                }
                for alert in contract.alerts
            ],
            "migration": _migration_state(self.session),
            "evidence": _evidence_entries(self.settings.platform_evidence_root),
            "recent_events": [
                {
                    "id": event.id,
                    "action": event.action,
                    "outcome": event.outcome,
                    "resource_type": event.resource_type,
                    "occurred_at": event.occurred_at,
                    "request_id": event.request_id,
                }
                for event in recent_events
            ],
        }
