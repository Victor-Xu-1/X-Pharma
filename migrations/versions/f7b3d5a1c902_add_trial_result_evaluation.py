"""add governed clinical trial result evaluation

Revision ID: f7b3d5a1c902
Revises: e1a8c4d2f065
Create Date: 2026-07-23 23:55:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b3d5a1c902"
down_revision: str | Sequence[str] | None = "e1a8c4d2f065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALUES = "'unfavorable','not_superior','non_inferior','similar','positive','superior','terminated'"


def upgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch_op:
        batch_op.add_column(sa.Column("result_evaluation", sa.String(length=40), nullable=True))
        batch_op.create_check_constraint(
            "ck_clinical_trial_result_evaluation",
            f"result_evaluation IS NULL OR result_evaluation IN ({_VALUES})",
        )
        batch_op.create_index(
            op.f("ix_clinical_trial_profiles_result_evaluation"),
            ["result_evaluation"],
        )


def downgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch_op:
        batch_op.drop_index(op.f("ix_clinical_trial_profiles_result_evaluation"))
        batch_op.drop_constraint("ck_clinical_trial_result_evaluation", type_="check")
        batch_op.drop_column("result_evaluation")
