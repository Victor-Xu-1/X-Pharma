from __future__ import annotations

import argparse
import json
import signal
import threading
from collections.abc import Iterator
from contextlib import contextmanager

import structlog
from sqlalchemy.orm import sessionmaker

from pharma_intel.commercial.billing import HttpBillingProviderAdapter
from pharma_intel.commercial.billing_consumer import BillingProviderConsumer
from pharma_intel.config import Settings, get_billing_worker_settings
from pharma_intel.db import create_engine_from_settings
from pharma_intel.runtime_heartbeat import RuntimeHeartbeat
from pharma_intel.telemetry import initialize_telemetry

logger = structlog.get_logger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deliver immutable billing statements to the configured provider")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--once", action="store_true", help="Drain one bounded batch and exit")
    actions.add_argument("--status", action="store_true", help="Print delivery counts and exit")
    actions.add_argument("--retry-dead", action="store_true", help="Requeue dead deliveries and exit")
    parser.add_argument("--tenant-id", help="Limit --retry-dead to one tenant ID")
    return parser


def main(arguments: list[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    if args.tenant_id and not args.retry_dead:
        raise SystemExit("--tenant-id requires --retry-dead")
    settings = get_billing_worker_settings()
    if not settings.billing_provider_enabled:
        raise RuntimeError("BILLING_PROVIDER_ENABLED must be true to start the billing provider worker")

    with _consumer_context(settings, telemetry_service="pharma-billing-provider") as consumer:
        return _execute(args, consumer, settings)


@contextmanager
def _consumer_context(
    settings: Settings,
    *,
    telemetry_service: str | None,
) -> Iterator[BillingProviderConsumer]:
    engine = create_engine_from_settings(settings)
    try:
        if telemetry_service is not None:
            initialize_telemetry(telemetry_service, settings=settings, engine=engine)
        verify: bool | str = settings.billing_provider_ca_certs or settings.billing_provider_verify_certs
        adapter = HttpBillingProviderAdapter(
            provider=settings.billing_provider_name,
            base_url=settings.billing_provider_base_url,
            api_token=settings.billing_provider_api_token,
            connect_timeout_seconds=settings.billing_provider_connect_timeout_seconds,
            request_timeout_seconds=settings.billing_provider_request_timeout_seconds,
            verify=verify,
            max_response_bytes=settings.billing_provider_max_response_bytes,
            max_metadata_bytes=settings.billing_provider_max_metadata_bytes,
        )
        consumer = BillingProviderConsumer(sessionmaker(bind=engine, expire_on_commit=False), adapter, settings)
        yield consumer
    finally:
        engine.dispose()


def _execute(args: argparse.Namespace, consumer: BillingProviderConsumer, settings: Settings) -> int:
    if args.status:
        print(json.dumps(consumer.delivery_counts(), sort_keys=True))
        return 0
    if args.retry_dead:
        print(json.dumps({"requeued": consumer.retry_dead(args.tenant_id)}, sort_keys=True))
        return 0
    if args.once:
        result = consumer.drain_once()
        print(json.dumps(result.__dict__, sort_keys=True))
        return int(result.dead > 0)
    stopping = threading.Event()

    def stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    _run_loop(consumer, settings, stopping)
    return 0


def _run_loop(
    consumer: BillingProviderConsumer,
    settings: Settings,
    stopping: threading.Event,
) -> None:
    logger.info("billing_provider_worker_started", provider=settings.billing_provider_name)
    with RuntimeHeartbeat("billing-provider") as heartbeat:
        while not stopping.is_set():
            result = consumer.drain_once()
            heartbeat.beat()
            if result.processed:
                logger.info(
                    "billing_provider_batch",
                    processed=result.processed,
                    succeeded=result.succeeded,
                    retried=result.retried,
                    dead=result.dead,
                )
                continue
            stopping.wait(settings.billing_provider_poll_seconds)
    logger.info("billing_provider_worker_stopped")


def serve(stopping: threading.Event) -> None:
    settings = get_billing_worker_settings()
    if not settings.billing_provider_enabled:
        raise RuntimeError("BILLING_PROVIDER_ENABLED must be true to start the billing provider worker")
    with _consumer_context(settings, telemetry_service=None) as consumer:
        _run_loop(consumer, settings, stopping)


def run() -> None:
    raise SystemExit(main())
