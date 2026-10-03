from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from pharma_intel.config import get_settings
from pharma_intel.models import AccountRegistrationBudget
from pharma_intel.security import normalize_email

WINDOW_SECONDS = 600
MAX_PEERS = 4096


@dataclass(frozen=True, slots=True)
class AccountBudget:
    namespace: bytes
    max_attempts: int
    action: str


REGISTRATION_BUDGET = AccountBudget(b"registration-peer", 10, "注册")
LOGIN_PEER_BUDGET = AccountBudget(b"login-peer", 240, "登录")
LOGIN_IDENTITY_BUDGET = AccountBudget(b"login-identity-peer", 60, "登录")


class AccountRateExceeded(RuntimeError):
    pass


def consume_account_budget(
    session: Session,
    resource: str,
    *,
    budget: AccountBudget = REGISTRATION_BUDGET,
    now: datetime | None = None,
) -> None:
    """Persist domain-separated attempts without storing addresses or credential input.

    The existing counter table is retained so migration preserves active registration
    limits. All account operations use this one atomic counter implementation.
    """
    observed = now or datetime.now(UTC)
    window = datetime.fromtimestamp(int(observed.timestamp()) // WINDOW_SECONDS * WINDOW_SECONDS, UTC)
    digest = hmac.new(
        get_settings().jwt_secret.encode(),
        budget.namespace + b"\x00" + resource.encode(),
        hashlib.sha256,
    ).hexdigest()
    dialect = session.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Account budget requires PostgreSQL or SQLite")
    if dialect == "postgresql":
        # Serialize admission as well as increments, including previously unseen keys.
        # SQLite's first DELETE acquires the corresponding database write lock.
        session.execute(select(func.pg_advisory_xact_lock(816713017661)))
    session.execute(
        delete(AccountRegistrationBudget)
        .where(AccountRegistrationBudget.window_start < window - timedelta(hours=1))
        .execution_options(synchronize_session=False),
    )
    if session.get(AccountRegistrationBudget, digest) is None:
        count = session.scalar(select(func.count()).select_from(AccountRegistrationBudget)) or 0
        if count >= MAX_PEERS:
            session.commit()
            raise AccountRateExceeded(f"{budget.action}服务繁忙，请稍后重试")
    factory = pg_insert if dialect == "postgresql" else sqlite_insert
    statement = factory(AccountRegistrationBudget).values(peer_digest=digest, window_start=window, attempts=1)
    counted = statement.on_conflict_do_update(
        index_elements=[AccountRegistrationBudget.peer_digest],
        set_={
            "window_start": window,
            "attempts": case(
                (AccountRegistrationBudget.window_start == window, AccountRegistrationBudget.attempts + 1),
                else_=1,
            ),
        },
    ).returning(AccountRegistrationBudget.attempts)
    attempts = session.scalar(counted)
    # Rejections and downstream rollbacks cannot erase already observed attempts.
    session.commit()
    if attempts is None or attempts > budget.max_attempts:
        raise AccountRateExceeded(f"{budget.action}尝试过多，请稍后重试")


def consume_login_budget(session: Session, peer: str, email: str, *, now: datetime | None = None) -> None:
    consume_account_budget(session, peer, budget=LOGIN_PEER_BUDGET, now=now)
    consume_account_budget(
        session,
        peer + "\x00" + normalize_email(email),
        budget=LOGIN_IDENTITY_BUDGET,
        now=now,
    )
