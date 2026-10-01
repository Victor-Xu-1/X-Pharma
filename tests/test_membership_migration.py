from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from pharma_intel.models import OrganizationMembership, Tenant, User, UserRole, UserSession, WorkspaceTablePreference

UNUSABLE_HASH = "preserved-credential-hash"


def test_membership_migration_preserves_legacy_identity_suspension_session_and_preferences(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = f"sqlite:///{tmp_path / 'membership-migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "b8d22d9a1ef3")
    engine = create_engine(url)
    tenant_id, account_id, session_id, preference_id = (str(uuid4()) for _ in range(4))
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO tenants (id, slug, name, active, created_at, updated_at)
                VALUES (:tenant, 'membership-legacy', 'Legacy organization', true, :now, :now)
            """),
                {"tenant": tenant_id, "now": now},
            )
            connection.execute(
                text("""
                INSERT INTO users (id, tenant_id, email, normalized_email, display_name, password_hash,
                    role, active, token_version, created_at, updated_at)
                VALUES (:id, :tenant, 'legacy@example.test', 'legacy@example.test', 'Legacy account',
                    'preserved-credential-hash', 'ANALYST', false, 7, :now, :now)
            """),
                {"id": account_id, "tenant": tenant_id, "now": now},
            )
            connection.execute(
                text("""
                INSERT INTO user_sessions (id, tenant_id, user_id, user_agent_sha256, issued_at, expires_at)
                VALUES (:id, :tenant, :account, :agent, :now, :expiry)
            """),
                {
                    "id": session_id,
                    "tenant": tenant_id,
                    "account": account_id,
                    "agent": "a" * 64,
                    "now": now,
                    "expiry": now + timedelta(hours=1),
                },
            )
            connection.execute(
                text("""
                INSERT INTO workspace_table_preferences (id, tenant_id, user_id, preference_key, schema_version,
                    column_visibility, column_order, density, version, created_at, updated_at)
                VALUES (:id, :tenant, :account, 'clinical-trials', 1, '{}', '[]', 'compact', 3, :now, :now)
            """),
                {"id": preference_id, "tenant": tenant_id, "account": account_id, "now": now},
            )
        command.upgrade(config, "head")
        with Session(engine) as session:
            account = session.get(User, account_id)
            member = session.get(OrganizationMembership, (tenant_id, account_id))
            stored_session = session.get(UserSession, session_id)
            preference = session.get(WorkspaceTablePreference, preference_id)
            assert account is not None and account.home_tenant_id == tenant_id and account.active
            assert account.password_hash == UNUSABLE_HASH and account.token_version == 7
            assert member is not None and member.role == UserRole.ANALYST and not member.active
            assert member.token_version == 7
            assert stored_session is not None and stored_session.user_id == account_id
            assert preference is not None and preference.version == 3 and preference.density == "compact"
        command.downgrade(config, "b8d22d9a1ef3")
        with engine.connect() as connection:
            stored = connection.execute(
                text("SELECT tenant_id, role, active, password_hash FROM users WHERE id=:id"), {"id": account_id}
            ).one()
            assert stored == (tenant_id, "ANALYST", 0, "preserved-credential-hash")
            assert connection.scalar(text("SELECT count(*) FROM workspace_table_preferences")) == 1
    finally:
        engine.dispose()


def test_downgrade_refuses_to_erase_additional_organization_memberships(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pharma_intel.accounts.identity import create_account

    url = f"sqlite:///{tmp_path / 'multi-membership-downgrade.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            first, second = Tenant(slug="first", name="First"), Tenant(slug="second", name="Second")
            session.add_all([first, second])
            session.flush()
            account = create_account(
                tenant_id=first.id,
                email="member@example.test",
                normalized_email="member@example.test",
                display_name="Member",
                password_hash=UNUSABLE_HASH,
            )
            session.add(account)
            session.flush()
            session.add(OrganizationMembership(tenant_id=second.id, account=account, role=UserRole.ANALYST))
            session.commit()
        with pytest.raises(RuntimeError, match="Multi-organization accounts"):
            command.downgrade(config, "b8d22d9a1ef3")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM organization_memberships")) == 2
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "d32a6c1f9e74"
    finally:
        engine.dispose()
