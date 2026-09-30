from __future__ import annotations

import signal
import threading

import structlog

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory
from pharma_intel.monitoring.consumer import MonitoringConsumer
from pharma_intel.quality.worker import DataQualityWorker
from pharma_intel.runtime_heartbeat import RuntimeHeartbeat
from pharma_intel.telemetry import initialize_telemetry

logger = structlog.get_logger(__name__)


def serve(stopping: threading.Event) -> None:
    settings = get_settings()
    if not settings.monitoring_enabled:
        raise RuntimeError("MONITORING_ENABLED must be true to start the monitoring worker")
    consumer = MonitoringConsumer(get_session_factory(), settings)
    quality = DataQualityWorker(get_session_factory(), settings)
    logger.info("monitoring_worker_started")
    with RuntimeHeartbeat("monitoring-worker") as heartbeat:
        while not stopping.is_set():
            result = consumer.drain_once()
            quality_snapshot = quality.process_once()
            heartbeat.beat()
            if quality_snapshot is not None:
                logger.info(
                    "data_quality_snapshot",
                    snapshot_id=quality_snapshot.id,
                    measured_at=quality_snapshot.measured_at.isoformat(),
                )
            if result.processed:
                logger.info(
                    "monitoring_batch",
                    processed=result.processed,
                    succeeded=result.succeeded,
                    retried=result.retried,
                    dead=result.dead,
                )
                continue
            stopping.wait(settings.monitoring_poll_seconds)
    logger.info("monitoring_worker_stopped")


def run() -> None:
    initialize_telemetry("pharma-monitoring-worker")
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    serve(stopping)
