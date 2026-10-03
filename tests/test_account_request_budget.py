from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.accounts.request_budget import (
    AccountRateExceeded,
    consume_account_budget,
    consume_login_budget,
)
from pharma_intel.models import AccountRegistrationBudget


def test_login_attempts_are_durable_private_and_do_not_spend_registration_limits(session: Session) -> None:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    for _ in range(10):
        consume_account_budget(session, "peer", now=now)
    for _ in range(60):
        consume_login_budget(session, "peer", "user@example.test", now=now)
    with pytest.raises(AccountRateExceeded, match="登录尝试过多"):
        consume_login_budget(session, "peer", " USER@example.test ", now=now)
    session.rollback()
    rows = list(session.scalars(select(AccountRegistrationBudget)))
    assert sorted(row.attempts for row in rows) == [10, 61, 61]
    assert all(len(row.peer_digest) == 64 and "peer" not in row.peer_digest for row in rows)
    consume_login_budget(session, "peer", "user@example.test", now=now + timedelta(minutes=10))
    with pytest.raises(AccountRateExceeded, match="注册尝试过多"):
        consume_account_budget(session, "peer", now=now)


def test_account_budget_does_not_admit_unbounded_new_keys(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pharma_intel.accounts.request_budget.MAX_PEERS", 2)
    consume_login_budget(session, "peer", "user@example.test")
    with pytest.raises(AccountRateExceeded, match="服务繁忙"):
        consume_login_budget(session, "another-peer", "user@example.test")
    assert len(list(session.scalars(select(AccountRegistrationBudget)))) == 2
