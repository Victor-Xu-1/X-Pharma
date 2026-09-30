"""add governed program status

Revision ID: d1a6b3f9e528
Revises: c9f5a2e8d417
Create Date: 2026-07-27 08:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1a6b3f9e528"
down_revision: str | Sequence[str] | None = "c9f5a2e8d417"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("development_programs", sa.Column("program_status", sa.String(length=20), nullable=True))
    with op.batch_alter_table("development_programs") as batch_op:
        batch_op.create_check_constraint(
            "ck_program_status",
            "program_status IS NULL OR program_status IN ('active', 'inactive', 'unknown')",
        )
        batch_op.create_index(op.f("ix_development_programs_program_status"), ["program_status"])
    # Deterministic backfill: only the exact tokens the product already renders as the
    # governed status vocabulary are promoted; every other free-text detail stays NULL
    # (displayed as 未披露) instead of being guessed into a bucket.
    op.execute(
        "UPDATE development_programs SET program_status = status_detail "
        "WHERE status_detail IN ('active', 'inactive', 'unknown')"
    )


def downgrade() -> None:
    with op.batch_alter_table("development_programs") as batch_op:
        batch_op.drop_index(op.f("ix_development_programs_program_status"))
        batch_op.drop_constraint("ck_program_status", type_="check")
    op.drop_column("development_programs", "program_status")
