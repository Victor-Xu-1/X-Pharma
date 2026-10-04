from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from pharma_intel.config import Settings
from pharma_intel.ingest.clinicaltrials_sync import advance_date_window, prepare_date_window
from pharma_intel.ingest.public_sync import DateWindowSyncRule, PublicSyncState, public_sync_pending
from pharma_intel.ingest.temporal_worker import _source_scan_interval
from pharma_intel.models import DataSource, DataSourceState, DataSourceType


def test_date_watermark_advances_only_after_the_fenced_cycle_finishes() -> None:
    rule = DateWindowSyncRule(sync_mode="continuous", start_date=date(2026, 7, 1), window_days=15)
    now = datetime(2026, 7, 31, tzinfo=UTC)
    first = prepare_date_window(rule, None, now)
    partial = advance_date_window(rule, first, None, 10, now)
    assert partial.window_start == date(2026, 7, 16)
    assert partial.pending and partial.completed_through is None
    partial = advance_date_window(rule, partial, None, 20, now)
    complete = advance_date_window(rule, partial, None, 1, now)
    assert not complete.pending
    assert complete.completed_through == date(2026, 7, 31)
    assert complete.cycle_processed == 31
    resumed = prepare_date_window(rule, complete, now + timedelta(days=2))
    assert resumed.phase == "incremental"
    assert resumed.window_start == date(2026, 7, 29)
    reconciled = prepare_date_window(rule, complete, now + timedelta(days=31))
    assert reconciled.phase == "reconcile"
    assert reconciled.window_start == rule.start_date


def test_pending_checkpoint_uses_bounded_catchup_without_changing_normal_cadence() -> None:
    rule = DateWindowSyncRule(sync_mode="continuous", start_date=date(2026, 7, 1))
    state = prepare_date_window(rule, None, datetime(2026, 7, 31, tzinfo=UTC))
    source = DataSource(
        source_type=DataSourceType.CLINICALTRIALS_GOV,
        routing_rules=[rule.document()],
        connector_cursor={"sync_state": state.model_dump(mode="json")},
        state=DataSourceState.ACTIVE,
        consecutive_failures=0,
        scan_interval_seconds=86_400,
    )
    assert public_sync_pending(source)
    assert _source_scan_interval(Settings(), source) == 30
    source.state = DataSourceState.UNAVAILABLE
    source.consecutive_failures = 3
    assert _source_scan_interval(Settings(), source) == 240
    source.state = DataSourceState.ACTIVE
    state = advance_date_window(rule, state, None, 1, datetime(2026, 7, 31, tzinfo=UTC))
    source.connector_cursor = {"sync_state": state.model_dump(mode="json")}
    assert _source_scan_interval(Settings(), source) == 86_400


@pytest.mark.parametrize(
    "field,value",
    [
        ("cycle_processed", True),
        ("page_token", "bad\nvalue"),
        ("window_end", "2026-06-01"),
        ("cycle_started_at", "2026-07-01T00:00:00"),
    ],
)
def test_malformed_checkpoint_is_rejected(field: str, value: object) -> None:
    rule = DateWindowSyncRule(sync_mode="continuous", start_date=date(2026, 7, 1))
    state = prepare_date_window(rule, None, datetime(2026, 7, 31, tzinfo=UTC)).model_dump(mode="json")
    state[field] = value
    with pytest.raises(ValueError):
        PublicSyncState.model_validate(state)
