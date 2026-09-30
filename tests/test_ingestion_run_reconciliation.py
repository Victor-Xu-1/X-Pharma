from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker
from temporalio.client import WorkflowExecutionStatus

from pharma_intel.ingest.run_reconciliation import reconcile_stale_ingestion_runs
from pharma_intel.models import DataSource, DataSourceType, IngestionRun, RunState, Tenant


class _WorkflowHandle:
    def __init__(
        self,
        status: WorkflowExecutionStatus,
        close_time: datetime | None,
        result: object,
        *,
        before_result: Callable[[], None] | None = None,
    ) -> None:
        self._status = status
        self._close_time = close_time
        self._result = result
        self._before_result = before_result

    async def describe(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status=self._status, close_time=self._close_time)

    async def result(self, *, follow_runs: bool = True, **_kwargs: object) -> object:
        assert follow_runs is False
        if self._before_result is not None:
            self._before_result()
        return self._result


class _TemporalClient:
    def __init__(self, handles: dict[tuple[str, str], _WorkflowHandle]) -> None:
        self.handles = handles
        self.requests: list[tuple[str, str | None]] = []

    def get_workflow_handle(self, workflow_id: str, *, run_id: str | None = None) -> _WorkflowHandle:
        self.requests.append((workflow_id, run_id))
        assert run_id is not None
        return self.handles[(workflow_id, run_id)]


def _factory(session: Session) -> sessionmaker[Session]:
    return sessionmaker(bind=session.get_bind(), autoflush=False, expire_on_commit=False)


def _source(session: Session, tenant: Tenant) -> DataSource:
    source = DataSource(
        tenant_id=tenant.id,
        name="Reconciliation source",
        source_type=DataSourceType.FOLDER,
        root_uri="/sources/reconciliation",
        owner="Data Operations",
        authorization_scopes=["contract:reconciliation"],
        authorization_valid_from=datetime.now(UTC),
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    return source


@pytest.mark.anyio
async def test_completed_temporal_execution_reconciles_stale_running_database_row(
    session: Session,
    tenant: Tenant,
) -> None:
    now = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    closed_at = now - timedelta(minutes=8)
    source = _source(session, tenant)
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="source-ingest-source-1-correlation",
        temporal_workflow_id="source-ingest-source-1",
        temporal_run_id="temporal-run-1",
        state=RunState.RUNNING,
        started_at=now - timedelta(minutes=10),
        heartbeat_at=now - timedelta(minutes=9),
        counters={"discovered": 0, "unchanged": 29, "unstable": 0, "excluded": 0, "failed": 0},
        result={"version_ids": []},
    )
    session.add(run)
    session.commit()
    scan_result: dict[str, Any] = {
        "run_id": run.id,
        "state": "succeeded",
        "version_ids": [],
        "discovered": 0,
        "unchanged": 100,
        "unstable": 0,
        "excluded": 0,
        "failed": 0,
    }
    client = _TemporalClient(
        {
            ("source-ingest-source-1", "temporal-run-1"): _WorkflowHandle(
                WorkflowExecutionStatus.COMPLETED,
                closed_at,
                {"scan": scan_result, "versions": []},
            )
        }
    )

    report = await reconcile_stale_ingestion_runs(
        client,  # type: ignore[arg-type]
        _factory(session),
        now=now,
        stale_after=timedelta(minutes=5),
    )

    session.expire_all()
    reconciled = session.get(IngestionRun, run.id)
    assert reconciled is not None
    assert report.scanned == 1
    assert report.reconciled == 1
    assert report.failed == 0
    assert reconciled.state == RunState.SUCCEEDED
    assert reconciled.completed_at is not None
    assert reconciled.completed_at.replace(tzinfo=UTC) == closed_at
    assert reconciled.heartbeat_at is not None
    assert reconciled.heartbeat_at.replace(tzinfo=UTC) == closed_at
    assert reconciled.counters["unchanged"] == 100
    assert reconciled.result == {"version_ids": []}
    assert reconciled.error_summary is None
    assert client.requests == [("source-ingest-source-1", "temporal-run-1")]


@pytest.mark.anyio
async def test_running_temporal_execution_leaves_stale_database_row_unchanged(
    session: Session,
    tenant: Tenant,
) -> None:
    now = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    source = _source(session, tenant)
    heartbeat_at = now - timedelta(minutes=9)
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="source-ingest-source-2-correlation",
        temporal_workflow_id="source-ingest-source-2",
        temporal_run_id="temporal-run-2",
        state=RunState.RUNNING,
        started_at=now - timedelta(minutes=10),
        heartbeat_at=heartbeat_at,
        counters={"discovered": 0},
        result={"version_ids": []},
    )
    session.add(run)
    session.commit()
    client = _TemporalClient(
        {
            ("source-ingest-source-2", "temporal-run-2"): _WorkflowHandle(
                WorkflowExecutionStatus.RUNNING,
                None,
                None,
            )
        }
    )

    report = await reconcile_stale_ingestion_runs(
        client,  # type: ignore[arg-type]
        _factory(session),
        now=now,
        stale_after=timedelta(minutes=5),
    )

    session.expire_all()
    unchanged = session.get(IngestionRun, run.id)
    assert unchanged is not None
    assert report.scanned == 1
    assert report.reconciled == 0
    assert report.still_running == 1
    assert report.failed == 0
    assert unchanged.state == RunState.RUNNING
    assert unchanged.completed_at is None
    assert unchanged.heartbeat_at is not None
    assert unchanged.heartbeat_at.replace(tzinfo=UTC) == heartbeat_at


@pytest.mark.anyio
async def test_invalid_completed_payload_fails_closed_instead_of_remaining_running(
    session: Session,
    tenant: Tenant,
) -> None:
    now = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    closed_at = now - timedelta(minutes=7)
    source = _source(session, tenant)
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="source-ingest-source-3-correlation",
        temporal_workflow_id="source-ingest-source-3",
        temporal_run_id="temporal-run-3",
        state=RunState.RUNNING,
        started_at=now - timedelta(minutes=10),
        heartbeat_at=now - timedelta(minutes=9),
        counters={"discovered": 0},
        result={"version_ids": []},
    )
    session.add(run)
    session.commit()
    client = _TemporalClient(
        {
            ("source-ingest-source-3", "temporal-run-3"): _WorkflowHandle(
                WorkflowExecutionStatus.COMPLETED,
                closed_at,
                {"scan": {"run_id": "different-run", "state": "succeeded"}},
            )
        }
    )

    report = await reconcile_stale_ingestion_runs(
        client,  # type: ignore[arg-type]
        _factory(session),
        now=now,
        stale_after=timedelta(minutes=5),
    )

    session.expire_all()
    failed = session.get(IngestionRun, run.id)
    assert failed is not None
    assert report.reconciled == 1
    assert report.failed == 1
    assert failed.state == RunState.FAILED
    assert failed.error_summary == "Temporal workflow completed without a valid ingestion scan result"


@pytest.mark.anyio
async def test_reconciliation_does_not_overwrite_a_run_whose_heartbeat_recovers_during_lookup(
    session: Session,
    tenant: Tenant,
) -> None:
    now = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    source = _source(session, tenant)
    run = IngestionRun(
        tenant_id=tenant.id,
        data_source_id=source.id,
        workflow_id="source-ingest-source-4-correlation",
        temporal_workflow_id="source-ingest-source-4",
        temporal_run_id="temporal-run-4",
        state=RunState.RUNNING,
        started_at=now - timedelta(minutes=10),
        heartbeat_at=now - timedelta(minutes=9),
        counters={"discovered": 0},
        result={"version_ids": []},
    )
    session.add(run)
    session.commit()

    def refresh_heartbeat() -> None:
        run.heartbeat_at = now
        session.commit()

    scan_result = {
        "run_id": run.id,
        "state": "succeeded",
        "version_ids": [],
        "discovered": 0,
        "unchanged": 100,
        "unstable": 0,
        "excluded": 0,
        "failed": 0,
    }
    client = _TemporalClient(
        {
            ("source-ingest-source-4", "temporal-run-4"): _WorkflowHandle(
                WorkflowExecutionStatus.COMPLETED,
                now - timedelta(minutes=8),
                {"scan": scan_result, "versions": []},
                before_result=refresh_heartbeat,
            )
        }
    )

    report = await reconcile_stale_ingestion_runs(
        client,  # type: ignore[arg-type]
        _factory(session),
        now=now,
        stale_after=timedelta(minutes=5),
    )

    session.expire_all()
    active = session.get(IngestionRun, run.id)
    assert active is not None
    assert report.scanned == 1
    assert report.reconciled == 0
    assert active.state == RunState.RUNNING
    assert active.heartbeat_at is not None
    assert active.heartbeat_at.replace(tzinfo=UTC) == now
