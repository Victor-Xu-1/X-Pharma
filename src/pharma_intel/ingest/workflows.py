from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError
from temporalio.workflow import ActivityCancellationType

from pharma_intel.ingest.contracts import ProcessInput, ScanInput

# Governance runs after parsing in the same activity and uses a remote provider
# quota. Keep one version in flight per source workflow; deployment-level worker
# limits still bound concurrency across independent workflows.
PROCESS_VERSION_BATCH_SIZE = 1
# A bounded remote-model request may include several HTTP attempts; the activity
# heartbeat must outlive that budget while the two-hour execution timeout remains the hard ceiling.
PROCESS_VERSION_ACTIVITY_HEARTBEAT_TIMEOUT = timedelta(minutes=30)

with workflow.unsafe.imports_passed_through():
    from pharma_intel.ingest.activities import (
        process_version_activity,
        scan_source_activity,
    )


async def _process_version_with_failure_isolation(payload: ProcessInput) -> dict[str, Any]:
    try:
        return await workflow.execute_activity(
            process_version_activity,
            payload,
            start_to_close_timeout=timedelta(hours=2),
            heartbeat_timeout=PROCESS_VERSION_ACTIVITY_HEARTBEAT_TIMEOUT,
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=10),
                backoff_coefficient=2,
                maximum_interval=timedelta(minutes=10),
                maximum_attempts=3,
            ),
        )
    except ActivityError as exc:
        cause = exc.cause or exc
        return {
            "source_version_id": payload.source_version_id,
            "status": "failed",
            "error_type": type(cause).__name__,
            "error": str(cause)[:500],
        }


@workflow.defn
class DataSourceIngestionWorkflow:
    @workflow.run
    async def run(self, payload: ScanInput) -> dict[str, Any]:
        scan = await workflow.execute_activity(
            scan_source_activity,
            payload,
            start_to_close_timeout=timedelta(hours=12),
            heartbeat_timeout=timedelta(minutes=5),
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2,
                maximum_interval=timedelta(minutes=5),
                maximum_attempts=5,
            ),
        )
        results: list[dict[str, Any]] = []
        ingestion_run_id = str(scan["run_id"])
        version_ids = [str(value) for value in scan.get("version_ids", [])]
        for offset in range(0, len(version_ids), PROCESS_VERSION_BATCH_SIZE):
            batch = version_ids[offset : offset + PROCESS_VERSION_BATCH_SIZE]
            batch_results = await asyncio.gather(
                *(
                    _process_version_with_failure_isolation(
                        ProcessInput(payload.tenant_id, version_id, ingestion_run_id, from_stage="auto")
                    )
                    for version_id in batch
                )
            )
            results.extend(batch_results)
        return {"scan": scan, "versions": results}


@workflow.defn
class SourceVersionReprocessWorkflow:
    @workflow.run
    async def run(self, payload: ProcessInput) -> dict[str, Any]:
        return await workflow.execute_activity(
            process_version_activity,
            payload,
            start_to_close_timeout=timedelta(hours=2),
            heartbeat_timeout=PROCESS_VERSION_ACTIVITY_HEARTBEAT_TIMEOUT,
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=10),
                backoff_coefficient=2,
                maximum_interval=timedelta(minutes=10),
                maximum_attempts=3,
            ),
        )
