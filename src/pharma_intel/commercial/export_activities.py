from __future__ import annotations

from typing import Any

import anyio
from temporalio import activity

from pharma_intel.commercial.export_contracts import ExportFailureInput, ExportInput
from pharma_intel.commercial.exports import (
    build_export_service,
    export_job_view,
)
from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory, set_tenant_context


@activity.defn
async def execute_export_activity(payload: ExportInput) -> dict[str, Any]:
    def execute() -> dict[str, Any]:
        settings = get_settings()
        with get_session_factory()() as session:
            set_tenant_context(session, payload.tenant_id)
            job = build_export_service(session, settings).execute(payload.tenant_id, payload.job_id)
            return export_job_view(job)

    return await anyio.to_thread.run_sync(execute)


@activity.defn
async def fail_export_activity(payload: ExportFailureInput) -> dict[str, Any]:
    def execute() -> dict[str, Any]:
        settings = get_settings()
        with get_session_factory()() as session:
            set_tenant_context(session, payload.tenant_id)
            job = build_export_service(session, settings).fail(
                payload.tenant_id,
                payload.job_id,
                code=payload.code,
                message=payload.message,
            )
            return export_job_view(job)

    return await anyio.to_thread.run_sync(execute)
