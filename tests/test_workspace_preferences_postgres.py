from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from pharma_intel.accounts.identity import create_account
from pharma_intel.db import set_tenant_context
from pharma_intel.models import Tenant, UserRole, WorkspaceTablePreference
from pharma_intel.schemas import WorkspaceTablePreferenceUpdate
from pharma_intel.workspace_preferences import (
    WorkspaceTablePreferenceConflict,
    WorkspaceTablePreferenceService,
)
from tests.support.postgres_safety import require_disposable_postgres_url


@pytest.mark.integration
def test_workspace_preferences_are_concurrent_user_scoped_and_rls_isolated() -> None:
    database_url = os.getenv("TEST_WORKSPACE_PREFERENCES_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_WORKSPACE_PREFERENCES_DATABASE_URL is not configured")
    require_disposable_postgres_url(database_url, "TEST_WORKSPACE_PREFERENCES_DATABASE_URL")
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    tenant_id = str(uuid.uuid4())
    other_tenant_id = str(uuid.uuid4())

    with factory() as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"workspace-preferences-{tenant_id}", name="Workspace Preferences")
        owner = create_account(
            tenant_id=tenant_id,
            email=f"workspace-owner-{tenant_id}@example.test",
            normalized_email=f"workspace-owner-{tenant_id}@example.test",
            display_name="Workspace Owner",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ANALYST,
        )
        colleague = create_account(
            tenant_id=tenant_id,
            email=f"workspace-colleague-{tenant_id}@example.test",
            normalized_email=f"workspace-colleague-{tenant_id}@example.test",
            display_name="Workspace Colleague",
            password_hash="not-used",  # noqa: S106
            role=UserRole.ANALYST,
        )
        session.add_all([tenant, owner, colleague])
        session.commit()
        WorkspaceTablePreferenceService(session, tenant_id, owner.id).upsert(
            "pipeline",
            WorkspaceTablePreferenceUpdate(expected_version=0, density="compact"),
        )
        assert WorkspaceTablePreferenceService(session, tenant_id, colleague.id).get("pipeline") is None
        owner_id = owner.id

    barrier = threading.Barrier(2)

    def update_density(density: str) -> int | str:
        with factory() as session:
            set_tenant_context(session, tenant_id)
            barrier.wait(timeout=10)
            try:
                item = WorkspaceTablePreferenceService(session, tenant_id, owner_id).upsert(
                    "pipeline",
                    WorkspaceTablePreferenceUpdate.model_validate(
                        {"expected_version": 1, "density": density},
                    ),
                )
            except WorkspaceTablePreferenceConflict:
                return "conflict"
            return int(item.version)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(update_density, ["comfortable", "compact"]))
    assert sorted(outcomes, key=str) == [2, "conflict"]

    with factory() as session:
        set_tenant_context(session, tenant_id)
        assert session.scalar(select(func.count()).select_from(WorkspaceTablePreference)) == 1
        set_tenant_context(session, other_tenant_id)
        assert session.scalar(select(func.count()).select_from(WorkspaceTablePreference)) == 0
    engine.dispose()
