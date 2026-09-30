from __future__ import annotations

import argparse
import json

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory
from pharma_intel.monitoring.consumer import MonitoringConsumer


def run() -> None:
    parser = argparse.ArgumentParser(description="Operate the durable monitoring consumer")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("status")
    drain = subcommands.add_parser("drain")
    drain.add_argument("--max-batches", type=int, default=1000)
    replay = subcommands.add_parser("retry-dead")
    replay.add_argument("--tenant-id")
    args = parser.parse_args()
    consumer = MonitoringConsumer(get_session_factory(), get_settings(), worker_id="monitoring-cli")
    if args.command == "status":
        print(json.dumps(consumer.delivery_counts(), sort_keys=True))
    elif args.command == "drain":
        print(json.dumps(consumer.drain(max_batches=args.max_batches).__dict__, sort_keys=True))
    else:
        print(json.dumps({"reset": consumer.retry_dead(args.tenant_id)}, sort_keys=True))
