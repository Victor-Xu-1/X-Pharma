from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from mcp.types import TextContent

from pharma_intel import performance_baseline
from pharma_intel.mcp_load_baseline import MCP_PROTOCOL_BASELINE
from pharma_intel.performance_baseline import RequestSample, latency_summary

TEST_TOKEN = "performance-test-token"  # noqa: S105
TEST_PASSWORD = "performance-test-password"  # noqa: S105


def _usage(settlements: int, units: str) -> dict[str, Any]:
    return {
        "settlement_count": settlements,
        "charged_units": units,
        "consumed_units": units,
        "active_reservations": 0,
        "reserved_units": "0.00000000",
    }


def test_latency_summary_is_entry_specific_and_preserves_tail() -> None:
    samples = [
        RequestSample("web", 1.0),
        RequestSample("mcp", 50.0, "settlement-1"),
        RequestSample("web", 2.0),
        RequestSample("web", 100.0),
    ]

    assert latency_summary(samples, "web") == {
        "minimum": 1.0,
        "p50": 2.0,
        "p95": 100.0,
        "p99": 100.0,
        "maximum": 100.0,
    }
    assert latency_summary(samples, "mcp")["p95"] == 50.0


def test_latency_summary_handles_an_empty_entry_without_nan() -> None:
    assert latency_summary([], "web") == {
        "minimum": 0.0,
        "p50": 0.0,
        "p95": 0.0,
        "p99": 0.0,
        "maximum": 0.0,
    }


@pytest.mark.asyncio
async def test_concurrent_idempotency_collapses_racing_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    usage_summaries = iter([_usage(10, "10.00000000"), _usage(11, "11.00100000")])
    result_index = 0

    async def fake_usage_summary(url: str, token: str) -> tuple[dict[str, Any], str]:
        del url, token
        return next(usage_summaries), MCP_PROTOCOL_BASELINE

    async def fake_call_result(url: str, token: str, name: str, arguments: dict[str, Any]) -> Any:
        nonlocal result_index
        del url, token, name, arguments
        result_index += 1
        if result_index == 1:
            return SimpleNamespace(
                is_error=False,
                structured_content={"usage": {"settlement_id": "settlement-one"}},
                content=[],
            )
        return SimpleNamespace(
            is_error=True,
            structured_content=None,
            content=[TextContent(type="text", text="commercial request is already reserved")],
        )

    async def fake_call(url: str, token: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        del url, token, name, arguments
        return {"usage": {"settlement_id": "settlement-one", "replayed": True}}

    monkeypatch.setattr(performance_baseline, "_usage_summary", fake_usage_summary)
    monkeypatch.setattr(performance_baseline, "_call_tool_result", fake_call_result)
    monkeypatch.setattr(performance_baseline, "_call_tool", fake_call)

    report = await performance_baseline.execute_concurrent_idempotency("http://mcp.test", "token", 6)

    assert report["settlement_delta"] == 1
    assert report["in_flight_rejections"] == 5
    assert all(report["assertions"].values())


@pytest.mark.asyncio
async def test_acceptance_report_preserves_local_scope_and_binds_both_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 200

    class FakeWebClient:
        async def __aenter__(self) -> FakeWebClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def post(self, path: str, json: dict[str, str]) -> FakeResponse:
            assert path == "/api/v1/auth/login"
            assert set(json) == {"email", "password"}
            return FakeResponse()

        async def get(self, path: str) -> FakeResponse:
            assert path == "/api/v1/auth/me"
            return FakeResponse()

    usage_summaries = iter(
        [
            (_usage(5, "5.00000000"), MCP_PROTOCOL_BASELINE),
            (_usage(7, "7.00200000"), MCP_PROTOCOL_BASELINE),
            (_usage(9, "9.00400000"), MCP_PROTOCOL_BASELINE),
        ]
    )

    async def fake_usage_summary(url: str, token: str) -> tuple[dict[str, Any], str]:
        del url, token
        return next(usage_summaries)

    async def fake_phase(name: str, **kwargs: Any) -> tuple[dict[str, Any], list[RequestSample]]:
        del kwargs
        samples = [
            RequestSample("web", 10.0),
            RequestSample("mcp", 20.0, f"settlement-{name}"),
        ]
        return (
            {
                "name": name,
                "requested": 2,
                "completed": 2,
                "failed": 0,
                "concurrency": 2 if name == "sustained" else 4,
                "duration_seconds": 1.1 if name == "sustained" else 0.1,
                "errors": [],
            },
            samples,
        )

    async def fake_race(url: str, token: str) -> dict[str, Any]:
        del url, token
        return {"assertions": {"one_settlement": True}}

    async def fake_resilience(url: str, token: str) -> dict[str, Any]:
        del url, token
        return {"assertions": {"timeout_terminal": True}}

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeWebClient())
    monkeypatch.setattr(performance_baseline, "_usage_summary", fake_usage_summary)
    monkeypatch.setattr(performance_baseline, "execute_phase", fake_phase)
    monkeypatch.setattr(performance_baseline, "execute_concurrent_idempotency", fake_race)
    monkeypatch.setattr(performance_baseline, "execute_resilience", fake_resilience)

    report = await performance_baseline.execute_acceptance(
        web_url="http://web.test",
        mcp_url="http://mcp.test",
        token=TEST_TOKEN,
        email="viewer@example.test",
        password=TEST_PASSWORD,
        sustained_requests=2,
        sustained_concurrency=2,
        sustained_seconds=1,
        peak_requests=2,
        peak_concurrency=4,
        max_web_p95_ms=800,
        max_mcp_p95_ms=2000,
    )

    assert report["status"] == "passed"
    assert report["production_claim"] is False
    assert report["aggregate"]["settlement_delta"] == 2
    assert report["coverage"]["long_running"] is False
    assert all(report["assertions"].values())
