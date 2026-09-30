"""add PubMed E-utilities source

Revision ID: 8c6d2e4f1a90
Revises: 7b5f1e9c2d48
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c6d2e4f1a90"
down_revision: str | Sequence[str] | None = "7b5f1e9c2d48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_VALUES = (
    "FOLDER",
    "HTTP_MANIFEST",
    "CLINICALTRIALS_GOV",
    "S3_SNAPSHOT",
    "SFTP_SNAPSHOT",
    "SMB_SNAPSHOT",
)
_NEW_VALUES = (*_OLD_VALUES, "PUBMED")


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("ALTER TYPE datasourcetype ADD VALUE IF NOT EXISTS 'PUBMED'")
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
    in_use = connection.scalar(sa.text("SELECT count(*) FROM data_sources WHERE source_type = 'PUBMED'"))
    if in_use:
        raise RuntimeError("Cannot remove PUBMED while PubMed sources exist")
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
    op.execute("ALTER TYPE datasourcetype RENAME TO datasourcetype_with_pubmed")
    op.execute(
        "CREATE TYPE datasourcetype AS ENUM "
        "('FOLDER', 'HTTP_MANIFEST', 'CLINICALTRIALS_GOV', 'S3_SNAPSHOT', 'SFTP_SNAPSHOT', 'SMB_SNAPSHOT')"
    )
    op.execute(
        "ALTER TABLE data_sources ALTER COLUMN source_type TYPE datasourcetype USING source_type::text::datasourcetype"
    )
    op.execute("DROP TYPE datasourcetype_with_pubmed")
