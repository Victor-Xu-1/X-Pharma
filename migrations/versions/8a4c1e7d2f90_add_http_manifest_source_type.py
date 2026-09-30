"""add HTTP manifest source type

Revision ID: 8a4c1e7d2f90
Revises: 7f3b9d2a6c81
Create Date: 2026-07-17 21:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a4c1e7d2f90"
down_revision: str | Sequence[str] | None = "7f3b9d2a6c81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    dialect_name = op.get_bind().dialect.name
    if dialect_name == "postgresql":
        op.execute("ALTER TYPE datasourcetype ADD VALUE IF NOT EXISTS 'HTTP_MANIFEST'")
    elif dialect_name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.String(length=6),
                type_=sa.Enum("FOLDER", "HTTP_MANIFEST", name="datasourcetype"),
                existing_nullable=False,
            )


def downgrade() -> None:
    connection = op.get_bind()
    in_use = connection.scalar(sa.text("SELECT count(*) FROM data_sources WHERE source_type = 'HTTP_MANIFEST'"))
    if in_use:
        raise RuntimeError("Cannot remove HTTP_MANIFEST while HTTP manifest data sources exist")
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("data_sources") as batch_op:
            batch_op.alter_column(
                "source_type",
                existing_type=sa.Enum("FOLDER", "HTTP_MANIFEST", name="datasourcetype"),
                type_=sa.Enum("FOLDER", name="datasourcetype"),
                existing_nullable=False,
            )
        return
    if connection.dialect.name != "postgresql":
        return
    op.execute("ALTER TYPE datasourcetype RENAME TO datasourcetype_with_http_manifest")
    op.execute("CREATE TYPE datasourcetype AS ENUM ('FOLDER')")
    op.execute(
        "ALTER TABLE data_sources ALTER COLUMN source_type TYPE datasourcetype USING source_type::text::datasourcetype"
    )
    op.execute("DROP TYPE datasourcetype_with_http_manifest")
