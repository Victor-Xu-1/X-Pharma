from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.mcp_streamable_contract import verify_positive_settlement

ROOT = Path(__file__).resolve().parents[1]


def test_positive_settlement_requires_the_normal_paid_single_result_path() -> None:
    verify_positive_settlement(
        {"billing_class": "entity.search", "result_count": 1, "charged_units": "1.01000000"},
        "entity.search",
    )


@pytest.mark.parametrize(
    "override",
    [
        {"billing_class": "entity.read"},
        {"result_count": 0},
        {"result_count": True},
        {"charged_units": "0"},
        {"charged_units": "-1"},
        {"charged_units": "NaN"},
        {"charged_units": "Infinity"},
        {"charged_units": "invalid"},
        {"charged_units": None},
    ],
)
def test_streamable_billing_contract_rejects_invalid_or_empty_usage(override: dict[str, Any]) -> None:
    usage = {"billing_class": "entity.search", "result_count": 1, "charged_units": "1.01", **override}
    with pytest.raises(RuntimeError):
        verify_positive_settlement(usage, "entity.search")


def test_ci_uses_the_fixture_owned_gate_once_without_removing_other_mcp_boundaries() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert workflow.count("./scripts/verify-entry-consistency.sh") == 1
    assert "Real MCP HTTP and Web canonical fact consistency" in workflow
    assert "tests/test_mcp_integration.py" not in workflow
    assert not (ROOT / "tests/test_mcp_integration.py").exists()
    assert workflow.index("./scripts/verify-entry-consistency.sh") < workflow.index(
        "./scripts/verify-mcp-interoperability.sh"
    )
    assert "Independent MCP dual-client interoperability" in workflow
    assert "--requests 20 --concurrency 4" in workflow and "--max-p95-ms 10000" in workflow
    probe = (ROOT / "scripts/entry_consistency_probe.py").read_text(encoding="utf-8")
    assert "timeout=httpx.Timeout(30, connect=10)" in probe
    assert 'Implementation(name="pharma-entry-consistency", version=PRODUCT_VERSION)' in probe
