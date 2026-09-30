"""add source version operations

Revision ID: b6d9f2a4c371
Revises: a4c7e1d9b260
Create Date: 2026-07-25 10:45:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6d9f2a4c371"
down_revision: str | Sequence[str] | None = "a4c7e1d9b260"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_version_operations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("source_version_id", sa.String(length=36), nullable=False),
        sa.Column("operation_key", sa.String(length=128), nullable=False),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("from_stage", sa.String(length=40), nullable=False),
        sa.Column("expected_state", sa.String(length=40), nullable=False),
        sa.Column("expected_error_code", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("requested_by_actor_type", sa.String(length=40), nullable=False),
        sa.Column("requested_by_actor_id", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("response", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "operation_key", name="uq_source_version_operation_key"),
    )
    op.create_index("ix_source_version_operations_tenant_id", "source_version_operations", ["tenant_id"])
    op.create_index(
        "ix_source_version_operations_source_version_id",
        "source_version_operations",
        ["source_version_id"],
    )
    op.create_index("ix_source_version_operations_state", "source_version_operations", ["state"])
    op.create_index(
        "ix_source_version_operations_version_created",
        "source_version_operations",
        ["source_version_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_version_operations_version_created", table_name="source_version_operations")
    op.drop_index("ix_source_version_operations_state", table_name="source_version_operations")
    op.drop_index("ix_source_version_operations_source_version_id", table_name="source_version_operations")
    op.drop_index("ix_source_version_operations_tenant_id", table_name="source_version_operations")
    op.drop_table("source_version_operations")
