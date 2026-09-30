from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from pharma_intel.config import get_settings
from pharma_intel.models import Tenant
from pharma_intel.platform.operations import PlatformOperationsService

ROOT = Path(__file__).resolve().parents[1]


def test_platform_operations_snapshot_uses_real_tenant_state_and_declared_slos(
    session: Session,
    tenant: Tenant,
) -> None:
    settings = get_settings().model_copy(
        update={
            "platform_operations_contract_path": ROOT / "deploy/operations/operations-contract.yaml",
            "platform_evidence_root": None,
        }
    )

    snapshot = PlatformOperationsService(session, tenant_id=tenant.id, settings=settings).snapshot()

    assert snapshot["environment"] == settings.app_env
    assert len(snapshot["services"]) == 10
    assert {item["service_id"] for item in snapshot["services"]} >= {"api", "mcp", "data-factory"}
    assert len(snapshot["slos"]) == 13
    assert all(item["evaluation_status"] == "external_evidence_required" for item in snapshot["slos"])
    workspace_slos = {item["id"]: item for item in snapshot["slos"] if item["id"].startswith("workspace-")}
    assert {
        objective: (item["metric"], item["measurement"], item["target"]) for objective, item in workspace_slos.items()
    } == {
        "workspace-cls": ("pharma.web.vitals.cls", "p75_ratio", 0.1),
        "workspace-inp": ("pharma.web.vitals.duration", "p75_milliseconds", 200.0),
        "workspace-lcp": ("pharma.web.vitals.duration", "p75_milliseconds", 2500.0),
        "workspace-ttfb": ("pharma.web.vitals.duration", "p75_milliseconds", 800.0),
    }
    assert snapshot["queues"]["ingestion"]["stale"] == 0
    assert snapshot["workflow"]["engine"] == "temporal"
    assert snapshot["model_budget"]["run_count"] == 0
    assert {item["status"] for item in snapshot["evidence"]} == {"not_configured"}
    assert snapshot["migration"]["status"] in {"current", "unknown"}


def test_platform_operations_validates_bounded_machine_evidence(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    (tmp_path / "backup_restore").mkdir()
    (tmp_path / "production_topology").mkdir()
    (tmp_path / "backup_restore/report.json").write_text(
        json.dumps(
            {
                "schema": "pharma.local-backup-restore-acceptance.v1",
                "schema_version": 1,
                "status": "passed",
                "generated_at": "2026-07-25T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "candidate-summary.json").write_text(
        json.dumps({"schema_version": 1, "status": "blocked", "generated_at": "2026-07-25T00:00:00+00:00"}),
        encoding="utf-8",
    )
    (tmp_path / "production_topology/report.json").write_text("not-json", encoding="utf-8")
    settings = get_settings().model_copy(
        update={
            "platform_operations_contract_path": ROOT / "deploy/operations/operations-contract.yaml",
            "platform_evidence_root": tmp_path,
        }
    )

    evidence = PlatformOperationsService(session, tenant_id=tenant.id, settings=settings).snapshot()["evidence"]

    by_category = {item["category"]: item for item in evidence}
    assert by_category["backup_restore"]["status"] == "passed"
    assert len(by_category["backup_restore"]["sha256"]) == 64
    assert by_category["release_candidate"]["status"] == "failed"
    assert by_category["production_topology"]["status"] == "invalid"
