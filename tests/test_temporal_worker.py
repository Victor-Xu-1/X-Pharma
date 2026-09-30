from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from pharma_intel.commercial.export_activities import execute_export_activity, fail_export_activity
from pharma_intel.commercial.export_contracts import ExportInput
from pharma_intel.commercial.export_workflows import GovernedDataExportWorkflow
from pharma_intel.config import Settings
from pharma_intel.ingest import temporal_worker
from pharma_intel.ingest.contracts import ScanInput
from pharma_intel.ingest.workflows import SourceVersionReprocessWorkflow


@pytest.mark.anyio
async def test_temporal_process_rejects_empty_role_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        temporal_enabled=True,
        temporal_worker_enabled=False,
        temporal_scheduler_enabled=False,
    )
    monkeypatch.setattr(temporal_worker, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="process role"):
        await temporal_worker._run()


@pytest.mark.anyio
async def test_temporal_connection_retries_with_bounded_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        temporal_connect_attempts=4,
        temporal_connect_backoff_seconds=0.1,
        temporal_connect_max_backoff_seconds=0.15,
    )
    connected_client = object()
    attempts = 0
    delays: list[float] = []

    async def connect(*args: Any, **kwargs: Any) -> object:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("Temporal is starting")
        return connected_client

    async def sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("pharma_intel.ingest.temporal_worker.Client.connect", connect)
    monkeypatch.setattr("pharma_intel.ingest.temporal_worker.asyncio.sleep", sleep)

    result = await temporal_worker._connect_temporal(settings)

    assert result is connected_client
    assert attempts == 3
    assert delays == [0.1, 0.15]


@pytest.mark.anyio
async def test_temporal_worker_registers_governed_export_workflow_and_compensation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        temporal_enabled=True,
        temporal_worker_enabled=True,
        temporal_scheduler_enabled=False,
    )
    captured: dict[str, Any] = {}

    class FakeWorker:
        def __init__(self, _client: object, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def run(self) -> None:
            return None

    async def connect(_settings: Settings) -> object:
        return object()

    async def maintain(_client: object, _settings: Settings) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(temporal_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(temporal_worker, "_connect_temporal", connect)
    monkeypatch.setattr(temporal_worker, "Worker", FakeWorker)
    monkeypatch.setattr(temporal_worker, "_reconciliation_maintenance", maintain)
    monkeypatch.setenv("PHARMA_RUNTIME_HEARTBEAT_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="role exited unexpectedly"):
        await temporal_worker._run()

    assert GovernedDataExportWorkflow in captured["workflows"]
    assert SourceVersionReprocessWorkflow in captured["workflows"]
    assert execute_export_activity in captured["activities"]
    assert fail_export_activity in captured["activities"]


@pytest.mark.anyio
async def test_temporal_process_exits_when_heartbeat_maintenance_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        temporal_enabled=True,
        temporal_worker_enabled=True,
        temporal_scheduler_enabled=False,
    )

    class BlockingWorker:
        def __init__(self, _client: object, **_kwargs: Any) -> None:
            pass

        async def run(self) -> None:
            await asyncio.Event().wait()

    class FailingHeartbeat:
        def __init__(self, _service: str) -> None:
            pass

        def beat(self) -> None:
            raise RuntimeError("heartbeat storage failed")

        def __enter__(self) -> FailingHeartbeat:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    async def connect(_settings: Settings) -> object:
        return object()

    async def maintain(_client: object, _settings: Settings) -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(temporal_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(temporal_worker, "_connect_temporal", connect)
    monkeypatch.setattr(temporal_worker, "Worker", BlockingWorker)
    monkeypatch.setattr(temporal_worker, "_reconciliation_maintenance", maintain)
    monkeypatch.setattr(temporal_worker, "RuntimeHeartbeat", FailingHeartbeat)

    with pytest.raises(RuntimeError, match="heartbeat storage failed"):
        await temporal_worker._run()


@pytest.mark.anyio
async def test_worker_only_mode_starts_ingestion_run_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = Settings(
        temporal_enabled=True,
        temporal_worker_enabled=True,
        temporal_scheduler_enabled=False,
    )
    maintenance_started = asyncio.Event()

    class BlockingWorker:
        def __init__(self, _client: object, **_kwargs: Any) -> None:
            pass

        async def run(self) -> None:
            await asyncio.Event().wait()

    async def connect(_settings: Settings) -> object:
        return object()

    async def maintain(_client: object, _settings: Settings) -> None:
        maintenance_started.set()

    monkeypatch.setattr(temporal_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(temporal_worker, "_connect_temporal", connect)
    monkeypatch.setattr(temporal_worker, "Worker", BlockingWorker)
    monkeypatch.setattr(temporal_worker, "_reconciliation_maintenance", maintain)
    monkeypatch.setenv("PHARMA_RUNTIME_HEARTBEAT_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="ingestion-run-reconciliation"):
        await temporal_worker._run()

    assert maintenance_started.is_set()


def test_unavailable_source_uses_bounded_retry_backoff() -> None:
    settings = Settings(source_retry_base_seconds=60, source_retry_max_seconds=300)
    unavailable = SimpleNamespace(
        state=temporal_worker.DataSourceState.UNAVAILABLE,
        consecutive_failures=1,
        scan_interval_seconds=86_400,
    )
    repeated_failure = SimpleNamespace(
        state=temporal_worker.DataSourceState.UNAVAILABLE,
        consecutive_failures=4,
        scan_interval_seconds=86_400,
    )
    active = SimpleNamespace(
        state=temporal_worker.DataSourceState.ACTIVE,
        consecutive_failures=4,
        scan_interval_seconds=86_400,
    )

    assert temporal_worker._source_scan_interval(settings, unavailable) == 60  # type: ignore[arg-type]
    assert temporal_worker._source_scan_interval(settings, repeated_failure) == 300  # type: ignore[arg-type]
    assert temporal_worker._source_scan_interval(settings, active) == 86_400  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_scheduler_dispatches_due_sources_without_manual_trigger_and_deduplicates_execution_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(temporal_task_queue="automatic-ingestion-test")
    calls: list[tuple[object, object, dict[str, object]]] = []

    class RecordingClient:
        async def start_workflow(self, workflow: object, payload: object, **kwargs: object) -> None:
            calls.append((workflow, payload, kwargs))

    monkeypatch.setattr(
        temporal_worker,
        "_collect_due_work",
        lambda _settings, _now: (
            [("tenant-1", "source-1")],
            [("tenant-1", "export-1", "export-workflow-1")],
        ),
    )
    monkeypatch.setattr(temporal_worker, "_recover_stale_runs", lambda _settings, _now: 0)
    monkeypatch.setattr(
        temporal_worker,
        "reconcile_stale_ingestion_runs",
        AsyncMock(return_value=SimpleNamespace(scanned=0, reconciled=0, still_running=0, failed=0)),
    )
    client = RecordingClient()

    await temporal_worker._run_scheduler_iteration(client, settings, datetime.now(UTC))  # type: ignore[arg-type]
    await temporal_worker._run_scheduler_iteration(client, settings, datetime.now(UTC))  # type: ignore[arg-type]

    source_calls = [(payload, kwargs) for _, payload, kwargs in calls if isinstance(payload, ScanInput)]
    export_calls = [(payload, kwargs) for _, payload, kwargs in calls if isinstance(payload, ExportInput)]
    assert len(source_calls) == 2
    assert len(export_calls) == 2
    assert {kwargs["id"] for _, kwargs in source_calls} == {"source-ingest-source-1"}
    assert {kwargs["task_queue"] for _, kwargs in source_calls} == {"automatic-ingestion-test"}
    assert {kwargs["id_reuse_policy"] for _, kwargs in source_calls} == {WorkflowIDReusePolicy.ALLOW_DUPLICATE}
    assert source_calls[0][0].workflow_id != source_calls[1][0].workflow_id
    assert all(payload.workflow_id.startswith("source-ingest-source-1-") for payload, _ in source_calls)
    assert {kwargs["id"] for _, kwargs in export_calls} == {"export-workflow-1"}
    assert {kwargs["id_reuse_policy"] for _, kwargs in export_calls} == {WorkflowIDReusePolicy.REJECT_DUPLICATE}


@pytest.mark.anyio
async def test_parallel_schedulers_treat_temporal_workflow_conflicts_as_successful_deduplication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(temporal_task_queue="automatic-ingestion-ha-test")
    accepted: set[str] = set()

    class ContendedClient:
        async def start_workflow(self, _workflow: object, _payload: object, **kwargs: object) -> None:
            workflow_id = str(kwargs["id"])
            if workflow_id in accepted:
                raise WorkflowAlreadyStartedError(workflow_id, "test-workflow")
            accepted.add(workflow_id)

    monkeypatch.setattr(
        temporal_worker,
        "_collect_due_work",
        lambda _settings, _now: (
            [("tenant-1", "source-1")],
            [("tenant-1", "export-1", "export-workflow-1")],
        ),
    )
    monkeypatch.setattr(temporal_worker, "_recover_stale_runs", lambda _settings, _now: 0)
    monkeypatch.setattr(
        temporal_worker,
        "reconcile_stale_ingestion_runs",
        AsyncMock(return_value=SimpleNamespace(scanned=0, reconciled=0, still_running=0, failed=0)),
    )
    client = ContendedClient()

    await temporal_worker._run_scheduler_iteration(client, settings, datetime.now(UTC))  # type: ignore[arg-type]
    await temporal_worker._run_scheduler_iteration(client, settings, datetime.now(UTC))  # type: ignore[arg-type]

    assert accepted == {"source-ingest-source-1", "export-workflow-1"}
