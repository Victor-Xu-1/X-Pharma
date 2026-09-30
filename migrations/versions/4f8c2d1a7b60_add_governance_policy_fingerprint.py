"""add immutable governance policy fingerprint

Revision ID: 4f8c2d1a7b60
Revises: 9a2d4f6b8c10
Create Date: 2026-07-22 14:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4f8c2d1a7b60"
down_revision: str | Sequence[str] | None = "9a2d4f6b8c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_POLICY_SHA256 = "0" * 64
_OLD_UNIQUE_CONSTRAINT = "extraction_runs_tenant_id_source_version_id_schema_name_sch_key"
_NEW_UNIQUE_CONSTRAINT = "uq_extraction_runs_policy_identity"
_POLICY_INDEX = "ix_extraction_runs_version_policy_status"
_SQLITE_NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("extraction_runs") as batch:
            batch.add_column(sa.Column("policy_sha256", sa.String(length=64), nullable=True))
    else:
        op.add_column("extraction_runs", sa.Column("policy_sha256", sa.String(length=64), nullable=True))
    op.execute(
        sa.text("UPDATE extraction_runs SET policy_sha256 = :legacy WHERE policy_sha256 IS NULL").bindparams(
            legacy=_LEGACY_POLICY_SHA256
        )
    )
    columns = [
        "tenant_id",
        "source_version_id",
        "schema_name",
        "schema_version",
        "input_sha256",
        "policy_sha256",
    ]
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table(
            "extraction_runs",
            naming_convention=_SQLITE_NAMING_CONVENTION,
            recreate="always",
        ) as batch:
            batch.alter_column("policy_sha256", existing_type=sa.String(length=64), nullable=False)
            batch.drop_constraint("uq_extraction_runs_tenant_id", type_="unique")
            batch.create_unique_constraint(_NEW_UNIQUE_CONSTRAINT, columns)
            batch.create_index(_POLICY_INDEX, ["source_version_id", "policy_sha256", "status"], unique=False)
    else:
        op.alter_column("extraction_runs", "policy_sha256", existing_type=sa.String(length=64), nullable=False)
        op.drop_constraint(_OLD_UNIQUE_CONSTRAINT, "extraction_runs", type_="unique")
        op.create_unique_constraint(_NEW_UNIQUE_CONSTRAINT, "extraction_runs", columns)
        op.create_index(
            _POLICY_INDEX,
            "extraction_runs",
            ["source_version_id", "policy_sha256", "status"],
            unique=False,
        )


def downgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text(
            """
            SELECT 1
            FROM extraction_runs
            GROUP BY tenant_id, source_version_id, schema_name, schema_version, input_sha256
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot downgrade governance policy fingerprints after multiple policy versions exist; "
            "use forward recovery to preserve immutable extraction history."
        )
    old_columns = ["tenant_id", "source_version_id", "schema_name", "schema_version", "input_sha256"]
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table(
            "extraction_runs",
            naming_convention=_SQLITE_NAMING_CONVENTION,
            recreate="always",
        ) as batch:
            batch.drop_index(_POLICY_INDEX)
            batch.drop_constraint(_NEW_UNIQUE_CONSTRAINT, type_="unique")
            batch.create_unique_constraint(_OLD_UNIQUE_CONSTRAINT, old_columns)
            batch.drop_column("policy_sha256")
    else:
        op.drop_index(_POLICY_INDEX, table_name="extraction_runs")
        op.drop_constraint(_NEW_UNIQUE_CONSTRAINT, "extraction_runs", type_="unique")
        op.create_unique_constraint(_OLD_UNIQUE_CONSTRAINT, "extraction_runs", old_columns)
        op.drop_column("extraction_runs", "policy_sha256")
