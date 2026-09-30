"""make RAGFlow dataset projection optional

Revision ID: 0a79d4c6e812
Revises: f68d0a2b5c74
Create Date: 2026-07-16 19:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0a79d4c6e812"
down_revision: str | Sequence[str] | None = "f68d0a2b5c74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tenant_datasets") as batch_op:
        batch_op.alter_column(
            "ragflow_dataset_id",
            existing_type=sa.String(length=64),
            nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    missing = bind.scalar(sa.text("SELECT count(*) FROM tenant_datasets WHERE ragflow_dataset_id IS NULL"))
    if missing:
        raise RuntimeError("Cannot restore the NOT NULL constraint while logical-only datasets exist")
    with op.batch_alter_table("tenant_datasets") as batch_op:
        batch_op.alter_column(
            "ragflow_dataset_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )
