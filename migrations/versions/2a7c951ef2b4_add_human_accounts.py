"""add human accounts

Revision ID: 2a7c951ef2b4
Revises: 8f2d23b59db2
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2a7c951ef2b4"
down_revision: str | Sequence[str] | None = "8f2d23b59db2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ADMIN", "ANALYST", "VIEWER", name="userrole"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_normalized_email"), "users", ["normalized_email"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_tenant_id"), "users", ["tenant_id"], unique=False)

    with op.batch_alter_table("research_bundles") as batch_op:
        batch_op.alter_column("requested_by_key_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.add_column(sa.Column("requested_by_user_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            op.f("ix_research_bundles_requested_by_user_id"),
            ["requested_by_user_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_research_bundles_requested_by_user_id_users",
            "users",
            ["requested_by_user_id"],
            ["id"],
        )
        batch_op.create_check_constraint(
            "ck_research_bundle_single_requester",
            "(requested_by_key_id IS NOT NULL) <> (requested_by_user_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("research_bundles") as batch_op:
        batch_op.drop_constraint("ck_research_bundle_single_requester", type_="check")
        batch_op.drop_constraint("fk_research_bundles_requested_by_user_id_users", type_="foreignkey")
        batch_op.drop_index(op.f("ix_research_bundles_requested_by_user_id"))
        batch_op.drop_column("requested_by_user_id")
        batch_op.alter_column("requested_by_key_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_index(op.f("ix_users_tenant_id"), table_name="users")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_normalized_email"), table_name="users")
    op.drop_table("users")
