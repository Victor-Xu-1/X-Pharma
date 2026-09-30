from __future__ import annotations

import signal
import threading

import structlog

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory
from pharma_intel.object_store import build_object_store
from pharma_intel.runtime_heartbeat import RuntimeHeartbeat
from pharma_intel.search.client import get_opensearch_gateway
from pharma_intel.search.maintenance import ProjectionMaintenanceWorker
from pharma_intel.telemetry import initialize_telemetry

logger = structlog.get_logger(__name__)


def serve(stopping: threading.Event) -> None:
    settings = get_settings()
    if not settings.search_projection_enabled:
        raise RuntimeError("SEARCH_PROJECTION_ENABLED must be true to start search maintenance")
    gateway = get_opensearch_gateway()
    initialized = gateway.ensure_indices()
    worker = ProjectionMaintenanceWorker(
        get_session_factory(),
        gateway,
        build_object_store(settings),
        settings,
    )
    logger.info("search_maintenance_started", indexes=initialized)
    with RuntimeHeartbeat("search-maintenance") as heartbeat:
        while not stopping.is_set():
            job = worker.process_once()
            heartbeat.beat()
            if job is not None:
                logger.info(
                    "search_projection_maintenance",
                    job_id=job.id,
                    operation=job.operation,
                    status=job.status,
                )
                continue
            stopping.wait(settings.search_projection_poll_seconds)
    logger.info("search_maintenance_stopped")


def run() -> None:
    initialize_telemetry("pharma-search-maintenance")
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    serve(stopping)


if __name__ == "__main__":
    run()
