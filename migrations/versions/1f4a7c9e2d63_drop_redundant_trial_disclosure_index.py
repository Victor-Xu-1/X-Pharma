"""drop redundant trial disclosure external id index

Revision ID: 1f4a7c9e2d63
Revises: 0c9e2b4d6f18
Create Date: 2026-07-24 00:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "1f4a7c9e2d63"
down_revision: str | Sequence[str] | None = "0c9e2b4d6f18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEX = "ix_clinical_trial_result_disclosures_external_id"
_TABLE = "clinical_trial_result_disclosures"


def upgrade() -> None:
    op.drop_index(_INDEX, table_name=_TABLE)


def downgrade() -> None:
    op.create_index(_INDEX, _TABLE, ["external_id"])
