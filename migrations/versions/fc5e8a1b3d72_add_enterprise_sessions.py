"""add enterprise sessions

Revision ID: fc5e8a1b3d72
Revises: fb4d7e9a1c36
Create Date: 2026-07-25 20:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fc5e8a1b3d72"
down_revision: str | Sequence[str] | None = "fb4d7e9a1c36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tenant_datasets") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), server_default="1", nullable=False))
        batch_op.create_check_constraint("ck_tenant_dataset_version", "version > 0")
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("user_agent_sha256", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("revoke_reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint("expires_at > issued_at", name="ck_user_session_expiry"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "user_id", "issued_at", "expires_at", "revoked_at", "revoked_by_user_id"):
        op.create_index(f"ix_user_sessions_{column}", "user_sessions", [column])
    op.create_index(
        "ix_user_sessions_tenant_user_expiry",
        "user_sessions",
        ["tenant_id", "user_id", "expires_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "user_sessions" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "user_sessions" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "user_sessions" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    op.drop_table("user_sessions")
    with op.batch_alter_table("tenant_datasets") as batch_op:
        batch_op.drop_constraint("ck_tenant_dataset_version", type_="check")
        batch_op.drop_column("version")
