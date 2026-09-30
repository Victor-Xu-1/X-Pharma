"""add workspace table preferences

Revision ID: f3c8d5a2b740
Revises: e2b7c4a1f639
Create Date: 2026-07-29 12:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3c8d5a2b740"
down_revision: str | Sequence[str] | None = "e2b7c4a1f639"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREFERENCE_KEYS = (
    "'clinical-trials','deals','entity-search','epidemiology','news-events',"
    "'patent-families','pipeline','regulatory-events'"
)


def upgrade() -> None:
    op.create_table(
        "workspace_table_preferences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("preference_key", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("column_visibility", sa.JSON(), nullable=False),
        sa.Column("column_order", sa.JSON(), nullable=False),
        sa.Column("density", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["users.tenant_id", "users.id"],
            name="fk_workspace_table_preferences_tenant_user",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "preference_key",
            name="uq_workspace_table_preferences_owner_key",
        ),
        sa.CheckConstraint("schema_version = 1", name="ck_workspace_table_preferences_schema_version"),
        sa.CheckConstraint("version > 0", name="ck_workspace_table_preferences_version"),
        sa.CheckConstraint(
            "density IN ('comfortable', 'compact')",
            name="ck_workspace_table_preferences_density",
        ),
        sa.CheckConstraint(
            f"preference_key IN ({_PREFERENCE_KEYS})",
            name="ck_workspace_table_preferences_key",
        ),
    )
    op.create_index(
        "ix_workspace_table_preferences_tenant_id",
        "workspace_table_preferences",
        ["tenant_id"],
    )
    op.create_index(
        "ix_workspace_table_preferences_user_id",
        "workspace_table_preferences",
        ["user_id"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "workspace_table_preferences" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "workspace_table_preferences" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "workspace_table_preferences" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY "tenant_isolation" ON "workspace_table_preferences"'))
        op.execute(sa.text('ALTER TABLE "workspace_table_preferences" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "workspace_table_preferences" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_workspace_table_preferences_user_id", table_name="workspace_table_preferences")
    op.drop_index("ix_workspace_table_preferences_tenant_id", table_name="workspace_table_preferences")
    op.drop_table("workspace_table_preferences")
