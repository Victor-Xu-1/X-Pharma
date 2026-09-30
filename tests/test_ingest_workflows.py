from __future__ import annotations

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from temporalio import workflow as temporal_workflow
from temporalio.exceptions import ActivityError, ApplicationError, RetryState
from temporalio.workflow import ActivityCancellationType

from pharma_intel.ingest import workflows
from pharma_intel.ingest.activities import scan_source_activity
from pharma_intel.ingest.contracts import ProcessInput, ScanInput


@pytest.mark.asyncio
async def test_process_version_failure_is_isolated_after_activity_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = ActivityError(
        "activity failed",
        scheduled_event_id=1,
        started_event_id=2,
        identity="worker",
        activity_type="process_version_activity",
        activity_id="activity-1",
        retry_state=RetryState.MAXIMUM_ATTEMPTS_REACHED,
    )
    failure.__cause__ = ApplicationError("provider content filter")
    execute_activity = AsyncMock(side_effect=failure)
    monkeypatch.setattr(temporal_workflow, "execute_activity", execute_activity)

    result = await workflows._process_version_with_failure_isolation(ProcessInput("tenant-1", "version-1", "run-1"))

    assert result == {
        "source_version_id": "version-1",
        "status": "failed",
        "error_type": "ApplicationError",
        "error": "provider content filter",
    }
    execute_activity.assert_awaited_once()
    assert execute_activity.call_args.kwargs["heartbeat_timeout"] == timedelta(minutes=30)


@pytest.mark.asyncio
async def test_reprocess_workflow_has_bounded_heartbeat_and_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_activity = AsyncMock(return_value={"status": "succeeded"})
    monkeypatch.setattr(temporal_workflow, "execute_activity", execute_activity)

    result = await workflows.SourceVersionReprocessWorkflow().run(ProcessInput("tenant-1", "version-1"))

    assert result == {"status": "succeeded"}
    execute_activity.assert_awaited_once()
    assert execute_activity.call_args.kwargs["heartbeat_timeout"] == timedelta(minutes=30)
    assert (
        execute_activity.call_args.kwargs["cancellation_type"] == ActivityCancellationType.WAIT_CANCELLATION_COMPLETED
    )


@pytest.mark.asyncio
async def test_source_ingestion_serializes_remote_governance_activity_per_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = 0
    maximum_active = 0
    processed: list[str] = []

    async def execute_activity(activity: object, payload: object, **_kwargs: object) -> dict[str, object]:
        nonlocal active, maximum_active
        if activity is scan_source_activity:
            return {"run_id": "run-1", "version_ids": ["version-1", "version-2", "version-3"]}
        assert isinstance(payload, ProcessInput)
        assert payload.from_stage == "auto"
        active += 1
        maximum_active = max(maximum_active, active)
        processed.append(payload.source_version_id)
        await asyncio.sleep(0)
        active -= 1
        return {"source_version_id": payload.source_version_id, "status": "succeeded"}

    monkeypatch.setattr(temporal_workflow, "execute_activity", execute_activity)

    result = await workflows.DataSourceIngestionWorkflow().run(ScanInput("tenant-1", "source-1", "workflow-1"))

    assert result["scan"] == {"run_id": "run-1", "version_ids": ["version-1", "version-2", "version-3"]}
    assert processed == ["version-1", "version-2", "version-3"]
    assert maximum_active == 1
