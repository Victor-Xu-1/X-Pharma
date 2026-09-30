"""add source governance contract

Revision ID: 7f3b9d2a6c81
Revises: 6e2a9c1d4f70
Create Date: 2026-07-17 18:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7f3b9d2a6c81"
down_revision: str | Sequence[str] | None = "6e2a9c1d4f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("data_sources", sa.Column("owner", sa.String(length=200), nullable=True))
    op.add_column("data_sources", sa.Column("data_classification", sa.String(length=32), nullable=True))
    op.add_column("data_sources", sa.Column("authorization_scopes", sa.JSON(), nullable=True))
    op.add_column("data_sources", sa.Column("expected_freshness_seconds", sa.Integer(), nullable=True))
    op.add_column("data_sources", sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True))
    op.add_column("data_sources", sa.Column("connector_cursor", sa.JSON(), nullable=True))
    op.add_column("data_sources", sa.Column("last_cursor_at", sa.DateTime(timezone=True), nullable=True))

    sources = sa.table(
        "data_sources",
        sa.column("owner", sa.String(length=200)),
        sa.column("data_classification", sa.String(length=32)),
        sa.column("authorization_scopes", sa.JSON()),
        sa.column("expected_freshness_seconds", sa.Integer()),
        sa.column("rate_limit_per_minute", sa.Integer()),
        sa.column("connector_cursor", sa.JSON()),
    )
    op.get_bind().execute(
        sources.update().values(
            owner="migration-unassigned",
            data_classification="internal",
            authorization_scopes=[],
            expected_freshness_seconds=86_400,
            rate_limit_per_minute=60,
            connector_cursor={},
        )
    )

    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.alter_column("owner", existing_type=sa.String(length=200), nullable=False)
        batch_op.alter_column("data_classification", existing_type=sa.String(length=32), nullable=False)
        batch_op.alter_column("authorization_scopes", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("expected_freshness_seconds", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("rate_limit_per_minute", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("connector_cursor", existing_type=sa.JSON(), nullable=False)
        batch_op.create_check_constraint(
            "ck_data_source_expected_freshness",
            "expected_freshness_seconds >= 60",
        )
        batch_op.create_check_constraint("ck_data_source_rate_limit", "rate_limit_per_minute > 0")


def downgrade() -> None:
    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.drop_constraint("ck_data_source_rate_limit", type_="check")
        batch_op.drop_constraint("ck_data_source_expected_freshness", type_="check")
        batch_op.drop_column("last_cursor_at")
        batch_op.drop_column("connector_cursor")
        batch_op.drop_column("rate_limit_per_minute")
        batch_op.drop_column("expected_freshness_seconds")
        batch_op.drop_column("authorization_scopes")
        batch_op.drop_column("data_classification")
        batch_op.drop_column("owner")
