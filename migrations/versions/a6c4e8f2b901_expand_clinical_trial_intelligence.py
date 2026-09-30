"""expand clinical trial intelligence

Revision ID: a6c4e8f2b901
Revises: 9f3a6c2d1e84
Create Date: 2026-07-23 11:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c4e8f2b901"
down_revision: str | Sequence[str] | None = "9f3a6c2d1e84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch_op:
        batch_op.add_column(sa.Column("study_design", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
        batch_op.add_column(sa.Column("eligibility", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
        batch_op.add_column(sa.Column("arms", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(sa.Column("status_history", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(sa.Column("has_results", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("results_first_posted", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("source_document_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_clinical_trial_profiles_source_document_id_source_documents"),
            "source_documents",
            ["source_document_id"],
            ["id"],
        )
        for column in ("has_results", "results_first_posted", "source_document_id"):
            batch_op.create_index(op.f(f"ix_clinical_trial_profiles_{column}"), [column])


def downgrade() -> None:
    with op.batch_alter_table("clinical_trial_profiles") as batch_op:
        for column in reversed(("has_results", "results_first_posted", "source_document_id")):
            batch_op.drop_index(op.f(f"ix_clinical_trial_profiles_{column}"))
        batch_op.drop_constraint(
            op.f("fk_clinical_trial_profiles_source_document_id_source_documents"),
            type_="foreignkey",
        )
        for column in reversed(
            (
                "study_design",
                "eligibility",
                "arms",
                "status_history",
                "has_results",
                "results_first_posted",
                "source_document_id",
            )
        ):
            batch_op.drop_column(column)
