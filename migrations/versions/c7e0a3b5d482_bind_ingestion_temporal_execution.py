"""bind ingestion temporal execution

Revision ID: c7e0a3b5d482
Revises: b6d9f2a4c371
Create Date: 2026-07-25 14:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e0a3b5d482"
down_revision: str | Sequence[str] | None = "b6d9f2a4c371"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_runs", sa.Column("temporal_workflow_id", sa.String(length=200), nullable=True))
    op.add_column("ingestion_runs", sa.Column("temporal_run_id", sa.String(length=64), nullable=True))
    op.add_column("ingestion_runs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingestion_runs", sa.Column("cancel_reason", sa.String(length=500), nullable=True))
    op.add_column("ingestion_runs", sa.Column("cancel_requested_by_actor_type", sa.String(length=40), nullable=True))
    op.add_column("ingestion_runs", sa.Column("cancel_requested_by_actor_id", sa.String(length=200), nullable=True))
    op.create_index("ix_ingestion_runs_temporal_workflow_id", "ingestion_runs", ["temporal_workflow_id"])
    op.create_index("ix_ingestion_runs_temporal_run_id", "ingestion_runs", ["temporal_run_id"])
    op.create_index("ix_ingestion_runs_cancel_requested_at", "ingestion_runs", ["cancel_requested_at"])
    op.create_index(
        "ix_ingestion_runs_temporal_execution",
        "ingestion_runs",
        ["temporal_workflow_id", "temporal_run_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_runs_temporal_execution", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_cancel_requested_at", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_temporal_run_id", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_temporal_workflow_id", table_name="ingestion_runs")
    op.drop_column("ingestion_runs", "cancel_requested_by_actor_id")
    op.drop_column("ingestion_runs", "cancel_requested_by_actor_type")
    op.drop_column("ingestion_runs", "cancel_reason")
    op.drop_column("ingestion_runs", "cancel_requested_at")
    op.drop_column("ingestion_runs", "temporal_run_id")
    op.drop_column("ingestion_runs", "temporal_workflow_id")
