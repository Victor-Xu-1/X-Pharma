"""add workspace domain exports

Revision ID: 9e2f4a6c8b10
Revises: 8d0f2b5c7e43
Create Date: 2026-07-24 23:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e2f4a6c8b10"
down_revision: str | Sequence[str] | None = "8d0f2b5c7e43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workspace_export_events") as batch_op:
        batch_op.drop_constraint("ck_workspace_export_event_set_version_positive", type_="check")
        batch_op.add_column(sa.Column("export_kind", sa.String(20), nullable=False, server_default="comparison"))
        batch_op.add_column(sa.Column("dataset", sa.String(80), nullable=True))
        batch_op.add_column(sa.Column("query_json", sa.JSON(), nullable=True))
        batch_op.alter_column("comparison_set_id", existing_type=sa.String(36), nullable=True)
        batch_op.alter_column("comparison_set_version", existing_type=sa.Integer(), nullable=True)
        batch_op.create_check_constraint(
            "ck_workspace_export_event_kind",
            "export_kind IN ('comparison', 'domain')",
        )
        batch_op.create_check_constraint(
            "ck_workspace_export_event_subject",
            "(export_kind = 'comparison' AND comparison_set_id IS NOT NULL "
            "AND comparison_set_version > 0 AND dataset IS NULL) OR "
            "(export_kind = 'domain' AND comparison_set_id IS NULL "
            "AND comparison_set_version IS NULL AND dataset IS NOT NULL)",
        )
        batch_op.create_index("ix_workspace_export_events_export_kind", ["export_kind"])
        batch_op.create_index("ix_workspace_export_events_dataset", ["dataset"])


def downgrade() -> None:
    domain_count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM workspace_export_events WHERE export_kind = 'domain'")
    )
    if domain_count:
        raise RuntimeError("Cannot downgrade workspace domain exports while immutable domain events exist")
    with op.batch_alter_table("workspace_export_events") as batch_op:
        batch_op.drop_index("ix_workspace_export_events_dataset")
        batch_op.drop_index("ix_workspace_export_events_export_kind")
        batch_op.drop_constraint("ck_workspace_export_event_subject", type_="check")
        batch_op.drop_constraint("ck_workspace_export_event_kind", type_="check")
        batch_op.alter_column("comparison_set_version", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("comparison_set_id", existing_type=sa.String(36), nullable=False)
        batch_op.drop_column("query_json")
        batch_op.drop_column("dataset")
        batch_op.drop_column("export_kind")
        batch_op.create_check_constraint(
            "ck_workspace_export_event_set_version_positive",
            "comparison_set_version > 0",
        )
