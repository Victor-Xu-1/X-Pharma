from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from pharma_intel.commercial.export_contracts import ExportFailureInput, ExportInput

with workflow.unsafe.imports_passed_through():
    from pharma_intel.commercial.export_activities import (
        execute_export_activity,
        fail_export_activity,
    )


@workflow.defn
class GovernedDataExportWorkflow:
    @workflow.run
    async def run(self, payload: ExportInput) -> dict[str, Any]:
        try:
            return await workflow.execute_activity(
                execute_export_activity,
                payload,
                start_to_close_timeout=timedelta(hours=2),
                heartbeat_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    backoff_coefficient=2,
                    maximum_interval=timedelta(minutes=2),
                    maximum_attempts=3,
                ),
            )
        except Exception as exc:
            await workflow.execute_activity(
                fail_export_activity,
                ExportFailureInput(
                    payload.tenant_id,
                    payload.job_id,
                    "export_workflow_failed",
                    str(exc)[:500],
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            raise
