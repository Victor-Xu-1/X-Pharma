"""add ingestion run operations

Revision ID: a4c7e1d9b260
Revises: 9e2f4a6c8b10
Create Date: 2026-07-25 10:05:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4c7e1d9b260"
down_revision: str | Sequence[str] | None = "9e2f4a6c8b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_run_operations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ingestion_run_id", sa.String(length=36), nullable=False),
        sa.Column("operation_key", sa.String(length=128), nullable=False),
        sa.Column("operation_type", sa.String(length=40), nullable=False),
        sa.Column("expected_state", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("requested_by_actor_type", sa.String(length=40), nullable=False),
        sa.Column("requested_by_actor_id", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("response", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "operation_key", name="uq_ingestion_run_operation_key"),
    )
    op.create_index(
        "ix_ingestion_run_operations_tenant_id",
        "ingestion_run_operations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_ingestion_run_operations_ingestion_run_id",
        "ingestion_run_operations",
        ["ingestion_run_id"],
    )
    op.create_index(
        "ix_ingestion_run_operations_state",
        "ingestion_run_operations",
        ["state"],
    )
    op.create_index(
        "ix_ingestion_run_operations_run_created",
        "ingestion_run_operations",
        ["ingestion_run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_run_operations_run_created", table_name="ingestion_run_operations")
    op.drop_index("ix_ingestion_run_operations_state", table_name="ingestion_run_operations")
    op.drop_index("ix_ingestion_run_operations_ingestion_run_id", table_name="ingestion_run_operations")
    op.drop_index("ix_ingestion_run_operations_tenant_id", table_name="ingestion_run_operations")
    op.drop_table("ingestion_run_operations")
