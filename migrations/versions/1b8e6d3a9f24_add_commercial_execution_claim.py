"""add commercial execution claim

Revision ID: 1b8e6d3a9f24
Revises: 0a79d4c6e812
Create Date: 2026-07-16 19:25:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1b8e6d3a9f24"
down_revision: str | Sequence[str] | None = "0a79d4c6e812"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usage_reservations",
        sa.Column("execution_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_usage_reservations_execution_started_at",
        "usage_reservations",
        ["execution_started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_reservations_execution_started_at", table_name="usage_reservations")
    op.drop_column("usage_reservations", "execution_started_at")
