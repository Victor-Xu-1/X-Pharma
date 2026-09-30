"""Add bounded account registration and tenant-isolated single-use invitations.

Revision ID: b8d22d9a1ef3
Revises: b6e4c9a2d781
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b8d22d9a1ef3"
down_revision = "b6e4c9a2d781"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("normalized_email", sa.String(320), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_user_id", sa.String(36)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id", "created_by_user_id"], ["users.tenant_id", "users.id"]),
        sa.ForeignKeyConstraint(["tenant_id", "claimed_user_id"], ["users.tenant_id", "users.id"]),
        sa.CheckConstraint("expires_at > created_at", name="ck_account_invitation_expiry"),
        sa.CheckConstraint(
            "(claimed_at IS NULL) = (claimed_user_id IS NULL)", name="ck_account_invitation_claim_complete"
        ),
    )
    for column in ("tenant_id", "normalized_email", "expires_at"):
        op.create_index(f"ix_account_invitations_{column}", "account_invitations", [column])
    op.create_index("ix_account_invitation_tenant_created", "account_invitations", ["tenant_id", "created_at"])
    op.create_index(
        "uq_account_invitation_pending",
        "account_invitations",
        ["tenant_id", "normalized_email"],
        unique=True,
        postgresql_where=sa.text("claimed_at IS NULL AND revoked_at IS NULL"),
        sqlite_where=sa.text("claimed_at IS NULL AND revoked_at IS NULL"),
    )
    op.create_table(
        "account_registration_budgets",
        sa.Column("peer_digest", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempts > 0", name="ck_account_registration_attempts"),
    )
    op.create_index("ix_account_registration_budgets_window_start", "account_registration_budgets", ["window_start"])
    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute('ALTER TABLE "account_invitations" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "account_invitations" FORCE ROW LEVEL SECURITY')
        op.execute(
            f'CREATE POLICY "tenant_isolation" ON "account_invitations" USING ({predicate}) WITH CHECK ({predicate})'
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # An RLS-filtered zero must not be mistaken for an empty audit-bearing table.
        op.execute("SET LOCAL row_security = off")
    if connection.scalar(sa.text("SELECT count(*) FROM account_invitations")):
        raise RuntimeError("Archive registration invitations before removing their audit history")
    op.drop_table("account_registration_budgets")
    op.drop_table("account_invitations")
