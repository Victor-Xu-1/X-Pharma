"""Add commercial risk queue keyset index.

Revision ID: f27c4d9e1a65
Revises: e16b3c8d0f54
Create Date: 2026-07-19 12:40:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f27c4d9e1a65"
down_revision: str | None = "e16b3c8d0f54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_commercial_policy_risk_queue",
        "commercial_policy_events",
        ["tenant_id", "decision", "occurred_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_commercial_policy_risk_queue", table_name="commercial_policy_events")
