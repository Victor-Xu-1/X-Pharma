"""add trial research classification

Revision ID: b8e4c1d7a206
Revises: ad7e3c1f9b42
Create Date: 2026-07-26 21:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e4c1d7a206"
down_revision: str | Sequence[str] | None = "ad7e3c1f9b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch:
        batch.add_column(sa.Column("acronym", sa.String(length=240), nullable=True))
        batch.add_column(sa.Column("initiation_type", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("therapy_lines", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch.create_check_constraint(
            "ck_clinical_trial_initiation_type",
            "initiation_type IS NULL OR initiation_type IN ('iit','ist')",
        )
        batch.create_index("ix_clinical_trial_profiles_acronym", ["acronym"])
        batch.create_index("ix_clinical_trial_profiles_initiation_type", ["initiation_type"])


def downgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch:
        batch.drop_index("ix_clinical_trial_profiles_initiation_type")
        batch.drop_index("ix_clinical_trial_profiles_acronym")
        batch.drop_constraint("ck_clinical_trial_initiation_type", type_="check")
        batch.drop_column("therapy_lines")
        batch.drop_column("initiation_type")
        batch.drop_column("acronym")
