from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from pharma_intel.mcp_load_baseline import _units, _write_report, percentile


def test_percentile_uses_nearest_rank_without_hiding_tail_latency() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 100.0]

    assert percentile(values, 0.50) == 3.0
    assert percentile(values, 0.95) == 100.0
    assert percentile(values, 0.99) == 100.0
    assert percentile([], 0.95) == 0.0


def test_units_requires_canonical_usage_summary_string() -> None:
    assert _units({"consumed_units": "1.25000000"}, "consumed_units") == Decimal("1.25000000")
    with pytest.raises(RuntimeError, match="omitted consumed_units"):
        _units({"consumed_units": 1.25}, "consumed_units")


def test_commercial_acceptance_report_is_private_and_exclusive(tmp_path: Path) -> None:
    output = tmp_path / "commercial.json"
    _write_report(output, {"status": "passed"})
    assert output.stat().st_mode & 0o777 == 0o600
    with pytest.raises(RuntimeError, match="already exists"):
        _write_report(output, {"status": "replaced"})
