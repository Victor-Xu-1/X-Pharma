from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.licensing import internal_evidence_license_policy
from pharma_intel.models import (
    AuditEvent,
    DataSource,
    DataSourceType,
    IngestionRun,
    RunState,
    Tenant,
    TenantDataset,
)
from pharma_intel.security import Principal, require_principal


def _source(session: Session, tenant: Tenant, root: str) -> DataSource:
    session.add(
        TenantDataset(
            tenant_id=tenant.id,
            dataset_key="literature",
            display_name="Literature",
            license_policy=internal_evidence_license_policy(source="test"),
            required_scopes=[],
        )
    )
    source = DataSource(
        tenant_id=tenant.id,
        name="Literature",
        source_type=DataSourceType.FOLDER,
        root_uri=root,
        owner="Data Operations",
        authorization_scopes=["contract:test-literature"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(source)
    session.commit()
    return source


@pytest.mark.parametrize("state", [RunState.FAILED, RunState.PARTIAL, RunState.CANCELED])
def test_replay_terminal_ingestion_run_starts_governed_workflow_and_audits(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state: RunState,
) -> None:
    source = _source(session, tenant, str(tmp_path))
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id=f"failed-{state.value}",
        state=state,
        error_summary="recoverable parser failure",
    )
    session.add(run)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "operator-1", "user", frozenset({"ingestion:manage"}))

    temporal_client = AsyncMock()
    monkeypatch.setattr("pharma_intel.api.Client.connect", AsyncMock(return_value=temporal_client))
    monkeypatch.setattr(
        "pharma_intel.api.get_settings",
        lambda: Settings(source_roots_config=str(tmp_path), temporal_enabled=True),
    )
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/admin/ingestion-runs/{run.id}/replay",
                json={
                    "operation_key": f"replay-{state.value}-0001",
                    "expected_state": state.value,
                    "reason": "Retry after parser service recovery",
                },
            )
            replay = client.post(
                f"/api/v1/admin/ingestion-runs/{run.id}/replay",
                json={
                    "operation_key": f"replay-{state.value}-0001",
                    "expected_state": state.value,
                    "reason": "Retry after parser service recovery",
                },
            )
            conflicting_replay = client.post(
                f"/api/v1/admin/ingestion-runs/{run.id}/replay",
                json={
                    "operation_key": f"replay-{state.value}-0001",
                    "expected_state": state.value,
                    "reason": "Different replay intent",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["workflow_id"] == f"source-ingest-{source.id}"
    assert body["replayed_from_run_id"] == run.id
    assert body["ingestion_run_id"].startswith(f"source-ingest-{source.id}-")
    assert replay.status_code == 202
    assert replay.json() == body
    assert conflicting_replay.status_code == 409
    temporal_client.start_workflow.assert_awaited_once()
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.tenant_id == tenant.id,
            AuditEvent.action == "ingestion_run.replay",
            AuditEvent.resource_id == run.id,
        )
    )
    assert audit is not None
    assert audit.actor_id == "operator-1"
    assert audit.details["reason"] == "Retry after parser service recovery"
    assert audit.details["ingestion_run_id"] == body["ingestion_run_id"]


def test_replay_rejects_non_terminal_missing_cross_tenant_and_invalid_requests(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(session, tenant, str(tmp_path))
    succeeded = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="succeeded-run",
        state=RunState.SUCCEEDED,
    )
    other_tenant = Tenant(slug="other", name="Other")
    session.add_all([succeeded, other_tenant])
    session.flush()
    other_source = DataSource(
        tenant_id=other_tenant.id,
        name="Other source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Other Operations",
        authorization_scopes=["contract:other"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
        stable_seconds=0,
    )
    session.add(other_source)
    session.flush()
    other_run = IngestionRun(
        tenant_id=other_tenant.id,
        data_source_id=other_source.id,
        workflow_id="other-failed-run",
        state=RunState.FAILED,
    )
    session.add(other_run)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "operator-1", "user", frozenset({"ingestion:manage"}))

    connect = AsyncMock()
    monkeypatch.setattr("pharma_intel.api.Client.connect", connect)
    monkeypatch.setattr(
        "pharma_intel.api.get_settings",
        lambda: Settings(source_roots_config=str(tmp_path), temporal_enabled=True),
    )
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            invalid_reason = client.post(
                f"/api/v1/admin/ingestion-runs/{succeeded.id}/replay",
                json={"operation_key": "replay-invalid-0001", "expected_state": "failed", "reason": "x"},
            )
            non_terminal = client.post(
                f"/api/v1/admin/ingestion-runs/{succeeded.id}/replay",
                json={
                    "operation_key": "replay-succeeded-0001",
                    "expected_state": "failed",
                    "reason": "Operator requested replay",
                },
            )
            missing = client.post(
                "/api/v1/admin/ingestion-runs/missing/replay",
                json={
                    "operation_key": "replay-missing-0001",
                    "expected_state": "failed",
                    "reason": "Operator requested replay",
                },
            )
            cross_tenant = client.post(
                f"/api/v1/admin/ingestion-runs/{other_run.id}/replay",
                json={
                    "operation_key": "replay-cross-tenant-0001",
                    "expected_state": "failed",
                    "reason": "Operator requested replay",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert invalid_reason.status_code == 422
    assert non_terminal.status_code == 409
    assert missing.status_code == 404
    assert cross_tenant.status_code == 404
    connect.assert_not_awaited()


def test_cancel_running_ingestion_run_targets_exact_temporal_execution_and_audits(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(session, tenant, str(tmp_path))
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="source-ingest-source-1-correlation",
        temporal_workflow_id="source-ingest-source-1",
        temporal_run_id="019f-temporal-run-1",
        state=RunState.RUNNING,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "operator-1", "user", frozenset({"ingestion:manage"}))

    handle = AsyncMock()
    temporal_client = MagicMock()
    temporal_client.get_workflow_handle.return_value = handle
    monkeypatch.setattr("pharma_intel.api.Client.connect", AsyncMock(return_value=temporal_client))
    monkeypatch.setattr(
        "pharma_intel.api.get_settings",
        lambda: Settings(source_roots_config=str(tmp_path), temporal_enabled=True),
    )
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    payload = {
        "operation_key": "cancel-running-0001",
        "expected_state": "running",
        "reason": "Source owner requested a controlled stop",
    }
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/v1/admin/ingestion-runs/{run.id}/cancel", json=payload)
            replay = client.post(f"/api/v1/admin/ingestion-runs/{run.id}/cancel", json=payload)
            conflict = client.post(
                f"/api/v1/admin/ingestion-runs/{run.id}/cancel",
                json={**payload, "reason": "Different cancellation intent"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    body = response.json()
    assert body == {
        "run_id": run.id,
        "workflow_id": "source-ingest-source-1-correlation",
        "temporal_workflow_id": "source-ingest-source-1",
        "temporal_run_id": "019f-temporal-run-1",
        "status": "cancel_requested",
    }
    assert replay.status_code == 202
    assert replay.json() == body
    assert conflict.status_code == 409
    temporal_client.get_workflow_handle.assert_called_once_with(
        "source-ingest-source-1",
        run_id="019f-temporal-run-1",
    )
    handle.cancel.assert_awaited_once_with(reason="Source owner requested a controlled stop")
    session.refresh(run)
    assert run.state == RunState.CANCELED
    assert run.cancel_requested_at is not None
    assert run.cancel_requested_by_actor_id == "operator-1"
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.tenant_id == tenant.id,
            AuditEvent.action == "ingestion_run.cancel",
            AuditEvent.resource_id == run.id,
        )
    )
    assert audit is not None
    assert audit.details["temporal_run_id"] == "019f-temporal-run-1"


def test_cancel_rejects_terminal_or_unbound_ingestion_execution(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(session, tenant, str(tmp_path))
    completed = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="completed-run",
        state=RunState.SUCCEEDED,
    )
    unbound = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="unbound-running-run",
        state=RunState.RUNNING,
    )
    session.add_all([completed, unbound])
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "operator-1", "user", frozenset({"ingestion:manage"}))

    connect = AsyncMock()
    monkeypatch.setattr("pharma_intel.api.Client.connect", connect)
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    payload = {
        "operation_key": "cancel-terminal-0001",
        "expected_state": "running",
        "reason": "Controlled stop requested by source owner",
    }
    try:
        with TestClient(app) as client:
            terminal = client.post(f"/api/v1/admin/ingestion-runs/{completed.id}/cancel", json=payload)
            unbound_response = client.post(
                f"/api/v1/admin/ingestion-runs/{unbound.id}/cancel",
                json={**payload, "operation_key": "cancel-unbound-0001"},
            )
    finally:
        app.dependency_overrides.clear()

    assert terminal.status_code == 409
    assert terminal.json()["detail"]["current_state"] == "succeeded"
    assert unbound_response.status_code == 409
    assert unbound_response.json()["detail"] == "Ingestion run does not have a bound Temporal execution"
    connect.assert_not_awaited()
