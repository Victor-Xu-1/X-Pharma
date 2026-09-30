"""add versioned program targets

Revision ID: ad7e3c1f9b42
Revises: fc5e8a1b3d72
Create Date: 2026-07-25 23:50:00
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ad7e3c1f9b42"
down_revision: str | Sequence[str] | None = "fc5e8a1b3d72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_VALUES = ("primary", "combination")


def _target_role() -> sa.Enum:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*_ROLE_VALUES, name="programtargetrole", create_type=False)
    return sa.Enum(*_ROLE_VALUES, name="programtargetrole")


def _backfill_targets(table: sa.Table) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, tenant_id, target_entity_id, source_document_id, created_at, updated_at "
            "FROM development_programs WHERE target_entity_id IS NOT NULL ORDER BY id"
        )
    ).mappings()
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(
            {
                "id": str(uuid.uuid4()),
                "tenant_id": row["tenant_id"],
                "program_id": row["id"],
                "target_set_version": 1,
                "target_entity_id": row["target_entity_id"],
                "role": "primary",
                "position": 0,
                "source_document_id": row["source_document_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        if len(batch) == 1000:
            bind.execute(table.insert(), batch)
            batch.clear()
    if batch:
        bind.execute(table.insert(), batch)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(*_ROLE_VALUES, name="programtargetrole").create(bind, checkfirst=True)
    with op.batch_alter_table("development_programs") as batch:
        batch.add_column(sa.Column("target_set_version", sa.Integer(), server_default="1", nullable=False))
        batch.add_column(sa.Column("target_combination_key", sa.String(length=760), nullable=True))
        batch.create_check_constraint("ck_development_program_target_set_version", "target_set_version > 0")
        batch.create_index(
            "ix_development_programs_target_combination_key",
            ["target_combination_key"],
        )
        batch.create_index(
            "ix_program_target_combination_lookup",
            ["tenant_id", "target_combination_key"],
        )

    target_role = _target_role()
    op.create_table(
        "development_program_targets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("program_id", sa.String(length=36), nullable=False),
        sa.Column("target_set_version", sa.Integer(), nullable=False),
        sa.Column("target_entity_id", sa.String(length=36), nullable=False),
        sa.Column("role", target_role, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("target_set_version > 0", name="ck_program_target_set_version"),
        sa.CheckConstraint("position >= 0 AND position < 20", name="ck_program_target_position"),
        sa.ForeignKeyConstraint(["program_id"], ["development_programs.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["target_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "program_id",
            "target_set_version",
            "target_entity_id",
            name="uq_program_target_version_entity",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "program_id",
            "target_set_version",
            "position",
            name="uq_program_target_version_position",
        ),
    )
    for column in (
        "tenant_id",
        "program_id",
        "target_set_version",
        "target_entity_id",
        "role",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_development_program_targets_{column}"), "development_program_targets", [column])
    op.create_index(
        "ix_program_targets_current_lookup",
        "development_program_targets",
        ["tenant_id", "program_id", "target_set_version", "position"],
    )
    op.create_index(
        "ix_program_targets_target_lookup",
        "development_program_targets",
        ["tenant_id", "target_entity_id", "program_id", "target_set_version"],
    )

    target_table = sa.table(
        "development_program_targets",
        sa.column("id", sa.String(length=36)),
        sa.column("tenant_id", sa.String(length=36)),
        sa.column("program_id", sa.String(length=36)),
        sa.column("target_set_version", sa.Integer()),
        sa.column("target_entity_id", sa.String(length=36)),
        sa.column("role", target_role),
        sa.column("position", sa.Integer()),
        sa.column("source_document_id", sa.String(length=36)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    _backfill_targets(target_table)
    op.execute(
        sa.text(
            "UPDATE development_programs SET target_combination_key=target_entity_id "
            "WHERE target_entity_id IS NOT NULL"
        )
    )

    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "development_program_targets" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "development_program_targets" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "development_program_targets" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_program_target_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'program target history is append-only'; END; $$"
            )
        )
        op.execute(
            sa.text(
                "CREATE TRIGGER immutable_development_program_targets "
                "BEFORE UPDATE OR DELETE ON development_program_targets "
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_program_target_mutation()"
            )
        )
    with op.batch_alter_table("development_programs") as batch:
        batch.alter_column("target_set_version", existing_type=sa.Integer(), server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TRIGGER immutable_development_program_targets ON development_program_targets"))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_program_target_mutation()"))
        op.execute(sa.text('DROP POLICY "tenant_isolation" ON "development_program_targets"'))
        op.execute(sa.text('ALTER TABLE "development_program_targets" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "development_program_targets" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("development_program_targets")
    with op.batch_alter_table("development_programs") as batch:
        batch.drop_index("ix_program_target_combination_lookup")
        batch.drop_index("ix_development_programs_target_combination_key")
        batch.drop_constraint("ck_development_program_target_set_version", type_="check")
        batch.drop_column("target_combination_key")
        batch.drop_column("target_set_version")
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(*_ROLE_VALUES, name="programtargetrole").drop(bind, checkfirst=True)
