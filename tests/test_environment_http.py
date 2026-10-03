from __future__ import annotations

import secrets
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import Tenant, UserRole
from pharma_intel.security import Principal, hash_password, require_principal


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER])
def test_environment_routes_enforce_live_human_organization_admin(
    session: Session, tenant: Tenant, role: UserRole
) -> None:
    user = create_account(
        tenant_id=tenant.id,
        email=f"{role.value}@example.test",
        normalized_email=f"{role.value}@example.test",
        display_name="Environment reader",
        password_hash=hash_password(secrets.token_urlsafe(24)),
        role=role,
    )
    session.add(user)
    session.commit()
    principal = Principal(
        tenant_id=tenant.id,
        actor_type="user",
        actor_id=user.id,
        scopes=frozenset({"enterprise:admin"}) if role is UserRole.ADMIN else frozenset(),
    )

    def db() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = db
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            result = client.get("/api/v1/enterprise/environment")
        assert result.status_code == (200 if role is UserRole.ADMIN else 403)
        if role is UserRole.ADMIN:
            payload = result.json()
            assert payload["host_status"] == "not_configured"
            assert payload["host"] is None
            assert all(row["scope"] == "gateway" for row in payload["runtime"])
            assert len(payload["recipes"]) == 3
    finally:
        app.dependency_overrides.clear()


def test_environment_rejects_agent_even_with_admin_scope(session: Session, tenant: Tenant) -> None:
    principal = Principal(
        tenant_id=tenant.id,
        actor_type="api_key",
        actor_id="environment-test-key",
        scopes=frozenset({"enterprise:admin"}),
    )

    def db() -> Generator[Session]:
        yield session

    app.dependency_overrides[get_session] = db
    app.dependency_overrides[require_principal] = lambda: principal
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/enterprise/environment").status_code == 403
    finally:
        app.dependency_overrides.clear()
