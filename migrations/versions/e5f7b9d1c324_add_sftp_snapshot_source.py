"""add SFTP snapshot source

Revision ID: e5f7b9d1c324
Revises: d4e6a8c0b213
Create Date: 2026-07-17 19:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f7b9d1c324"
down_revision: str | Sequence[str] | None = "d4e6a8c0b213"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        op.execute("ALTER TYPE datasourcetype ADD VALUE IF NOT EXISTS 'SFTP_SNAPSHOT'")
    elif dialect_name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.Enum("FOLDER", "HTTP_MANIFEST", "S3_SNAPSHOT", name="datasourcetype"),
                type_=sa.Enum(
                    "FOLDER",
                    "HTTP_MANIFEST",
                    "S3_SNAPSHOT",
                    "SFTP_SNAPSHOT",
                    name="datasourcetype",
                ),
                existing_nullable=False,
            )


def downgrade() -> None:
    connection = op.get_bind()
    in_use = connection.scalar(sa.text("SELECT count(*) FROM data_sources WHERE source_type = 'SFTP_SNAPSHOT'"))
    if in_use:
        raise RuntimeError("Cannot remove SFTP_SNAPSHOT while SFTP snapshot data sources exist")
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.Enum(
                    "FOLDER",
                    "HTTP_MANIFEST",
                    "S3_SNAPSHOT",
                    "SFTP_SNAPSHOT",
                    name="datasourcetype",
                ),
                type_=sa.Enum("FOLDER", "HTTP_MANIFEST", "S3_SNAPSHOT", name="datasourcetype"),
                existing_nullable=False,
            )
        return
    if connection.dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE datasourcetype RENAME TO datasourcetype_with_sftp_snapshot")
    op.execute("CREATE TYPE datasourcetype AS ENUM ('FOLDER', 'HTTP_MANIFEST', 'S3_SNAPSHOT')")
    op.execute(
        "ALTER TABLE data_sources ALTER COLUMN source_type TYPE datasourcetype USING source_type::text::datasourcetype"
    )
    op.execute("DROP TYPE datasourcetype_with_sftp_snapshot")
