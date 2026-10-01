from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.models import Tenant, User, UserRole
from pharma_intel.schemas import WorkspaceTablePreferenceUpdate
from pharma_intel.security import Principal, require_principal
from pharma_intel.workspace_preferences import (
    WorkspaceTablePreferenceConflict,
    WorkspaceTablePreferenceService,
)


def _user(session: Session, tenant: Tenant, suffix: str) -> User:
    item = create_account(
        tenant_id=tenant.id,
        email=f"preferences-{suffix}@example.test",
        normalized_email=f"preferences-{suffix}@example.test",
        display_name=f"Preferences {suffix}",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ANALYST,
    )
    session.add(item)
    session.commit()
    return item


def test_workspace_table_preferences_are_user_scoped_and_optimistically_versioned(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "owner")
    colleague = _user(session, tenant, "colleague")
    owner_service = WorkspaceTablePreferenceService(session, tenant.id, owner.id)

    created = owner_service.upsert(
        "clinical-trials",
        WorkspaceTablePreferenceUpdate(
            expected_version=0,
            column_visibility={"phase": False},
            column_order=["title", "phase"],
            density="compact",
        ),
    )

    assert created.version == 1
    assert created.column_visibility == {"phase": False}
    assert WorkspaceTablePreferenceService(session, tenant.id, colleague.id).get("clinical-trials") is None
    with pytest.raises(WorkspaceTablePreferenceConflict, match="stale"):
        owner_service.upsert(
            "clinical-trials",
            WorkspaceTablePreferenceUpdate(expected_version=0),
        )

    updated = owner_service.upsert(
        "clinical-trials",
        WorkspaceTablePreferenceUpdate(
            expected_version=1,
            column_visibility={},
            column_order=[],
            density="comfortable",
        ),
    )
    assert updated.version == 2
    assert updated.density == "comfortable"


def test_workspace_table_preference_schema_rejects_unbounded_or_ambiguous_columns() -> None:
    with pytest.raises(ValueError, match="invalid column ID"):
        WorkspaceTablePreferenceUpdate(expected_version=0, column_order=["unsafe column"])
    with pytest.raises(ValueError, match="must be unique"):
        WorkspaceTablePreferenceUpdate(expected_version=0, column_order=["phase", "phase"])
    with pytest.raises(ValueError, match="at most 64"):
        WorkspaceTablePreferenceUpdate(
            expected_version=0,
            column_visibility={f"column-{index}": True for index in range(65)},
        )


def test_workspace_table_preference_api_returns_defaults_persists_and_rejects_agents(
    session: Session,
    tenant: Tenant,
) -> None:
    user = _user(session, tenant, "api")

    def session_override() -> Generator[Session]:
        yield session

    def human_override() -> Principal:
        return Principal(tenant.id, user.id, "user", frozenset({"entities:read"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = human_override
    try:
        with TestClient(app) as client:
            default = client.get("/api/v1/workspace/table-preferences/patent-families")
            assert default.status_code == 200
            assert default.json() == {
                "preference_key": "patent-families",
                "schema_version": 1,
                "column_visibility": {},
                "column_order": [],
                "density": "comfortable",
                "version": 0,
                "persisted": False,
                "updated_at": None,
            }

            created = client.put(
                "/api/v1/workspace/table-preferences/patent-families",
                json={
                    "schema_version": 1,
                    "expected_version": 0,
                    "column_visibility": {"status": False},
                    "column_order": ["title", "status"],
                    "density": "compact",
                },
            )
            assert created.status_code == 200
            assert created.json() | {"updated_at": "ignored"} == {
                "preference_key": "patent-families",
                "schema_version": 1,
                "column_visibility": {"status": False},
                "column_order": ["title", "status"],
                "density": "compact",
                "version": 1,
                "persisted": True,
                "updated_at": "ignored",
            }
            assert created.json()["updated_at"]

            stale = client.put(
                "/api/v1/workspace/table-preferences/patent-families",
                json={"expected_version": 0, "density": "comfortable"},
            )
            assert stale.status_code == 409
            assert client.get("/api/v1/workspace/table-preferences/not-a-domain").status_code == 422

        app.dependency_overrides[require_principal] = lambda: Principal(
            tenant.id,
            "agent-1",
            "agent",
            frozenset({"entities:read"}),
        )
        with TestClient(app) as client:
            assert client.get("/api/v1/workspace/table-preferences/patent-families").status_code == 403
    finally:
        app.dependency_overrides.clear()
