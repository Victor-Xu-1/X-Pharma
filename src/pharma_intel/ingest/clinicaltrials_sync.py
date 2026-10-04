from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pharma_intel.ingest.public_sync import DateWindowSyncRule, PublicSyncState, sync_configuration_sha256


def prepare_date_window(rule: DateWindowSyncRule, previous: PublicSyncState | None, now: datetime) -> PublicSyncState:
    """Fence one cycle, then paginate partitions without advancing the coverage watermark early."""
    if previous is not None and previous.pending:
        return previous.model_copy()
    assert rule.start_date is not None
    cutoff = now.astimezone(UTC).date()
    start = rule.start_date
    phase = "backfill"
    if previous is not None and previous.completed_through is not None:
        reconcile_due = previous.last_reconciled_at is None or (now - previous.last_reconciled_at) >= timedelta(
            days=rule.reconcile_interval_days
        )
        phase = "reconcile" if reconcile_due else "incremental"
        if not reconcile_due:
            start = max(rule.start_date, previous.completed_through - timedelta(days=rule.overlap_days))
    return PublicSyncState(
        configuration_sha256=sync_configuration_sha256(rule),
        source_kind="clinicaltrials_gov",
        phase=phase,
        pending=True,
        cycle_started_at=now,
        last_completed_at=previous.last_completed_at if previous else None,
        last_reconciled_at=previous.last_reconciled_at if previous else None,
        completed_through=previous.completed_through if previous else None,
        window_start=start,
        window_end=min(start + timedelta(days=rule.window_days - 1), cutoff),
        cycle_cutoff=cutoff,
    )


def advance_date_window(
    rule: DateWindowSyncRule, state: PublicSyncState, next_page_token: str | None, count: int, now: datetime
) -> PublicSyncState:
    assert state.window_end is not None and state.cycle_cutoff is not None
    updated = state.model_copy(update={"cycle_processed": state.cycle_processed + count})
    if next_page_token is not None:
        return updated.model_copy(update={"page_token": next_page_token, "pending": True})
    if state.window_end < state.cycle_cutoff:
        start = state.window_end + timedelta(days=1)
        return updated.model_copy(
            update={
                "window_start": start,
                "window_end": min(start + timedelta(days=rule.window_days - 1), state.cycle_cutoff),
                "page_token": None,
                "pending": True,
            }
        )
    return updated.model_copy(
        update={
            "page_token": None,
            "pending": False,
            "completed_through": state.cycle_cutoff,
            "last_completed_at": now,
            "last_reconciled_at": now if state.phase in {"backfill", "reconcile"} else state.last_reconciled_at,
        }
    )
