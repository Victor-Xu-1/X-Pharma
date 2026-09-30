"""add enterprise user groups

Revision ID: e16b3c8d0f54
Revises: d05a2b7c9f43
Create Date: 2026-07-19 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e16b3c8d0f54"
down_revision: str | Sequence[str] | None = "d05a2b7c9f43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("user_groups", "user_group_memberships")


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_unique_constraint("uq_users_tenant_id_id", ["tenant_id", "id"])
    op.create_table(
        "user_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("normalized_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_user_groups_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "normalized_name", name="uq_user_groups_tenant_name"),
    )
    op.create_index(op.f("ix_user_groups_active"), "user_groups", ["active"], unique=False)
    op.create_index(op.f("ix_user_groups_tenant_id"), "user_groups", ["tenant_id"], unique=False)
    op.create_table(
        "user_group_memberships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "group_id"],
            ["user_groups.tenant_id", "user_groups.id"],
            name="fk_user_group_memberships_tenant_group",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_user_group_memberships_tenant_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "group_id", "user_id", name="uq_user_group_membership"),
    )
    op.create_index(
        "ix_user_group_memberships_tenant_group",
        "user_group_memberships",
        ["tenant_id", "group_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_group_memberships_tenant_user",
        "user_group_memberships",
        ["tenant_id", "user_id"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in TENANT_TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f'CREATE POLICY "tenant_isolation" ON "{table}" '
                    f"USING ({predicate}) WITH CHECK ({predicate})"
                )
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in reversed(TENANT_TABLES):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))

    op.drop_index("ix_user_group_memberships_tenant_user", table_name="user_group_memberships")
    op.drop_index("ix_user_group_memberships_tenant_group", table_name="user_group_memberships")
    op.drop_table("user_group_memberships")
    op.drop_index(op.f("ix_user_groups_tenant_id"), table_name="user_groups")
    op.drop_index(op.f("ix_user_groups_active"), table_name="user_groups")
    op.drop_table("user_groups")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_tenant_id_id", type_="unique")
