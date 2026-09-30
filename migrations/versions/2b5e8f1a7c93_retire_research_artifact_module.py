"""retire fixed research artifact module

Revision ID: 2b5e8f1a7c93
Revises: 1c4d7e9f2a60
Create Date: 2026-07-18 12:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2b5e8f1a7c93"
down_revision: str | Sequence[str] | None = "1c4d7e9f2a60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    row_count = bind.execute(sa.text("SELECT count(*) FROM research_bundles")).scalar_one()
    if row_count:
        raise RuntimeError(
            "research_bundles contains legacy downstream artifacts; "
            "export and remove legacy rows before retiring the module"
        )
    op.drop_table("research_bundles")


def downgrade() -> None:
    op.create_table(
        "research_bundles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by_key_id", sa.String(length=36), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("resolved_entity_ids", sa.JSON(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(requested_by_key_id IS NOT NULL) <> (requested_by_user_id IS NOT NULL)",
            name="ck_research_bundle_single_requester",
        ),
        sa.ForeignKeyConstraint(["requested_by_key_id"], ["api_keys.id"]),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_research_bundles_requested_by_user_id_users",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_sha256"),
    )
    op.create_index(
        op.f("ix_research_bundles_requested_by_key_id"),
        "research_bundles",
        ["requested_by_key_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_bundles_requested_by_user_id"),
        "research_bundles",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_research_bundles_tenant_id"),
        "research_bundles",
        ["tenant_id"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "research_bundles" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "research_bundles" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "research_bundles" '
                "USING (tenant_id = public.app_current_tenant_id()) "
                "WITH CHECK (tenant_id = public.app_current_tenant_id())"
            )
        )
