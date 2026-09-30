"""expand patent intelligence

Revision ID: c8e6a0b4d123
Revises: b7d5f9a3c012
Create Date: 2026-07-23 17:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e6a0b4d123"
down_revision: str | Sequence[str] | None = "b7d5f9a3c012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("patent_families") as batch_op:
        batch_op.add_column(sa.Column("legal_status_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("legal_events", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(sa.Column("independent_claims", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.create_index(op.f("ix_patent_families_legal_status_at"), ["legal_status_at"])


def downgrade() -> None:
    with op.batch_alter_table("patent_families") as batch_op:
        batch_op.drop_index(op.f("ix_patent_families_legal_status_at"))
        batch_op.drop_column("independent_claims")
        batch_op.drop_column("legal_events")
        batch_op.drop_column("legal_status_at")
