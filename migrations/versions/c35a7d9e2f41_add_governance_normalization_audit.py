"""add governance normalization audit fields

Revision ID: c35a7d9e2f41
Revises: b24e8f6a1c30
Create Date: 2026-07-16 14:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c35a7d9e2f41"
down_revision: str | Sequence[str] | None = "b24e8f6a1c30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("staged_facts") as batch_op:
        batch_op.add_column(sa.Column("raw_payload", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("normalization_version", sa.String(length=100), nullable=True))

    op.execute(sa.text("UPDATE staged_facts SET raw_payload = payload WHERE raw_payload IS NULL"))

    with op.batch_alter_table("staged_facts") as batch_op:
        batch_op.alter_column("raw_payload", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("staged_facts") as batch_op:
        batch_op.drop_column("normalization_version")
        batch_op.drop_column("raw_payload")
