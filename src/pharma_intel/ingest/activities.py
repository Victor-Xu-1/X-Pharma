from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

import anyio
from temporalio import activity
from temporalio.exceptions import ApplicationError

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory
from pharma_intel.governance.service import GovernanceError
from pharma_intel.ingest.contracts import ProcessInput, ScanInput
from pharma_intel.ingest.data_factory import (
    DataFactoryService,
    IngestionRunCanceled,
    SourceVersionReplayRejected,
)
from pharma_intel.object_store import build_object_store


def event_loop_heartbeat(loop: asyncio.AbstractEventLoop) -> Callable[[str], None]:
    def send(path: str) -> None:
        loop.call_soon_threadsafe(activity.heartbeat, {"path": path})

    return send


@activity.defn
async def scan_source_activity(payload: ScanInput) -> dict[str, Any]:
    heartbeat = event_loop_heartbeat(asyncio.get_running_loop())
    info = activity.info()

    def execute() -> dict[str, Any]:
        settings = get_settings()
        with get_session_factory()() as session:
            service = DataFactoryService(
                session,
                settings,
                build_object_store(settings),
                payload.tenant_id,
                heartbeat=heartbeat,
            )
            return asdict(
                service.scan_source(
                    payload.data_source_id,
                    payload.workflow_id,
                    temporal_workflow_id=info.workflow_id,
                    temporal_run_id=info.workflow_run_id,
                )
            )

    return await anyio.to_thread.run_sync(execute)


@activity.defn
async def process_version_activity(payload: ProcessInput) -> dict[str, Any]:
    heartbeat = event_loop_heartbeat(asyncio.get_running_loop())

    def execute() -> dict[str, Any]:
        settings = get_settings()
        with get_session_factory()() as session:
            try:
                result = DataFactoryService(
                    session,
                    settings,
                    build_object_store(settings),
                    payload.tenant_id,
                    heartbeat=heartbeat,
                ).process_version(payload.source_version_id, payload.ingestion_run_id, payload.from_stage)
            except IngestionRunCanceled as exc:
                raise ApplicationError(
                    str(exc),
                    type="IngestionRunCanceled",
                    non_retryable=True,
                ) from exc
            except GovernanceError as exc:
                raise ApplicationError(
                    str(exc),
                    type="GovernancePolicyError",
                    non_retryable=True,
                ) from exc
            except SourceVersionReplayRejected as exc:
                raise ApplicationError(
                    str(exc),
                    type="SourceVersionReplayRejected",
                    non_retryable=True,
                ) from exc
            return asdict(result)

    return await anyio.to_thread.run_sync(execute)
