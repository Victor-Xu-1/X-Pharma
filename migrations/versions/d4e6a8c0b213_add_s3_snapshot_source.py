"""add S3 snapshot source

Revision ID: d4e6a8c0b213
Revises: 8a4c1e7d2f90
Create Date: 2026-07-17 22:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e6a8c0b213"
down_revision: str | Sequence[str] | None = "8a4c1e7d2f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        op.execute("ALTER TYPE datasourcetype ADD VALUE IF NOT EXISTS 'S3_SNAPSHOT'")
    elif dialect_name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.Enum("FOLDER", "HTTP_MANIFEST", name="datasourcetype"),
                type_=sa.Enum("FOLDER", "HTTP_MANIFEST", "S3_SNAPSHOT", name="datasourcetype"),
                existing_nullable=False,
            )
    op.add_column("source_assets", sa.Column("source_fingerprint", sa.String(length=64), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    in_use = connection.scalar(sa.text("SELECT count(*) FROM data_sources WHERE source_type = 'S3_SNAPSHOT'"))
    if in_use:
        raise RuntimeError("Cannot remove S3_SNAPSHOT while S3 snapshot data sources exist")
    op.drop_column("source_assets", "source_fingerprint")
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.Enum("FOLDER", "HTTP_MANIFEST", "S3_SNAPSHOT", name="datasourcetype"),
                type_=sa.Enum("FOLDER", "HTTP_MANIFEST", name="datasourcetype"),
                existing_nullable=False,
            )
        return
    if connection.dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE datasourcetype RENAME TO datasourcetype_with_s3_snapshot")
    op.execute("CREATE TYPE datasourcetype AS ENUM ('FOLDER', 'HTTP_MANIFEST')")
    op.execute(
        "ALTER TABLE data_sources ALTER COLUMN source_type TYPE datasourcetype USING source_type::text::datasourcetype"
    )
    op.execute("DROP TYPE datasourcetype_with_s3_snapshot")
