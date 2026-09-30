from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from pharma_intel.config import get_settings
from pharma_intel.models import AccountRegistrationBudget

WINDOW_SECONDS = 600
MAX_ATTEMPTS = 10
MAX_PEERS = 4096


class RegistrationRateExceeded(RuntimeError):
    pass


def consume_registration_budget(session: Session, peer: str, *, now: datetime | None = None) -> None:
    observed = now or datetime.now(UTC)
    window = datetime.fromtimestamp(int(observed.timestamp()) // WINDOW_SECONDS * WINDOW_SECONDS, UTC)
    digest = hmac.new(
        get_settings().jwt_secret.encode(), b"registration-peer\x00" + peer.encode(), hashlib.sha256
    ).hexdigest()
    session.execute(
        delete(AccountRegistrationBudget)
        .where(AccountRegistrationBudget.window_start < window - timedelta(hours=1))
        .execution_options(synchronize_session=False)
    )
    if session.get(AccountRegistrationBudget, digest) is None:
        count = session.scalar(select(func.count()).select_from(AccountRegistrationBudget)) or 0
        if count >= MAX_PEERS:
            session.commit()
            raise RegistrationRateExceeded("注册服务繁忙，请稍后重试")
    dialect = session.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise RuntimeError("Registration budget requires PostgreSQL or SQLite")
    factory = pg_insert if dialect == "postgresql" else sqlite_insert
    statement = factory(AccountRegistrationBudget).values(peer_digest=digest, window_start=window, attempts=1)
    counted = statement.on_conflict_do_update(
        index_elements=[AccountRegistrationBudget.peer_digest],
        set_={
            "window_start": window,
            "attempts": case(
                (AccountRegistrationBudget.window_start == window, AccountRegistrationBudget.attempts + 1), else_=1
            ),
        },
    ).returning(AccountRegistrationBudget.attempts)
    attempts = session.scalar(counted)
    # Counts survive invalid invites, duplicate accounts and subsequent business rollbacks.
    session.commit()
    if attempts is None or attempts > MAX_ATTEMPTS:
        raise RegistrationRateExceeded("注册尝试过多，请稍后重试")
