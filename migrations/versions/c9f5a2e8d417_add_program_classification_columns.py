"""add program classification columns

Revision ID: c9f5a2e8d417
Revises: b8e4c1d7a206
Create Date: 2026-07-27 05:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9f5a2e8d417"
down_revision: str | Sequence[str] | None = "b8e4c1d7a206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("innovation_type", "therapeutic_area", "drug_category")


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column("development_programs", sa.Column(column, sa.String(length=120), nullable=True))
    with op.batch_alter_table("development_programs") as batch_op:
        for column in _COLUMNS:
            batch_op.create_index(op.f(f"ix_development_programs_{column}"), [column])


def downgrade() -> None:
    with op.batch_alter_table("development_programs") as batch_op:
        for column in reversed(_COLUMNS):
            batch_op.drop_index(op.f(f"ix_development_programs_{column}"))
    for column in reversed(_COLUMNS):
        op.drop_column("development_programs", column)
