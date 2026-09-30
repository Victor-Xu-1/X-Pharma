"""allow stage replay without a version error code

Revision ID: d8f1b4c6e593
Revises: c7e0a3b5d482
Create Date: 2026-07-25 16:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f1b4c6e593"
down_revision: str | Sequence[str] | None = "c7e0a3b5d482"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("source_version_operations") as batch_op:
        batch_op.alter_column(
            "expected_error_code",
            existing_type=sa.String(length=120),
            nullable=True,
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE source_version_operations "
            "SET expected_error_code = 'stage_status_failed' "
            "WHERE expected_error_code IS NULL"
        )
    )
    with op.batch_alter_table("source_version_operations") as batch_op:
        batch_op.alter_column(
            "expected_error_code",
            existing_type=sa.String(length=120),
            nullable=False,
        )
