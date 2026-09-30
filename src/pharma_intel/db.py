from __future__ import annotations

import hashlib
import hmac
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from pharma_intel.config import Settings, get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine_from_settings(get_settings())


def create_engine_from_settings(settings: Settings) -> Engine:
    url = settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    pool_options: dict[str, int | float] = {}
    if not url.startswith("sqlite"):
        pool_options = {
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_timeout": settings.database_pool_timeout_seconds,
            "pool_recycle": settings.database_pool_recycle_seconds,
        }
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args, **pool_options)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Generator[Session]:
    session = get_session_factory()()
    request.state.db_session = session
    try:
        yield session
    finally:
        if getattr(request.state, "db_session", None) is session:
            del request.state.db_session
        session.close()


@event.listens_for(Session, "after_begin")
def _set_postgres_tenant_context(session: Session, _transaction: object, connection: Connection) -> None:
    tenant_id = session.info.get("tenant_id")
    if not tenant_id or connection.dialect.name != "postgresql":
        return
    signature = _sign_tenant_context(tenant_id, session.info.get("tenant_context_signing_secret"))
    connection.exec_driver_sql(
        "SELECT set_config('app.tenant_id', %s, true), set_config('app.tenant_signature', %s, true)",
        (tenant_id, signature),
    )


def _sign_tenant_context(tenant_id: str, signing_secret: object = None) -> str:
    secret_value = (
        signing_secret if isinstance(signing_secret, str) else get_settings().effective_tenant_context_signing_secret
    )
    secret = secret_value.encode("utf-8")
    return hmac.new(secret, tenant_id.encode("utf-8"), hashlib.sha256).hexdigest()


def set_tenant_context(session: Session, tenant_id: str, *, signing_secret: str | None = None) -> None:
    """Apply tenant context now and to every subsequent transaction on this session."""
    session.info["tenant_id"] = tenant_id
    if signing_secret is not None:
        session.info["tenant_context_signing_secret"] = signing_secret
    if session.in_transaction() and session.get_bind().dialect.name == "postgresql":
        session.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant_id, true), "
                "set_config('app.tenant_signature', :signature, true)"
            ),
            {"tenant_id": tenant_id, "signature": _sign_tenant_context(tenant_id, signing_secret)},
        )
