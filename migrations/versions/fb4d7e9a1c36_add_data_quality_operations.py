"""add data quality operations

Revision ID: fb4d7e9a1c36
Revises: fa3c6e8b0d25
Create Date: 2026-07-25 19:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fb4d7e9a1c36"
down_revision: str | Sequence[str] | None = "fa3c6e8b0d25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = ("data_quality_snapshots", "data_quality_issues", "data_quality_issue_events")


def upgrade() -> None:
    op.create_table(
        "data_quality_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("trigger", sa.String(length=40), nullable=False),
        sa.Column("definitions_version", sa.String(length=40), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "trigger IN ('scheduled','manual')",
            name="ck_data_quality_snapshot_trigger",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "trigger", "measured_at"):
        op.create_index(f"ix_data_quality_snapshots_{column}", "data_quality_snapshots", [column])
    op.create_index(
        "ix_quality_snapshots_tenant_measured",
        "data_quality_snapshots",
        ["tenant_id", "measured_at"],
    )
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("active_key", sa.String(length=160), nullable=True),
        sa.Column("metric_key", sa.String(length=120), nullable=False),
        sa.Column("scope_type", sa.String(length=40), nullable=False),
        sa.Column("scope_id", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("comparison", sa.String(length=8), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("last_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open','acknowledged','ready_to_resolve','resolved','waived')",
            name="ck_data_quality_issue_status",
        ),
        sa.CheckConstraint(
            "severity IN ('critical','high','medium','low')",
            name="ck_data_quality_issue_severity",
        ),
        sa.CheckConstraint(
            "comparison IN ('gte','lte')",
            name="ck_data_quality_issue_comparison",
        ),
        sa.CheckConstraint("version > 0", name="ck_data_quality_issue_version"),
        sa.ForeignKeyConstraint(["last_snapshot_id"], ["data_quality_snapshots.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "active_key"),
    )
    for column in (
        "tenant_id",
        "metric_key",
        "scope_type",
        "scope_id",
        "status",
        "severity",
        "owner_user_id",
        "sla_due_at",
        "last_snapshot_id",
    ):
        op.create_index(f"ix_data_quality_issues_{column}", "data_quality_issues", [column])
    op.create_index(
        "ix_quality_issues_tenant_status_due",
        "data_quality_issues",
        ["tenant_id", "status", "sla_due_at"],
    )
    op.create_table(
        "data_quality_issue_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("issue_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=200), nullable=False),
        sa.Column("previous_status", sa.String(length=24), nullable=True),
        sa.Column("resulting_status", sa.String(length=24), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["data_quality_issues.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "issue_id", "action", "occurred_at"):
        op.create_index(f"ix_data_quality_issue_events_{column}", "data_quality_issue_events", [column])
    op.create_index(
        "ix_quality_issue_events_issue_occurred",
        "data_quality_issue_events",
        ["issue_id", "occurred_at"],
    )

    bind = op.get_bind()
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
                "CREATE FUNCTION platform_private.reject_quality_event_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'data quality issue events are append-only'; END; $$"
            )
        )
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_data_quality_issue_events" '
                'BEFORE UPDATE OR DELETE ON "data_quality_issue_events" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_quality_event_mutation()"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER "immutable_data_quality_issue_events" ON "data_quality_issue_events"'))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_quality_event_mutation()"))
    op.drop_table("data_quality_issue_events")
    op.drop_table("data_quality_issues")
    op.drop_table("data_quality_snapshots")
