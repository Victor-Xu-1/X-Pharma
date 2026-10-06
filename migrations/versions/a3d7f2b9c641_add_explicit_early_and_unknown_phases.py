"""Preserve early clinical and unknown development stages.

Revision ID: a3d7f2b9c641
Revises: d32a6c1f9e74
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3d7f2b9c641"
down_revision = "d32a6c1f9e74"
branch_labels = None
depends_on = None

_OLD_VALUES = (
    "DISCOVERY",
    "PRECLINICAL",
    "IND",
    "PHASE_1",
    "PHASE_1_2",
    "PHASE_2",
    "PHASE_2_3",
    "PHASE_3",
    "FILED",
    "APPROVED",
    "DISCONTINUED",
)
_ADDED_VALUES = ("EARLY_PHASE_1", "UNKNOWN")
_NEW_VALUES = (*_OLD_VALUES, *_ADDED_VALUES)


def _text_phase_constraints(values: tuple[str, ...]) -> None:
    allowed = ",".join(f"'{value.lower()}'" for value in values)
    with op.batch_alter_table("development_programs") as batch:
        for column in ("global_phase", "china_phase"):
            batch.drop_constraint(f"ck_program_{column}", type_="check")
            batch.create_check_constraint(f"ck_program_{column}", f"{column} IS NULL OR {column} IN ({allowed})")
    with op.batch_alter_table("deal_asset_associations") as batch:
        batch.drop_constraint("ck_deal_asset_transaction_phase", type_="check")
        batch.create_check_constraint(
            "ck_deal_asset_transaction_phase",
            f"development_phase_at_transaction IS NULL OR development_phase_at_transaction IN ({allowed})",
        )


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")
        for value in _ADDED_VALUES:
            op.execute(sa.text(f"ALTER TYPE developmentphase ADD VALUE IF NOT EXISTS '{value}'"))
    elif connection.dialect.name == "sqlite":
        with op.batch_alter_table("development_programs") as batch:
            batch.alter_column(
                "phase",
                existing_type=sa.Enum(*_OLD_VALUES, name="developmentphase"),
                type_=sa.Enum(*_NEW_VALUES, name="developmentphase"),
                existing_nullable=False,
            )
    _text_phase_constraints(_NEW_VALUES)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE development_programs, deal_asset_associations IN ACCESS EXCLUSIVE MODE")
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM development_programs WHERE phase IN ('EARLY_PHASE_1', 'UNKNOWN') "
            "OR global_phase IN ('early_phase_1', 'unknown') OR china_phase IN ('early_phase_1', 'unknown')"
        )
    ):
        raise RuntimeError("Explicit early/unknown phase records require a preservation plan before downgrade")
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM deal_asset_associations "
            "WHERE development_phase_at_transaction IN ('early_phase_1', 'unknown')"
        )
    ):
        raise RuntimeError("Explicit early/unknown deal stages require a preservation plan before downgrade")
    _text_phase_constraints(_OLD_VALUES)
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("development_programs") as batch:
            batch.alter_column(
                "phase",
                existing_type=sa.Enum(*_NEW_VALUES, name="developmentphase"),
                type_=sa.Enum(*_OLD_VALUES, name="developmentphase"),
                existing_nullable=False,
            )
    elif connection.dialect.name == "postgresql":
        op.execute("ALTER TYPE developmentphase RENAME TO developmentphase_with_explicit_stages")
        values = ", ".join(f"'{value}'" for value in _OLD_VALUES)
        op.execute(sa.text(f"CREATE TYPE developmentphase AS ENUM ({values})"))
        op.execute(
            "ALTER TABLE development_programs ALTER COLUMN phase TYPE developmentphase "
            "USING phase::text::developmentphase"
        )
        op.execute("DROP TYPE developmentphase_with_explicit_stages")
