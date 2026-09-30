"""add ClinicalTrials.gov API source

Revision ID: 6a4e2d8f1c37
Revises: f3c8d5a2b740
Create Date: 2026-07-30 09:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6a4e2d8f1c37"
down_revision: str | Sequence[str] | None = "f3c8d5a2b740"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_VALUES = ("FOLDER", "HTTP_MANIFEST", "S3_SNAPSHOT", "SFTP_SNAPSHOT", "SMB_SNAPSHOT")
_NEW_VALUES = (*_OLD_VALUES, "CLINICALTRIALS_GOV")


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("ALTER TYPE datasourcetype ADD VALUE IF NOT EXISTS 'CLINICALTRIALS_GOV'")
    elif connection.dialect.name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.Enum(*_OLD_VALUES, name="datasourcetype"),
                type_=sa.Enum(*_NEW_VALUES, name="datasourcetype"),
                existing_nullable=False,
            )


def downgrade() -> None:
    connection = op.get_bind()
    in_use = connection.scalar(
        sa.text("SELECT count(*) FROM data_sources WHERE source_type = 'CLINICALTRIALS_GOV'")
    )
    if in_use:
        raise RuntimeError("Cannot remove CLINICALTRIALS_GOV while ClinicalTrials.gov sources exist")
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.Enum(*_NEW_VALUES, name="datasourcetype"),
                type_=sa.Enum(*_OLD_VALUES, name="datasourcetype"),
                existing_nullable=False,
            )
        return
    if connection.dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE datasourcetype RENAME TO datasourcetype_with_clinicaltrials_gov")
    op.execute(
        "CREATE TYPE datasourcetype AS ENUM "
        "('FOLDER', 'HTTP_MANIFEST', 'S3_SNAPSHOT', 'SFTP_SNAPSHOT', 'SMB_SNAPSHOT')"
    )
    op.execute(
        "ALTER TABLE data_sources ALTER COLUMN source_type TYPE datasourcetype "
        "USING source_type::text::datasourcetype"
    )
    op.execute("DROP TYPE datasourcetype_with_clinicaltrials_gov")
