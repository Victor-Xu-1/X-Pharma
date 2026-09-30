"""widen audit request id

Revision ID: e41f7c8a9b20
Revises: d93e4a7c2f10
Create Date: 2026-07-16 02:25:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e41f7c8a9b20"
down_revision: str | Sequence[str] | None = "d93e4a7c2f10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.alter_column(
            "request_id",
            existing_type=sa.String(length=36),
            type_=sa.String(length=100),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.alter_column(
            "request_id",
            existing_type=sa.String(length=100),
            type_=sa.String(length=36),
            existing_nullable=False,
        )
