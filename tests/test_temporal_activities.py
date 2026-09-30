from __future__ import annotations

import asyncio
import threading
from contextlib import nullcontext

import anyio
import pytest
from temporalio.exceptions import ApplicationError

from pharma_intel.governance.service import GovernanceError
from pharma_intel.ingest.activities import event_loop_heartbeat, process_version_activity
from pharma_intel.ingest.contracts import ProcessInput


@pytest.mark.anyio
async def test_threaded_scanner_heartbeat_is_dispatched_on_worker_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_loop_thread = threading.get_ident()
    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(
        "pharma_intel.ingest.activities.activity.heartbeat",
        lambda payload: calls.append((threading.get_ident(), payload)),
    )
    heartbeat = event_loop_heartbeat(asyncio.get_running_loop())

    await anyio.to_thread.run_sync(lambda: heartbeat("paper.md"))
    await asyncio.sleep(0)

    assert calls == [(event_loop_thread, {"path": "paper.md"})]


@pytest.mark.anyio
async def test_governance_policy_failure_is_non_retryable_at_temporal_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingDataFactory:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def process_version(
            self,
            source_version_id: str,
            ingestion_run_id: str | None = None,
            from_stage: str = "malware_scan",
        ) -> None:
            assert ingestion_run_id is None
            assert from_stage == "malware_scan"
            raise GovernanceError(f"policy rejected {source_version_id}")

    monkeypatch.setattr("pharma_intel.ingest.activities.get_settings", object)
    monkeypatch.setattr("pharma_intel.ingest.activities.get_session_factory", lambda: lambda: nullcontext(object()))
    monkeypatch.setattr("pharma_intel.ingest.activities.build_object_store", lambda _settings: object())
    monkeypatch.setattr("pharma_intel.ingest.activities.DataFactoryService", FailingDataFactory)

    with pytest.raises(ApplicationError) as captured:
        await process_version_activity(ProcessInput("tenant-1", "version-1"))

    assert captured.value.non_retryable is True
    assert captured.value.type == "GovernancePolicyError"
