"""expand target and program intelligence

Revision ID: b7d5f9a3c012
Revises: a6c4e8f2b901
Create Date: 2026-07-23 15:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d5f9a3c012"
down_revision: str | Sequence[str] | None = "a6c4e8f2b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("target_profiles") as batch_op:
        batch_op.add_column(sa.Column("source_document_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_target_profiles_source_document_id_source_documents"),
            "source_documents",
            ["source_document_id"],
            ["id"],
        )
        batch_op.create_index(op.f("ix_target_profiles_source_document_id"), ["source_document_id"])

    with op.batch_alter_table("development_programs") as batch_op:
        batch_op.add_column(sa.Column("status_history", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.add_column(sa.Column("milestones", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("development_programs") as batch_op:
        batch_op.drop_column("milestones")
        batch_op.drop_column("status_history")

    with op.batch_alter_table("target_profiles") as batch_op:
        batch_op.drop_index(op.f("ix_target_profiles_source_document_id"))
        batch_op.drop_constraint(
            op.f("fk_target_profiles_source_document_id_source_documents"),
            type_="foreignkey",
        )
        batch_op.drop_column("source_document_id")
