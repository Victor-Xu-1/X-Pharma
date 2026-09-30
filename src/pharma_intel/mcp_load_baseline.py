from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

MCP_PROTOCOL_BASELINE = "2025-11-25"
QUERY_MIX = ("EGFR", "HER2", "KRAS", "TP53", "BTK")


class ToolCallError(RuntimeError):
    pass


@dataclass(frozen=True)
class CallSample:
    latency_ms: float
    settlement_id: str


def _units(summary: dict[str, Any], field: str) -> Decimal:
    value = summary.get(field)
    if not isinstance(value, str):
        raise RuntimeError(f"Usage summary omitted {field}")
    return Decimal(value)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def _structured(result: Any) -> dict[str, Any]:
    if result.isError:
        raise ToolCallError(_tool_error_message(result))
    payload = result.structuredContent
    if payload is None:
        if not result.content or not isinstance(result.content[0], TextContent):
            raise RuntimeError("MCP tool returned no structured content")
        payload = json.loads(result.content[0].text)
    if not isinstance(payload, dict):
        raise RuntimeError("MCP tool returned a non-object payload")
    return payload


def _tool_error_message(result: Any) -> str:
    if result.content and isinstance(result.content[0], TextContent):
        return result.content[0].text[:1000]
    return "MCP tool returned an error"


async def _open_session(url: str, token: str) -> Any:
    http_client = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(30),
        follow_redirects=True,
        trust_env=False,
    )
    transport = streamable_http_client(url, http_client=http_client)
    return http_client, transport


async def _usage_summary(url: str, token: str) -> tuple[dict[str, Any], str]:
    http_client, transport = await _open_session(url, token)
    async with http_client:
        async with transport as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                summary = _structured(await session.call_tool("get_usage_summary", {}))
                return summary, str(initialization.protocolVersion)


async def _call_tool_result(url: str, token: str, name: str, arguments: dict[str, Any]) -> Any:
    http_client, transport = await _open_session(url, token)
    async with http_client:
        async with transport as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                if str(initialization.protocolVersion) != MCP_PROTOCOL_BASELINE:
                    raise RuntimeError("MCP protocol changed during commercial acceptance")
                return await session.call_tool(name, arguments)


async def _call_tool(url: str, token: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return _structured(await _call_tool_result(url, token, name, arguments))


async def _expect_tool_error(url: str, token: str, name: str, arguments: dict[str, Any]) -> str:
    http_client, transport = await _open_session(url, token)
    async with http_client:
        async with transport as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                if str(initialization.protocolVersion) != MCP_PROTOCOL_BASELINE:
                    raise RuntimeError("MCP protocol changed during expected-failure probe")
                result = await session.call_tool(name, arguments)
                if not result.isError:
                    raise RuntimeError(f"{name} unexpectedly succeeded")
                return _tool_error_message(result)


async def _cancellation_probe(url: str, token: str, idempotency_key: str) -> dict[str, Any]:
    http_client, transport = await _open_session(url, token)
    async with http_client:
        async with transport as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                if str(initialization.protocolVersion) != MCP_PROTOCOL_BASELINE:
                    raise RuntimeError("MCP protocol changed during cancellation probe")
                task = asyncio.create_task(
                    session.call_tool(
                        "search_entities",
                        {
                            "query": "cancellation-probe-EGFR",
                            "limit": 5,
                            "idempotency_key": idempotency_key,
                            "max_billable_units": "100",
                        },
                    )
                )
                await asyncio.sleep(0.025)
                cancellation_requested = task.cancel()
                try:
                    payload = _structured(await task)
                except asyncio.CancelledError:
                    return {"cancellation_requested": cancellation_requested, "outcome": "cancelled"}
                except ToolCallError as exc:
                    return {
                        "cancellation_requested": cancellation_requested,
                        "outcome": "failed",
                        "message": str(exc)[:1000],
                    }
                usage = payload.get("usage")
                if not isinstance(usage, dict) or not isinstance(usage.get("settlement_id"), str):
                    raise RuntimeError("Completed cancellation probe omitted settlement metadata")
                return {
                    "cancellation_requested": cancellation_requested,
                    "outcome": "settled",
                    "settlement_id": usage["settlement_id"],
                }


async def _timeout_probe(url: str, token: str, idempotency_key: str) -> dict[str, Any]:
    arguments = {
        "query": "timeout-probe-HER2",
        "limit": 5,
        "idempotency_key": idempotency_key,
        "max_billable_units": "100",
    }
    http_client, transport = await _open_session(url, token)
    timed_out = False
    initial_settlement: str | None = None
    async with http_client:
        async with transport as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                if str(initialization.protocolVersion) != MCP_PROTOCOL_BASELINE:
                    raise RuntimeError("MCP protocol changed during timeout probe")
                try:
                    async with asyncio.timeout(0.025):
                        payload = _structured(await session.call_tool("search_entities", arguments))
                    usage = payload.get("usage")
                    if not isinstance(usage, dict) or not isinstance(usage.get("settlement_id"), str):
                        raise RuntimeError("Completed timeout probe omitted settlement metadata")
                    initial_settlement = usage["settlement_id"]
                except TimeoutError:
                    timed_out = True

    recovery_started = time.perf_counter()
    reserved_retries = 0
    replay: dict[str, Any] | None = None
    while time.perf_counter() - recovery_started < 10:
        await asyncio.sleep(0.2)
        try:
            replay = await _call_tool(url, token, "search_entities", arguments)
            break
        except ToolCallError as exc:
            message = str(exc)[:1000]
            normalized = message.casefold()
            if "already reserved" in normalized:
                reserved_retries += 1
                continue
            if "already released" in normalized:
                return {
                    "timeout_observed": timed_out,
                    "outcome": "released",
                    "replay_rejected_as_released": True,
                    "reserved_retries": reserved_retries,
                    "recovery_seconds": round(time.perf_counter() - recovery_started, 6),
                }
            raise RuntimeError("Timeout replay failed without a durable terminal state") from exc
    if replay is None:
        raise RuntimeError("Timeout replay remained reserved beyond the recovery deadline")
    replay_usage = replay.get("usage")
    if not isinstance(replay_usage, dict) or not isinstance(replay_usage.get("settlement_id"), str):
        raise RuntimeError("Timeout replay omitted settlement metadata")
    return {
        "timeout_observed": timed_out,
        "outcome": "replay_settled" if timed_out else "settled_before_deadline",
        "settlement_id": replay_usage["settlement_id"],
        "same_settlement": initial_settlement is None or initial_settlement == replay_usage["settlement_id"],
        "replay_flag": replay_usage.get("replayed") is True,
        "reserved_retries": reserved_retries,
        "recovery_seconds": round(time.perf_counter() - recovery_started, 6),
    }


async def execute_resilience(url: str, token: str) -> dict[str, Any]:
    before, protocol_version = await _usage_summary(url, token)
    replay_key = f"resilience-replay-{uuid.uuid4().hex}"
    replay_arguments = {
        "query": "EGFR",
        "limit": 5,
        "idempotency_key": replay_key,
        "max_billable_units": "100",
    }
    first = await _call_tool(url, token, "search_entities", replay_arguments)
    replay = await _call_tool(url, token, "search_entities", replay_arguments)
    first_usage = first.get("usage")
    replay_usage = replay.get("usage")
    if not isinstance(first_usage, dict) or not isinstance(replay_usage, dict):
        raise RuntimeError("Idempotency probe omitted usage metadata")

    conflict_arguments = {**replay_arguments, "query": "KRAS"}
    conflict_error = await _expect_tool_error(url, token, "search_entities", conflict_arguments)
    domain_error = await _expect_tool_error(
        url,
        token,
        "get_entity",
        {
            "entity_id": "00000000-0000-0000-0000-000000000000",
            "idempotency_key": f"resilience-domain-failure-{uuid.uuid4().hex}",
            "max_billable_units": "100",
        },
    )
    budget_error = await _expect_tool_error(
        url,
        token,
        "search_entities",
        {
            "query": "BTK",
            "limit": 5,
            "idempotency_key": f"resilience-budget-{uuid.uuid4().hex}",
            "max_billable_units": "0",
        },
    )
    cancellation = await _cancellation_probe(
        url,
        token,
        f"resilience-cancel-{uuid.uuid4().hex}",
    )
    timeout = await _timeout_probe(
        url,
        token,
        f"resilience-timeout-{uuid.uuid4().hex}",
    )
    await asyncio.sleep(0.5)
    after, after_protocol_version = await _usage_summary(url, token)

    first_settlement = first_usage.get("settlement_id")
    replay_settlement = replay_usage.get("settlement_id")
    cancellation_settlements = 1 if cancellation["outcome"] == "settled" else 0
    timeout_settlements = 0 if timeout["outcome"] == "released" else 1
    settlement_delta = int(after["settlement_count"]) - int(before["settlement_count"])
    charged_delta = _units(after, "charged_units") - _units(before, "charged_units")
    consumed_delta = _units(after, "consumed_units") - _units(before, "consumed_units")
    balance_identity = _units(after, "available_units") == _units(after, "granted_units") - _units(
        after, "consumed_units"
    ) - _units(after, "reserved_units")
    assertions = {
        "idempotent_replay_reuses_settlement": (
            isinstance(first_settlement, str)
            and first_settlement == replay_settlement
            and replay_usage.get("replayed") is True
        ),
        "idempotency_argument_conflict_rejected": bool(conflict_error),
        "domain_failure_rejected": bool(domain_error),
        "insufficient_budget_rejected": bool(budget_error),
        "cancellation_was_requested": cancellation["cancellation_requested"] is True,
        "timeout_was_observed": timeout["timeout_observed"] is True,
        "timeout_reached_a_durable_terminal_state": timeout["outcome"] in {"released", "replay_settled"},
        "settlement_delta_matches_durable_successes": (
            settlement_delta == 1 + cancellation_settlements + timeout_settlements
        ),
        "charged_and_consumed_deltas_match": charged_delta == consumed_delta,
        "no_active_reservations_after_failures": int(after["active_reservations"]) == 0,
        "reserved_units_returned_to_zero": _units(after, "reserved_units") == Decimal("0"),
        "balance_identity_holds": balance_identity,
        "protocol_baseline_negotiated": protocol_version == after_protocol_version == MCP_PROTOCOL_BASELINE,
    }
    return {
        "idempotency": {
            "same_settlement": first_settlement == replay_settlement,
            "replay_flag": replay_usage.get("replayed") is True,
            "argument_conflict_rejected": bool(conflict_error),
        },
        "failure_release": {
            "domain_failure_rejected": bool(domain_error),
            "budget_failure_rejected": bool(budget_error),
            "active_reservations_after": int(after["active_reservations"]),
            "reserved_units_after": str(_units(after, "reserved_units")),
        },
        "cancellation": cancellation,
        "timeout": timeout,
        "reconciliation": {
            "settlement_delta": settlement_delta,
            "charged_units_delta": str(charged_delta),
            "consumed_units_delta": str(consumed_delta),
            "balance_identity_holds": balance_identity,
        },
        "assertions": assertions,
    }


async def _worker(
    worker_id: int,
    *,
    url: str,
    token: str,
    total_requests: int,
    concurrency: int,
    samples: list[CallSample],
    errors: list[dict[str, Any]],
) -> None:
    http_client, transport = await _open_session(url, token)
    async with http_client:
        async with transport as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                initialization = await session.initialize()
                negotiated_protocol = str(initialization.protocolVersion)
                if negotiated_protocol != MCP_PROTOCOL_BASELINE:
                    raise RuntimeError(f"MCP protocol mismatch: {negotiated_protocol} != {MCP_PROTOCOL_BASELINE}")
                for request_index in range(worker_id, total_requests, concurrency):
                    started = time.perf_counter()
                    try:
                        payload = _structured(
                            await session.call_tool(
                                "search_entities",
                                {
                                    "query": QUERY_MIX[request_index % len(QUERY_MIX)],
                                    "limit": 5,
                                    "idempotency_key": f"load-{uuid.uuid4().hex}",
                                    "max_billable_units": "100",
                                },
                            )
                        )
                        usage = payload.get("usage")
                        if not isinstance(usage, dict) or not isinstance(usage.get("settlement_id"), str):
                            raise RuntimeError("Successful billable call omitted settlement_id")
                        samples.append(
                            CallSample(
                                latency_ms=(time.perf_counter() - started) * 1000,
                                settlement_id=usage["settlement_id"],
                            )
                        )
                    except Exception as exc:  # noqa: BLE001 - the load report must retain every failed call
                        errors.append(
                            {
                                "request_index": request_index,
                                "worker_id": worker_id,
                                "error_type": type(exc).__name__,
                                "message": str(exc)[:1000],
                            }
                        )


async def execute_baseline(url: str, token: str, total_requests: int, concurrency: int) -> dict[str, Any]:
    before, protocol_version = await _usage_summary(url, token)
    samples: list[CallSample] = []
    errors: list[dict[str, Any]] = []
    started_at = datetime.now(UTC)
    started = time.perf_counter()
    await asyncio.gather(
        *(
            _worker(
                worker_id,
                url=url,
                token=token,
                total_requests=total_requests,
                concurrency=concurrency,
                samples=samples,
                errors=errors,
            )
            for worker_id in range(concurrency)
        )
    )
    duration_seconds = time.perf_counter() - started
    finished_at = datetime.now(UTC)
    after, after_protocol_version = await _usage_summary(url, token)
    latencies = [sample.latency_ms for sample in samples]
    settlement_ids = [sample.settlement_id for sample in samples]
    settlement_delta = int(after["settlement_count"]) - int(before["settlement_count"])
    active_reservations = int(after["active_reservations"])
    completed = len(samples)
    assertions = {
        "all_requests_succeeded": completed == total_requests and not errors,
        "one_unique_settlement_per_success": len(set(settlement_ids)) == completed,
        "ledger_delta_covers_successes": settlement_delta >= completed,
        "no_active_reservations_after_run": active_reservations == 0,
        "protocol_baseline_negotiated": protocol_version == after_protocol_version == MCP_PROTOCOL_BASELINE,
    }
    return {
        "schema": "pharma.mcp-commercial-acceptance.v2",
        "schema_version": "1.0",
        "status": "passed" if all(assertions.values()) else "failed",
        "environment": "local-or-ci-controlled-baseline",
        "production_claim": False,
        "credentials_recorded": False,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "protocol_version": protocol_version,
        "requests": {
            "requested": total_requests,
            "completed": completed,
            "failed": len(errors),
            "concurrency": concurrency,
            "duration_seconds": round(duration_seconds, 6),
            "throughput_rps": round(completed / duration_seconds, 3) if duration_seconds else 0.0,
        },
        "latency_ms": {
            "minimum": round(min(latencies), 3) if latencies else 0.0,
            "p50": round(percentile(latencies, 0.50), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "p99": round(percentile(latencies, 0.99), 3),
            "maximum": round(max(latencies), 3) if latencies else 0.0,
        },
        "billing": {
            "settlements_before": int(before["settlement_count"]),
            "settlements_after": int(after["settlement_count"]),
            "settlement_delta": settlement_delta,
            "unique_settlement_ids": len(set(settlement_ids)),
            "active_reservations_after": active_reservations,
        },
        "assertions": assertions,
        "errors": errors[:100],
    }


async def execute_commercial_acceptance(
    url: str,
    token: str,
    total_requests: int,
    concurrency: int,
) -> dict[str, Any]:
    report = await execute_baseline(url, token, total_requests, concurrency)
    report["schema_version"] = "2.0"
    report["resilience"] = await execute_resilience(url, token)
    report["status"] = (
        "passed"
        if all(report["assertions"].values()) and all(report["resilience"]["assertions"].values())
        else "failed"
    )
    return report


def _write_report(path: Path, report: dict[str, Any]) -> None:
    parent = path.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / path.name
    if target.exists() or target.is_symlink():
        raise RuntimeError(f"Commercial acceptance report already exists: {target}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.link(temporary, target, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)


def run() -> None:
    parser = argparse.ArgumentParser(description="Run a bounded, billed MCP concurrency baseline")
    parser.add_argument("--url", default="http://127.0.0.1:8090/mcp")
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--max-p95-ms", type=float, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.requests < 1 or args.requests > 10_000:
        parser.error("--requests must be between 1 and 10000")
    if args.concurrency < 1 or args.concurrency > min(args.requests, 200):
        parser.error("--concurrency must be between 1 and min(requests, 200)")
    token = os.environ.get("TEST_MCP_ACCESS_TOKEN", "")
    if not token:
        parser.error("TEST_MCP_ACCESS_TOKEN is required")
    report = asyncio.run(execute_commercial_acceptance(args.url, token, args.requests, args.concurrency))
    if args.output:
        _write_report(args.output, report)
    print(json.dumps(report, sort_keys=True))
    assertions = report["assertions"]
    p95 = float(report["latency_ms"]["p95"])
    resilience_assertions = report["resilience"]["assertions"]
    if (
        not all(assertions.values())
        or not all(resilience_assertions.values())
        or (args.max_p95_ms and p95 > args.max_p95_ms)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    run()
