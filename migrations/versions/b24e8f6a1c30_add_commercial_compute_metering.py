"""add commercial compute metering

Revision ID: b24e8f6a1c30
Revises: a13b7c4d9e02
Create Date: 2026-07-16 11:05:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b24e8f6a1c30"
down_revision: str | Sequence[str] | None = "a13b7c4d9e02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rate_card_items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "per_compute_unit",
                sa.Numeric(precision=28, scale=8),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_rate_card_item_compute_units",
            "per_compute_unit >= 0",
        )

    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "requested_compute_units",
                sa.Numeric(precision=28, scale=8),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_usage_reservation_compute_units",
            "requested_compute_units >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.drop_constraint("ck_usage_reservation_compute_units", type_="check")
        batch_op.drop_column("requested_compute_units")

    with op.batch_alter_table("rate_card_items") as batch_op:
        batch_op.drop_constraint("ck_rate_card_item_compute_units", type_="check")
        batch_op.drop_column("per_compute_unit")
