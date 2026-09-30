"""add source authorization window

Revision ID: d05a2b7c9f43
Revises: c94f1a6d8e32
Create Date: 2026-07-19 08:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d05a2b7c9f43"
down_revision: str | Sequence[str] | None = "c94f1a6d8e32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.add_column(sa.Column("authorization_valid_from", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("authorization_valid_until", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        sa.text(
            "UPDATE data_sources SET authorization_valid_from = created_at "
            "WHERE authorization_valid_from IS NULL"
        )
    )
    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.alter_column("authorization_valid_from", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.create_check_constraint(
            "ck_data_source_authorization_window",
            "authorization_valid_until IS NULL OR authorization_valid_until > authorization_valid_from",
        )


def downgrade() -> None:
    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.drop_constraint("ck_data_source_authorization_window", type_="check")
        batch_op.drop_column("authorization_valid_until")
        batch_op.drop_column("authorization_valid_from")
