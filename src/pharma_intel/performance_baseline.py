from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
from mcp import ClientSession

from pharma_intel.mcp_load_baseline import (
    MCP_PROTOCOL_BASELINE,
    QUERY_MIX,
    _call_tool,
    _call_tool_result,
    _open_session,
    _structured,
    _tool_error_message,
    _units,
    _usage_summary,
    _write_report,
    execute_resilience,
    percentile,
)

REPORT_SCHEMA = "pharma.local-performance-baseline.v1"
EntryKind = Literal["web", "mcp"]


@dataclass(frozen=True)
class RequestSample:
    entry: EntryKind
    latency_ms: float
    settlement_id: str | None = None


def latency_summary(samples: list[RequestSample], entry: EntryKind) -> dict[str, float]:
    values = [sample.latency_ms for sample in samples if sample.entry == entry]
    return {
        "minimum": round(min(values), 3) if values else 0.0,
        "p50": round(percentile(values, 0.50), 3),
        "p95": round(percentile(values, 0.95), 3),
        "p99": round(percentile(values, 0.99), 3),
        "maximum": round(max(values), 3) if values else 0.0,
    }


async def _wait_until_scheduled(started: float, position: int, total: int, minimum_duration: float) -> None:
    if minimum_duration <= 0 or total <= 1:
        return
    target = started + minimum_duration * position / (total - 1)
    delay = target - time.perf_counter()
    if delay > 0:
        await asyncio.sleep(delay)


async def _web_worker(
    worker_id: int,
    *,
    client: httpx.AsyncClient,
    positions: list[int],
    workers: int,
    total_requests: int,
    minimum_duration: float,
    ready: asyncio.Queue[None],
    start_event: asyncio.Event,
    started_box: list[float],
    samples: list[RequestSample],
    errors: list[dict[str, Any]],
) -> None:
    ready.put_nowait(None)
    await start_event.wait()
    for position in positions[worker_id::workers]:
        await _wait_until_scheduled(started_box[0], position, total_requests, minimum_duration)
        started = time.perf_counter()
        try:
            response = await client.get(
                "/api/v1/entities",
                params={"q": QUERY_MIX[position % len(QUERY_MIX)], "limit": 5, "offset": 0},
            )
            if response.status_code != 200:
                raise RuntimeError(f"Web search returned HTTP {response.status_code}")
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise RuntimeError("Web search returned an invalid payload")
            samples.append(RequestSample("web", (time.perf_counter() - started) * 1000))
        except Exception as exc:  # noqa: BLE001 - every load failure belongs in the report
            errors.append(
                {
                    "entry": "web",
                    "position": position,
                    "worker_id": worker_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:1000],
                }
            )


async def _mcp_worker(
    worker_id: int,
    *,
    url: str,
    token: str,
    positions: list[int],
    workers: int,
    total_requests: int,
    minimum_duration: float,
    ready: asyncio.Queue[None],
    start_event: asyncio.Event,
    started_box: list[float],
    samples: list[RequestSample],
    errors: list[dict[str, Any]],
) -> None:
    announced = False
    try:
        http_client, transport = await _open_session(url, token)
        async with http_client:
            async with transport as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialization = await session.initialize()
                    if str(initialization.protocol_version) != MCP_PROTOCOL_BASELINE:
                        raise RuntimeError("MCP protocol mismatch during mixed load")
                    ready.put_nowait(None)
                    announced = True
                    await start_event.wait()
                    for position in positions[worker_id::workers]:
                        await _wait_until_scheduled(started_box[0], position, total_requests, minimum_duration)
                        started = time.perf_counter()
                        try:
                            payload = _structured(
                                await session.call_tool(
                                    "search_entities",
                                    {
                                        "query": QUERY_MIX[position % len(QUERY_MIX)],
                                        "limit": 5,
                                        "idempotency_key": f"performance-{uuid.uuid4().hex}",
                                        "max_billable_units": "100",
                                    },
                                )
                            )
                            usage = payload.get("usage")
                            if not isinstance(usage, dict) or not isinstance(usage.get("settlement_id"), str):
                                raise RuntimeError("MCP load result omitted settlement metadata")
                            samples.append(
                                RequestSample(
                                    "mcp",
                                    (time.perf_counter() - started) * 1000,
                                    usage["settlement_id"],
                                )
                            )
                        except Exception as exc:  # noqa: BLE001 - every load failure belongs in the report
                            errors.append(
                                {
                                    "entry": "mcp",
                                    "position": position,
                                    "worker_id": worker_id,
                                    "error_type": type(exc).__name__,
                                    "message": str(exc)[:1000],
                                }
                            )
    except Exception as exc:  # noqa: BLE001 - session setup failures must not deadlock the coordinator
        errors.append(
            {
                "entry": "mcp",
                "position": None,
                "worker_id": worker_id,
                "error_type": type(exc).__name__,
                "message": str(exc)[:1000],
            }
        )
    finally:
        if not announced:
            ready.put_nowait(None)


async def execute_phase(
    name: str,
    *,
    web: httpx.AsyncClient,
    mcp_url: str,
    token: str,
    total_requests: int,
    concurrency: int,
    minimum_duration: float,
) -> tuple[dict[str, Any], list[RequestSample]]:
    web_positions = [position for position in range(total_requests) if position % 2 == 0]
    mcp_positions = [position for position in range(total_requests) if position % 2 == 1]
    web_workers = min(len(web_positions), max(1, concurrency // 2))
    mcp_workers = min(len(mcp_positions), max(1, concurrency - web_workers))
    worker_count = web_workers + mcp_workers
    ready: asyncio.Queue[None] = asyncio.Queue()
    start_event = asyncio.Event()
    started_box = [0.0]
    samples: list[RequestSample] = []
    errors: list[dict[str, Any]] = []
    tasks = [
        asyncio.create_task(
            _web_worker(
                worker_id,
                client=web,
                positions=web_positions,
                workers=web_workers,
                total_requests=total_requests,
                minimum_duration=minimum_duration,
                ready=ready,
                start_event=start_event,
                started_box=started_box,
                samples=samples,
                errors=errors,
            )
        )
        for worker_id in range(web_workers)
    ]
    tasks.extend(
        asyncio.create_task(
            _mcp_worker(
                worker_id,
                url=mcp_url,
                token=token,
                positions=mcp_positions,
                workers=mcp_workers,
                total_requests=total_requests,
                minimum_duration=minimum_duration,
                ready=ready,
                start_event=start_event,
                started_box=started_box,
                samples=samples,
                errors=errors,
            )
        )
        for worker_id in range(mcp_workers)
    )
    for _ in range(worker_count):
        await ready.get()
    started_box[0] = time.perf_counter()
    start_event.set()
    await asyncio.gather(*tasks)
    duration = time.perf_counter() - started_box[0]
    settlement_ids = [sample.settlement_id for sample in samples if sample.settlement_id is not None]
    return (
        {
            "name": name,
            "requested": total_requests,
            "completed": len(samples),
            "failed": len(errors),
            "concurrency": concurrency,
            "web_workers": web_workers,
            "mcp_workers": mcp_workers,
            "web_completed": sum(sample.entry == "web" for sample in samples),
            "mcp_completed": sum(sample.entry == "mcp" for sample in samples),
            "duration_seconds": round(duration, 6),
            "minimum_duration_seconds": minimum_duration,
            "throughput_rps": round(len(samples) / duration, 3) if duration else 0.0,
            "web_latency_ms": latency_summary(samples, "web"),
            "mcp_latency_ms": latency_summary(samples, "mcp"),
            "unique_mcp_settlements": len(set(settlement_ids)),
            "errors": errors[:100],
        },
        samples,
    )


async def execute_concurrent_idempotency(url: str, token: str, concurrency: int = 6) -> dict[str, Any]:
    before, _ = await _usage_summary(url, token)
    arguments = {
        "query": "EGFR",
        "limit": 5,
        "idempotency_key": f"performance-race-{uuid.uuid4().hex}",
        "max_billable_units": "100",
    }
    results = await asyncio.gather(
        *(_call_tool_result(url, token, "search_entities", arguments) for _ in range(concurrency))
    )
    settlement_ids: list[str] = []
    rejected_messages: list[str] = []
    for result in results:
        if result.is_error:
            rejected_messages.append(_tool_error_message(result))
            continue
        payload = _structured(result)
        usage = payload.get("usage")
        if not isinstance(usage, dict) or not isinstance(usage.get("settlement_id"), str):
            raise RuntimeError("Concurrent idempotency result omitted settlement metadata")
        settlement_ids.append(usage["settlement_id"])
    replay = await _call_tool(url, token, "search_entities", arguments)
    replay_usage = replay.get("usage")
    if not isinstance(replay_usage, dict) or not isinstance(replay_usage.get("settlement_id"), str):
        raise RuntimeError("Concurrent idempotency replay omitted settlement metadata")
    settlement_ids.append(replay_usage["settlement_id"])
    after, _ = await _usage_summary(url, token)
    settlement_delta = int(after["settlement_count"]) - int(before["settlement_count"])
    assertions = {
        "one_durable_settlement": len(set(settlement_ids)) == 1 and settlement_delta == 1,
        "racing_requests_do_not_create_unexpected_errors": all(
            "already reserved" in message.casefold() for message in rejected_messages
        ),
        "terminal_replay_is_marked": replay_usage.get("replayed") is True,
        "no_reservation_leak": int(after["active_reservations"]) == 0,
    }
    return {
        "concurrency": concurrency,
        "successful_or_replayed_calls": len(settlement_ids),
        "in_flight_rejections": len(rejected_messages),
        "settlement_delta": settlement_delta,
        "unique_settlements": len(set(settlement_ids)),
        "active_reservations_after": int(after["active_reservations"]),
        "assertions": assertions,
    }


async def execute_acceptance(
    *,
    web_url: str,
    mcp_url: str,
    token: str,
    email: str,
    password: str,
    sustained_requests: int,
    sustained_concurrency: int,
    sustained_seconds: float,
    peak_requests: int,
    peak_concurrency: int,
    max_web_p95_ms: float,
    max_mcp_p95_ms: float,
) -> dict[str, Any]:
    timeout = httpx.Timeout(30, connect=10)
    limits = httpx.Limits(
        max_connections=max(peak_concurrency, 10), max_keepalive_connections=max(10, peak_concurrency)
    )
    async with httpx.AsyncClient(base_url=web_url, timeout=timeout, limits=limits, trust_env=False) as web:
        login = await web.post("/api/v1/auth/login", json={"email": email, "password": password})
        if login.status_code != 200:
            raise RuntimeError(f"Performance Web login returned HTTP {login.status_code}")
        current_user = await web.get("/api/v1/auth/me")
        if current_user.status_code != 200:
            raise RuntimeError("Performance Web session was not accepted")
        before, protocol_version = await _usage_summary(mcp_url, token)
        started_at = datetime.now(UTC)
        sustained, sustained_samples = await execute_phase(
            "sustained",
            web=web,
            mcp_url=mcp_url,
            token=token,
            total_requests=sustained_requests,
            concurrency=sustained_concurrency,
            minimum_duration=sustained_seconds,
        )
        peak, peak_samples = await execute_phase(
            "peak",
            web=web,
            mcp_url=mcp_url,
            token=token,
            total_requests=peak_requests,
            concurrency=peak_concurrency,
            minimum_duration=0,
        )
        after_load, after_protocol_version = await _usage_summary(mcp_url, token)

    samples = sustained_samples + peak_samples
    mcp_samples = [sample for sample in samples if sample.entry == "mcp"]
    web_samples = [sample for sample in samples if sample.entry == "web"]
    settlement_ids = [sample.settlement_id for sample in mcp_samples if sample.settlement_id is not None]
    settlement_delta = int(after_load["settlement_count"]) - int(before["settlement_count"])
    charged_delta = _units(after_load, "charged_units") - _units(before, "charged_units")
    consumed_delta = _units(after_load, "consumed_units") - _units(before, "consumed_units")
    race = await execute_concurrent_idempotency(mcp_url, token)
    resilience = await execute_resilience(mcp_url, token)
    final, _ = await _usage_summary(mcp_url, token)
    web_latency = latency_summary(samples, "web")
    mcp_latency = latency_summary(samples, "mcp")
    assertions = {
        "all_mixed_requests_succeeded": sustained["failed"] == peak["failed"] == 0,
        "both_public_entries_exercised": bool(web_samples) and bool(mcp_samples),
        "sustained_duration_reached": float(sustained["duration_seconds"]) >= sustained_seconds,
        "peak_concurrency_exceeds_sustained": peak_concurrency > sustained_concurrency,
        "one_unique_settlement_per_mcp_success": len(set(settlement_ids)) == len(mcp_samples),
        "settlement_delta_matches_mcp_successes": settlement_delta == len(mcp_samples),
        "charged_and_consumed_deltas_match": charged_delta == consumed_delta,
        "no_load_reservation_leak": int(after_load["active_reservations"]) == 0,
        "no_final_reservation_leak": int(final["active_reservations"]) == 0,
        "web_p95_within_local_threshold": float(web_latency["p95"]) <= max_web_p95_ms,
        "mcp_p95_within_local_threshold": float(mcp_latency["p95"]) <= max_mcp_p95_ms,
        "protocol_baseline_negotiated": protocol_version == after_protocol_version == MCP_PROTOCOL_BASELINE,
    }
    all_assertions = [*assertions.values(), *race["assertions"].values(), *resilience["assertions"].values()]
    return {
        "schema": REPORT_SCHEMA,
        "schema_version": 1,
        "status": "passed" if all(all_assertions) else "failed",
        "production_claim": False,
        "environment_kind": "local-controlled-baseline",
        "generated_at": datetime.now(UTC).isoformat(),
        "started_at": started_at.isoformat(),
        "protocol_version": protocol_version,
        "thresholds": {"web_p95_ms": max_web_p95_ms, "mcp_p95_ms": max_mcp_p95_ms},
        "phases": [sustained, peak],
        "aggregate": {
            "web_completed": len(web_samples),
            "mcp_completed": len(mcp_samples),
            "web_latency_ms": web_latency,
            "mcp_latency_ms": mcp_latency,
            "settlement_delta": settlement_delta,
            "charged_units_delta": str(charged_delta),
            "consumed_units_delta": str(consumed_delta),
            "active_reservations_after_load": int(after_load["active_reservations"]),
            "active_reservations_final": int(final["active_reservations"]),
        },
        "concurrent_idempotency": race,
        "failure_injection": resilience,
        "assertions": assertions,
        "coverage": {
            "sustained_load": "bounded local protocol load",
            "peak_load": "bounded local protocol burst",
            "backpressure": "bounded client concurrency and fail-closed commercial reservations",
            "fault_injection": ["client_cancel", "client_timeout", "domain_failure", "budget_rejection"],
            "metering_integrity": "settlement, units, idempotency race, and zero-reservation invariants",
            "long_running": False,
            "target_infrastructure_faults": False,
            "production_approvals": False,
        },
        "production_gaps": [
            "approved target-scale sustained and long-running load",
            "server-side backpressure and managed-dependency fault injection",
            "target gateway, IdP, network, and multi-zone failover",
            "platform and product approval",
        ],
        "credentials_recorded": False,
    }


def run() -> None:
    parser = argparse.ArgumentParser(description="Run a bounded local Web and billed MCP performance baseline")
    parser.add_argument("--web-url", default="http://127.0.0.1:8080")
    parser.add_argument("--mcp-url", default="http://127.0.0.1:8090/mcp")
    parser.add_argument("--sustained-requests", type=int, default=20)
    parser.add_argument("--sustained-concurrency", type=int, default=4)
    parser.add_argument("--sustained-seconds", type=float, default=5)
    parser.add_argument("--peak-requests", type=int, default=24)
    parser.add_argument("--peak-concurrency", type=int, default=12)
    parser.add_argument("--max-web-p95-ms", type=float, default=800)
    parser.add_argument("--max-mcp-p95-ms", type=float, default=2000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 2 <= args.sustained_requests <= 10_000 or args.sustained_requests % 2:
        parser.error("--sustained-requests must be an even number between 2 and 10000")
    if not 2 <= args.peak_requests <= 10_000 or args.peak_requests % 2:
        parser.error("--peak-requests must be an even number between 2 and 10000")
    if not 2 <= args.sustained_concurrency <= min(args.sustained_requests, 200):
        parser.error("--sustained-concurrency is outside the supported range")
    if not args.sustained_concurrency < args.peak_concurrency <= min(args.peak_requests, 200):
        parser.error("--peak-concurrency must exceed sustained concurrency and not exceed peak requests")
    if not 1 <= args.sustained_seconds <= 86_400:
        parser.error("--sustained-seconds must be between 1 and 86400")
    if args.max_web_p95_ms <= 0 or args.max_mcp_p95_ms <= 0:
        parser.error("latency thresholds must be positive")
    token = os.environ.get("TEST_MCP_ACCESS_TOKEN", "")
    email = os.environ.get("PERFORMANCE_TEST_EMAIL", "")
    password = os.environ.get("PERFORMANCE_TEST_PASSWORD", "")
    if not token or not email or not password:
        parser.error("TEST_MCP_ACCESS_TOKEN, PERFORMANCE_TEST_EMAIL and PERFORMANCE_TEST_PASSWORD are required")
    report = asyncio.run(
        execute_acceptance(
            web_url=args.web_url,
            mcp_url=args.mcp_url,
            token=token,
            email=email,
            password=password,
            sustained_requests=args.sustained_requests,
            sustained_concurrency=args.sustained_concurrency,
            sustained_seconds=args.sustained_seconds,
            peak_requests=args.peak_requests,
            peak_concurrency=args.peak_concurrency,
            max_web_p95_ms=args.max_web_p95_ms,
            max_mcp_p95_ms=args.max_mcp_p95_ms,
        )
    )
    if args.output:
        _write_report(args.output, report)
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    run()
