"""add source quarantine decisions

Revision ID: e9a2c5d7f604
Revises: d8f1b4c6e593
Create Date: 2026-07-25 19:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9a2c5d7f604"
down_revision: str | Sequence[str] | None = "d8f1b4c6e593"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

QUARANTINE_STATUSES = (
    "NOT_APPLICABLE",
    "PENDING_REVIEW",
    "HELD",
    "RESCAN_REQUESTED",
    "REJECTED",
    "CLEARED",
)
RLS_TABLES = (
    "ingestion_run_operations",
    "source_version_operations",
    "source_version_quarantine_decisions",
)


def _quarantine_status() -> sa.Enum:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(*QUARANTINE_STATUSES, name="quarantinestatus", create_type=False)
    return sa.Enum(*QUARANTINE_STATUSES, name="quarantinestatus")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(*QUARANTINE_STATUSES, name="quarantinestatus").create(bind, checkfirst=True)
    quarantine_status = _quarantine_status()
    quarantine_columns = (
        sa.Column(
            "quarantine_status",
            quarantine_status,
            server_default="NOT_APPLICABLE",
            nullable=False,
        ),
        sa.Column("quarantine_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("quarantine_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("source_versions") as batch:
            for column in quarantine_columns:
                batch.add_column(column)
            batch.create_check_constraint(
                "ck_source_version_quarantine_version",
                "quarantine_version >= 0",
            )
    else:
        for column in quarantine_columns:
            op.add_column("source_versions", column)
        op.create_check_constraint(
            "ck_source_version_quarantine_version",
            "source_versions",
            "quarantine_version >= 0",
        )
    op.create_index(
        "ix_source_versions_quarantine_status",
        "source_versions",
        ["quarantine_status"],
    )
    op.create_index(
        "ix_source_versions_quarantine_updated_at",
        "source_versions",
        ["quarantine_updated_at"],
    )
    op.add_column(
        "source_version_operations",
        sa.Column("expected_quarantine_version", sa.Integer(), nullable=True),
    )
    op.create_table(
        "source_version_quarantine_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("source_version_id", sa.String(length=36), nullable=False),
        sa.Column("operation_key", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column("previous_status", quarantine_status, nullable=False),
        sa.Column("resulting_status", quarantine_status, nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=200), nullable=False),
        sa.Column("workflow_id", sa.String(length=200), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expected_version >= 0", name="ck_quarantine_decision_expected_version"),
        sa.CheckConstraint(
            "resulting_version = expected_version + 1",
            name="ck_quarantine_decision_resulting_version",
        ),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "operation_key",
            name="uq_source_version_quarantine_decision_key",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "source_version_id",
            "resulting_version",
            name="uq_source_version_quarantine_decision_version",
        ),
    )
    op.create_index(
        "ix_source_version_quarantine_decisions_tenant_id",
        "source_version_quarantine_decisions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_source_version_quarantine_decisions_source_version_id",
        "source_version_quarantine_decisions",
        ["source_version_id"],
    )
    op.create_index(
        "ix_source_version_quarantine_decisions_action",
        "source_version_quarantine_decisions",
        ["action"],
    )
    op.create_index(
        "ix_source_version_quarantine_decisions_created_at",
        "source_version_quarantine_decisions",
        ["created_at"],
    )
    op.create_index(
        "ix_source_version_quarantine_decisions_version_created",
        "source_version_quarantine_decisions",
        ["source_version_id", "created_at"],
    )
    op.execute(
        sa.text(
            "UPDATE source_versions SET quarantine_status='PENDING_REVIEW', "
            "quarantine_version=1, quarantine_updated_at=COALESCE(malware_scanned_at, discovered_at) "
            "WHERE error_code='malware_detected'"
        )
    )
    backfill = sa.text(
        "INSERT INTO source_version_quarantine_decisions "
        "(id, tenant_id, source_version_id, operation_key, action, expected_version, resulting_version, "
        "previous_status, resulting_status, reason, actor_type, actor_id, workflow_id, details, created_at) "
        "SELECT id, tenant_id, id, 'migration:malware-detected:' || id, 'scan_detected', 0, 1, "
        "'NOT_APPLICABLE', 'PENDING_REVIEW', 'Imported malware detection requires operator review', "
        "'system', 'migration', NULL, :empty_details, COALESCE(malware_scanned_at, discovered_at) "
        "FROM source_versions WHERE error_code='malware_detected'"
    ).bindparams(sa.bindparam("empty_details", value={}, type_=sa.JSON()))
    op.execute(backfill)
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_quarantine_decision_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'quarantine decisions are append-only'; END; $$"
            )
        )
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in RLS_TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )
        op.execute(
            sa.text(
                "CREATE TRIGGER immutable_source_version_quarantine_decisions "
                "BEFORE UPDATE OR DELETE ON source_version_quarantine_decisions "
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_quarantine_decision_mutation()"
            )
        )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("source_versions") as batch:
            batch.alter_column(
                "quarantine_status",
                existing_type=quarantine_status,
                server_default=None,
            )
            batch.alter_column(
                "quarantine_version",
                existing_type=sa.Integer(),
                server_default=None,
            )
    else:
        op.alter_column("source_versions", "quarantine_status", server_default=None)
        op.alter_column("source_versions", "quarantine_version", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in reversed(RLS_TABLES):
            op.execute(sa.text(f'DROP POLICY "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.execute(
            sa.text("DROP TRIGGER immutable_source_version_quarantine_decisions ON source_version_quarantine_decisions")
        )
        op.execute(sa.text("DROP FUNCTION platform_private.reject_quarantine_decision_mutation()"))
    op.drop_index(
        "ix_source_version_quarantine_decisions_version_created",
        table_name="source_version_quarantine_decisions",
    )
    op.drop_index(
        "ix_source_version_quarantine_decisions_created_at",
        table_name="source_version_quarantine_decisions",
    )
    op.drop_index(
        "ix_source_version_quarantine_decisions_action",
        table_name="source_version_quarantine_decisions",
    )
    op.drop_index(
        "ix_source_version_quarantine_decisions_source_version_id",
        table_name="source_version_quarantine_decisions",
    )
    op.drop_index(
        "ix_source_version_quarantine_decisions_tenant_id",
        table_name="source_version_quarantine_decisions",
    )
    op.drop_table("source_version_quarantine_decisions")
    op.drop_index("ix_source_versions_quarantine_updated_at", table_name="source_versions")
    op.drop_index("ix_source_versions_quarantine_status", table_name="source_versions")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("source_version_operations") as batch:
            batch.drop_column("expected_quarantine_version")
        with op.batch_alter_table("source_versions") as batch:
            batch.drop_constraint("ck_source_version_quarantine_version", type_="check")
            batch.drop_column("quarantine_updated_at")
            batch.drop_column("quarantine_version")
            batch.drop_column("quarantine_status")
    else:
        op.drop_column("source_version_operations", "expected_quarantine_version")
        op.drop_constraint(
            "ck_source_version_quarantine_version",
            "source_versions",
            type_="check",
        )
        op.drop_column("source_versions", "quarantine_updated_at")
        op.drop_column("source_versions", "quarantine_version")
        op.drop_column("source_versions", "quarantine_status")
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(*QUARANTINE_STATUSES, name="quarantinestatus").drop(bind, checkfirst=True)
