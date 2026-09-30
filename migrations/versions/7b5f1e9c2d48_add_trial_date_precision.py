"""Preserve the reported precision of clinical trial dates.

Revision ID: 7b5f1e9c2d48
Revises: 6a4e2d8f1c37
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7b5f1e9c2d48"
down_revision = "6a4e2d8f1c37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch_op:
        batch_op.add_column(sa.Column("start_date_precision", sa.String(length=16)))
        batch_op.add_column(sa.Column("completion_date_precision", sa.String(length=16)))
        batch_op.create_check_constraint(
            "ck_clinical_trial_start_date_precision",
            "start_date_precision IS NULL OR start_date_precision IN ('day','month','year')",
        )
        batch_op.create_check_constraint(
            "ck_clinical_trial_completion_date_precision",
            "completion_date_precision IS NULL OR completion_date_precision IN ('day','month','year')",
        )


def downgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch_op:
        batch_op.drop_constraint("ck_clinical_trial_completion_date_precision", type_="check")
        batch_op.drop_constraint("ck_clinical_trial_start_date_precision", type_="check")
        batch_op.drop_column("completion_date_precision")
        batch_op.drop_column("start_date_precision")
