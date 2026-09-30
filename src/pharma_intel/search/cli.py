from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import datetime
from typing import Any

from pharma_intel.config import get_settings
from pharma_intel.db import get_session_factory
from pharma_intel.object_store import build_object_store
from pharma_intel.search.client import get_opensearch_gateway
from pharma_intel.search.projector import SearchProjectionConsumer
from pharma_intel.search.rebuild import SearchRebuilder

BUILD_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pharma-search", description="OpenSearch projection operations")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ensure", help="Install templates and create initial aliases")
    commands.add_parser("status", help="Show cluster, alias and delivery status")
    drain = commands.add_parser("drain", help="Project due transactional outbox events")
    drain.add_argument("--max-batches", type=int, default=1000)
    rebuild = commands.add_parser("rebuild", help="Rebuild every projection and atomically switch aliases")
    rebuild.add_argument("--build-id")
    retry = commands.add_parser("retry-dead", help="Explicitly replay dead-letter deliveries")
    retry.add_argument("--tenant-id")
    return parser


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def run() -> None:
    args = _parser().parse_args()
    settings = get_settings()
    gateway = get_opensearch_gateway()
    object_store = build_object_store(settings)
    consumer = SearchProjectionConsumer(get_session_factory(), gateway, object_store, settings)
    output: dict[str, Any]
    if args.command == "ensure":
        output = {"indexes": gateway.ensure_indices()}
    elif args.command == "status":
        output = {"cluster": asdict(gateway.status()), "deliveries": consumer.delivery_counts()}
    elif args.command == "drain":
        if not 1 <= args.max_batches <= 100_000:
            raise SystemExit("--max-batches must be between 1 and 100000")
        gateway.ensure_indices()
        output = {"result": asdict(consumer.drain(args.max_batches))}
    elif args.command == "retry-dead":
        output = {"reset": consumer.retry_dead(args.tenant_id)}
    elif args.command == "rebuild":
        if args.build_id and not BUILD_ID_PATTERN.fullmatch(args.build_id):
            raise SystemExit("--build-id must contain 3-80 lowercase letters, digits or hyphens")
        result = SearchRebuilder(
            get_session_factory(),
            gateway,
            object_store,
            settings,
        ).rebuild(args.build_id)
        output = {"result": asdict(result)}
    else:
        raise SystemExit(f"Unsupported command: {args.command}")
    print(json.dumps(output, ensure_ascii=True, sort_keys=True, default=_json_default))


if __name__ == "__main__":
    run()
