"""expand pipeline regional phase and rights intelligence

Revision ID: 5d7e1a3c9b24
Revises: 3b6d9f2a5c87
Create Date: 2026-07-24 09:15:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d7e1a3c9b24"
down_revision: str | Sequence[str] | None = "3b6d9f2a5c87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEVELOPMENT_PHASES = (
    "'discovery','preclinical','ind','phase_1','phase_1_2','phase_2','phase_2_3','phase_3',"
    "'filed','approved','discontinued'"
)
_INDEXED_COLUMNS = (
    "global_phase",
    "china_phase",
    "global_phase_started_at",
    "china_phase_started_at",
)


def upgrade() -> None:
    columns = (
        sa.Column("global_phase", sa.String(length=40), nullable=True),
        sa.Column("china_phase", sa.String(length=40), nullable=True),
        sa.Column("global_phase_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("china_phase_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("development_rights_regions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("commercialization_rights_regions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("program_tags", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    for column in columns:
        op.add_column("development_programs", column)

    with op.batch_alter_table("development_programs") as batch_op:
        batch_op.create_check_constraint(
            "ck_program_global_phase",
            f"global_phase IS NULL OR global_phase IN ({_DEVELOPMENT_PHASES})",
        )
        batch_op.create_check_constraint(
            "ck_program_china_phase",
            f"china_phase IS NULL OR china_phase IN ({_DEVELOPMENT_PHASES})",
        )
        batch_op.create_check_constraint(
            "ck_program_global_phase_date_requires_phase",
            "global_phase_started_at IS NULL OR global_phase IS NOT NULL",
        )
        batch_op.create_check_constraint(
            "ck_program_china_phase_date_requires_phase",
            "china_phase_started_at IS NULL OR china_phase IS NOT NULL",
        )
        for column in _INDEXED_COLUMNS:
            batch_op.create_index(op.f(f"ix_development_programs_{column}"), [column])
        batch_op.create_index(
            "ix_program_regional_phase",
            ["tenant_id", "global_phase", "china_phase"],
        )
        for column in (
            "development_rights_regions",
            "commercialization_rights_regions",
            "program_tags",
        ):
            batch_op.alter_column(column, server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("development_programs") as batch_op:
        batch_op.drop_index("ix_program_regional_phase")
        for column in reversed(_INDEXED_COLUMNS):
            batch_op.drop_index(op.f(f"ix_development_programs_{column}"))
        batch_op.drop_constraint("ck_program_china_phase_date_requires_phase", type_="check")
        batch_op.drop_constraint("ck_program_global_phase_date_requires_phase", type_="check")
        batch_op.drop_constraint("ck_program_china_phase", type_="check")
        batch_op.drop_constraint("ck_program_global_phase", type_="check")
        for column in reversed(
            (
                "global_phase",
                "china_phase",
                "global_phase_started_at",
                "china_phase_started_at",
                "development_rights_regions",
                "commercialization_rights_regions",
                "program_tags",
            )
        ):
            batch_op.drop_column(column)
