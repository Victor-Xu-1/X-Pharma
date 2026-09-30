from __future__ import annotations

import signal
import threading

import structlog

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory
from pharma_intel.object_store import build_object_store
from pharma_intel.runtime_heartbeat import RuntimeHeartbeat
from pharma_intel.search.client import get_opensearch_gateway
from pharma_intel.search.projector import SearchProjectionConsumer
from pharma_intel.telemetry import initialize_telemetry

logger = structlog.get_logger(__name__)


def serve(stopping: threading.Event) -> None:
    settings = get_settings()
    if not settings.search_projection_enabled:
        raise RuntimeError("SEARCH_PROJECTION_ENABLED must be true to start the OpenSearch projector")
    gateway = get_opensearch_gateway()
    initialized = gateway.ensure_indices()
    consumer = SearchProjectionConsumer(
        get_session_factory(),
        gateway,
        build_object_store(settings),
        settings,
    )
    logger.info("search_projector_started", indexes=initialized)
    with RuntimeHeartbeat("search-projector") as heartbeat:
        while not stopping.is_set():
            result = consumer.drain_once()
            heartbeat.beat()
            if result.processed:
                logger.info(
                    "search_projection_batch",
                    processed=result.processed,
                    succeeded=result.succeeded,
                    retried=result.retried,
                    dead=result.dead,
                )
                continue
            stopping.wait(settings.search_projection_poll_seconds)
    logger.info("search_projector_stopped")


def run() -> None:
    initialize_telemetry("pharma-search-projector")
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    serve(stopping)
