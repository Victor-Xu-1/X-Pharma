"""Separate global identities from organization membership and authorization.

Revision ID: d32a6c1f9e74
Revises: b8d22d9a1ef3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

revision = "d32a6c1f9e74"
down_revision = "b8d22d9a1ef3"
branch_labels = None
depends_on = None

_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(column_1_name)s_%(referred_table_name)s"}
_CONTEXT_TABLES = ("account_invitations", "user_group_memberships", "workspace_table_preferences")
_ROLE = sa.Enum("ADMIN", "ANALYST", "VIEWER", name="userrole").with_variant(
    ENUM("ADMIN", "ANALYST", "VIEWER", name="userrole", create_type=False), "postgresql"
)


def _rewire_context_references(*, to_memberships: bool) -> None:
    inspector = sa.inspect(op.get_bind())
    for table in _CONTEXT_TABLES:
        foreign_keys = inspector.get_foreign_keys(table)
        source = "users" if to_memberships else "organization_memberships"
        targets = [
            fk for fk in foreign_keys if fk["referred_table"] == source and "tenant_id" in fk["constrained_columns"]
        ]
        with op.batch_alter_table(table, naming_convention=_NAMING) as batch:
            for fk in targets:
                columns = fk["constrained_columns"]
                old_name = fk["name"] or f"fk_{table}_{'_'.join(columns)}_{source}"
                batch.drop_constraint(old_name, type_="foreignkey")
                if table == "account_invitations":
                    suffix = "sponsor" if "created_by_user_id" in columns else "claim"
                    name = f"fk_account_invitation_{suffix}_membership"
                else:
                    name = fk["name"] or old_name
                batch.create_foreign_key(
                    name,
                    "organization_memberships" if to_memberships else "users",
                    columns,
                    ["tenant_id", "user_id" if to_memberships else "id"],
                    ondelete=fk["options"].get("ondelete"),
                )


def _install_membership_rls() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        sa.text("""
        CREATE FUNCTION public.app_current_account_id() RETURNS text
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path = pg_catalog, platform_private, public
        AS $$
        DECLARE requested_account text; supplied_signature text; signing_secret text;
        BEGIN
            requested_account := current_setting('app.account_id', true);
            supplied_signature := current_setting('app.account_signature', true);
            SELECT secret_value INTO signing_secret FROM platform_private.runtime_secrets
            WHERE secret_name = 'tenant_context';
            IF requested_account IS NULL OR requested_account = '' OR signing_secret IS NULL THEN
                RETURN NULL;
            END IF;
            IF supplied_signature IS DISTINCT FROM encode(public.hmac(
                convert_to('account:' || requested_account, 'UTF8'),
                convert_to(signing_secret, 'UTF8'), 'sha256'), 'hex') THEN
                RETURN NULL;
            END IF;
            RETURN requested_account;
        END; $$
    """)
    )
    op.execute("ALTER TABLE organization_memberships ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization_memberships FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY membership_read ON organization_memberships FOR SELECT
        USING (tenant_id = public.app_current_tenant_id() OR user_id = public.app_current_account_id())
    """)
    for action in ("INSERT", "UPDATE", "DELETE"):
        predicate = "tenant_id = public.app_current_tenant_id()"
        using = f" USING ({predicate})" if action != "INSERT" else ""
        check = f" WITH CHECK ({predicate})" if action != "DELETE" else ""
        op.execute(f"CREATE POLICY membership_{action.lower()} ON organization_memberships FOR {action}{using}{check}")


def upgrade() -> None:
    op.create_table(
        "organization_memberships",
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", _ROLE, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organization_memberships_role", "organization_memberships", ["role"])
    # Preserve every legacy UUID, role, suspension, login time and business owner.
    op.execute(
        sa.text("""
        INSERT INTO organization_memberships
            (tenant_id, user_id, role, active, token_version, last_login_at, created_at, updated_at)
        SELECT tenant_id, id, role, active, token_version, last_login_at, created_at, updated_at FROM users
    """)
    )
    _rewire_context_references(to_memberships=True)
    with op.batch_alter_table("user_sessions") as batch:
        batch.create_foreign_key(
            "fk_user_sessions_membership",
            "organization_memberships",
            ["tenant_id", "user_id"],
            ["tenant_id", "user_id"],
        )
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_tenant_id_id", type_="unique")
        batch.drop_index("ix_users_role")
        batch.drop_index("ix_users_tenant_id")
        batch.alter_column("tenant_id", new_column_name="home_tenant_id", existing_type=sa.String(36))
        batch.drop_column("role")
    op.create_index("ix_users_home_tenant_id", "users", ["home_tenant_id"])
    # Legacy 'active' was organization suspension, now preserved in the member.
    op.execute(sa.text("UPDATE users SET active = true"))
    _install_membership_rls()


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Preserve the check/drop invariant against a concurrent membership join.
        # An unavailable maintenance window must fail, never wait without a bound.
        op.execute("SET LOCAL lock_timeout = '5s'")
        op.execute("LOCK TABLE users, organization_memberships IN ACCESS EXCLUSIVE MODE")
        op.execute("SET LOCAL row_security = off")
        # FORCE RLS prevents false-empty reads; maintenance must use the migration role.
        op.execute("ALTER TABLE organization_memberships NO FORCE ROW LEVEL SECURITY")
    incompatible = connection.scalar(
        sa.text("""
        SELECT count(*) FROM users u WHERE
            (SELECT count(*) FROM organization_memberships m WHERE m.user_id = u.id) <> 1 OR
            NOT EXISTS (SELECT 1 FROM organization_memberships m
                        WHERE m.user_id = u.id AND m.tenant_id = u.home_tenant_id)
    """)
    )
    if incompatible:
        raise RuntimeError("Multi-organization accounts cannot be downgraded without an explicit preservation plan")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_home_tenant_id")
        batch.alter_column("home_tenant_id", new_column_name="tenant_id", existing_type=sa.String(36))
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", _ROLE))
        batch.create_unique_constraint("uq_users_tenant_id_id", ["tenant_id", "id"])
        batch.create_index("ix_users_role", ["role"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.execute(
        sa.text("""
        UPDATE users SET
            role = (SELECT role FROM organization_memberships WHERE user_id = users.id),
            active = active AND (SELECT active FROM organization_memberships WHERE user_id = users.id),
            token_version = token_version + 1
    """)
    )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", nullable=False, existing_type=_ROLE)
    _rewire_context_references(to_memberships=False)
    with op.batch_alter_table("user_sessions") as batch:
        batch.drop_constraint("fk_user_sessions_membership", type_="foreignkey")
    op.drop_table("organization_memberships")
    if connection.dialect.name == "postgresql":
        op.execute("DROP FUNCTION public.app_current_account_id()")
