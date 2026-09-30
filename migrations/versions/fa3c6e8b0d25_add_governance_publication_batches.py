"""add governance publication batches

Revision ID: fa3c6e8b0d25
Revises: e9a2c5d7f604
Create Date: 2026-07-25 22:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fa3c6e8b0d25"
down_revision: str | Sequence[str] | None = "e9a2c5d7f604"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = (
    "governance_publication_batches",
    "governance_publication_batch_items",
    "fact_withdrawal_tombstones",
    "projection_maintenance_jobs",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TYPE governancestatus ADD VALUE IF NOT EXISTS 'WITHDRAWN'"))

    op.create_table(
        "governance_publication_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("preview_sha256", sa.String(length=64), nullable=False),
        sa.Column("expected_count", sa.Integer(), nullable=False),
        sa.Column("blocked_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reason", sa.String(length=4000), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("committed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("operation IN ('publish','withdraw')", name="ck_publication_batch_operation"),
        sa.CheckConstraint(
            "status IN ('previewed','committed','failed')",
            name="ck_publication_batch_status",
        ),
        sa.CheckConstraint("expected_count > 0", name="ck_publication_batch_expected_count"),
        sa.CheckConstraint("blocked_count >= 0", name="ck_publication_batch_blocked_count"),
        sa.ForeignKeyConstraint(["committed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key"),
    )
    for column in ("tenant_id", "operation", "status", "requested_by_user_id", "committed_by_user_id"):
        op.create_index(f"ix_governance_publication_batches_{column}", "governance_publication_batches", [column])
    op.create_index(
        "ix_publication_batches_tenant_status_created",
        "governance_publication_batches",
        ["tenant_id", "status", "created_at"],
    )
    op.create_table(
        "governance_publication_batch_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("publication_batch_id", sa.String(length=36), nullable=False),
        sa.Column("staged_fact_id", sa.String(length=36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("expected_status", sa.String(length=40), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_batch_id"], ["governance_publication_batches.id"]),
        sa.ForeignKeyConstraint(["staged_fact_id"], ["staged_facts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "publication_batch_id", "staged_fact_id"),
    )
    for column in ("tenant_id", "publication_batch_id", "staged_fact_id"):
        op.create_index(
            f"ix_governance_publication_batch_items_{column}",
            "governance_publication_batch_items",
            [column],
        )
    op.create_index(
        "ix_publication_batch_items_batch_position",
        "governance_publication_batch_items",
        ["publication_batch_id", "position"],
    )
    op.create_table(
        "fact_withdrawal_tombstones",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("staged_fact_id", sa.String(length=36), nullable=False),
        sa.Column("publication_batch_id", sa.String(length=36), nullable=False),
        sa.Column("withdrawn_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=4000), nullable=False),
        sa.Column("resource_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_batch_id"], ["governance_publication_batches.id"]),
        sa.ForeignKeyConstraint(["staged_fact_id"], ["staged_facts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["withdrawn_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "staged_fact_id"),
    )
    for column in ("tenant_id", "staged_fact_id", "publication_batch_id", "withdrawn_by_user_id", "created_at"):
        op.create_index(f"ix_fact_withdrawal_tombstones_{column}", "fact_withdrawal_tombstones", [column])
    op.create_index(
        "ix_fact_withdrawal_tombstones_batch_created",
        "fact_withdrawal_tombstones",
        ["publication_batch_id", "created_at"],
    )
    op.create_table(
        "projection_maintenance_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("active_key", sa.String(length=40), nullable=True),
        sa.Column("build_id", sa.String(length=80), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_projection_maintenance_attempts"),
        sa.CheckConstraint(
            "operation IN ('consistency_check','rebuild')",
            name="ck_projection_maintenance_operation",
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed')",
            name="ck_projection_maintenance_status",
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("active_key"),
    )
    for column in (
        "tenant_id",
        "operation",
        "status",
        "build_id",
        "requested_by_user_id",
        "worker_id",
        "lease_expires_at",
    ):
        op.create_index(f"ix_projection_maintenance_jobs_{column}", "projection_maintenance_jobs", [column])
    op.create_index(
        "ix_projection_maintenance_jobs_status_created",
        "projection_maintenance_jobs",
        ["status", "created_at"],
    )

    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in RLS_TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_fact_tombstone_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'fact withdrawal tombstones are append-only'; END; $$"
            )
        )
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_fact_withdrawal_tombstones" '
                'BEFORE UPDATE OR DELETE ON "fact_withdrawal_tombstones" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_fact_tombstone_mutation()"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER "immutable_fact_withdrawal_tombstones" ON "fact_withdrawal_tombstones"'))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_fact_tombstone_mutation()"))
    op.drop_table("projection_maintenance_jobs")
    op.drop_table("fact_withdrawal_tombstones")
    op.drop_table("governance_publication_batch_items")
    op.drop_table("governance_publication_batches")

    if bind.dialect.name == "postgresql":
        op.execute(sa.text("UPDATE staged_facts SET status='REJECTED' WHERE status='WITHDRAWN'"))
        op.execute(sa.text("ALTER TYPE governancestatus RENAME TO governancestatus_with_withdrawn"))
        op.execute(
            sa.text(
                "CREATE TYPE governancestatus AS ENUM "
                "('PROPOSED','VALIDATED','CONFLICT','REVIEW_PENDING','APPROVED','REJECTED','PUBLISHED')"
            )
        )
        for table in ("staged_facts", "review_tasks"):
            op.execute(
                sa.text(
                    f'ALTER TABLE "{table}" ALTER COLUMN status TYPE governancestatus '
                    "USING status::text::governancestatus"
                )
            )
        op.execute(sa.text("DROP TYPE governancestatus_with_withdrawn"))
