from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import (
    DataSource,
    DataSourceType,
    ExtractionRun,
    RunState,
    SourceAsset,
    SourceVersion,
    SourceVersionState,
    StageStatus,
    Tenant,
)
from pharma_intel.security import Principal, require_principal


def test_governance_run_inventory_is_tenant_scoped_bounded_and_redacted(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    source = DataSource(
        tenant_id=tenant.id,
        name="Governance run source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Data Operations",
        authorization_scopes=["contract:test"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="reports/egfr.pdf",
        source_uri="file:///sources/reports/egfr.pdf",
        file_name="egfr.pdf",
        extension=".pdf",
        media_type="application/pdf",
        processing_mode="parse",
    )
    session.add(asset)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256="a" * 64,
        size_bytes=1024,
        state=SourceVersionState.GOVERNANCE_PENDING,
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        retrieval_status=StageStatus.NOT_STARTED,
        governance_status=StageStatus.RUNNING,
    )
    session.add(version)
    session.flush()
    run = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=version.id,
        schema_name="pharma_document_facts",
        schema_version="2.12",
        model_provider="openai_compatible",
        model_name="approved-model",
        prompt_sha256="b" * 64,
        policy_sha256="c" * 64,
        input_sha256="d" * 64,
        status=RunState.FAILED,
        structured_output={"sensitive": "must not be returned"},
        validation_errors=[{"code": "quote_not_found"}],
        input_tokens=120,
        output_tokens=30,
        estimated_cost=Decimal("0.012345"),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "operator-1", "user", frozenset({"governance:read"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/governance/runs",
                params={"status": "failed", "limit": 10, "offset": 0},
            )
            empty = client.get("/api/v1/governance/runs", params={"status": "succeeded"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert len(payload["current_policy_sha256"]) == 64
    assert run.started_at is not None
    assert run.completed_at is not None
    assert payload["items"][0] == {
        "id": run.id,
        "source_version_id": version.id,
        "source_asset_id": asset.id,
        "source_logical_path": "reports/egfr.pdf",
        "source_file_name": "egfr.pdf",
        "source_content_sha256": "a" * 64,
        "schema_name": "pharma_document_facts",
        "schema_version": "2.12",
        "model_provider": "openai_compatible",
        "model_name": "approved-model",
        "prompt_sha256": "b" * 64,
        "policy_sha256": "c" * 64,
        "input_sha256": "d" * 64,
        "policy_current": False,
        "status": "failed",
        "validation_errors": [{"code": "quote_not_found"}],
        "input_tokens": 120,
        "output_tokens": 30,
        "estimated_cost": "0.012345",
        "started_at": run.started_at.isoformat().replace("+00:00", "Z"),
        "completed_at": run.completed_at.isoformat().replace("+00:00", "Z"),
        "created_at": run.created_at.isoformat().replace("+00:00", "Z"),
    }
    assert "structured_output" not in payload["items"][0]
    assert empty.status_code == 200
    assert empty.json()["total"] == 0
