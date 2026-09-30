"""add billing dispute workflow

Revision ID: 3c6f9a1d8b42
Revises: 2b5e8f1a7c93
Create Date: 2026-07-18 19:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c6f9a1d8b42"
down_revision: str | Sequence[str] | None = "2b5e8f1a7c93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_disputes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("dispute_key", sa.String(length=120), nullable=False),
        sa.Column("billing_account_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("statement_id", sa.String(length=36), nullable=False),
        sa.Column("invoice_reference_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("disputed_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=4000), nullable=False),
        sa.Column("opened_by", sa.String(length=500), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_to", sa.String(length=500), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_code", sa.String(length=40), nullable=True),
        sa.Column("resolution_notes", sa.String(length=4000), nullable=False),
        sa.Column("resolved_by", sa.String(length=500), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_adjustment_key", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'rejected', 'cancelled')",
            name="ck_billing_dispute_status",
        ),
        sa.CheckConstraint(
            "category IN ('usage', 'pricing', 'duplicate', 'authorization', 'service', 'other')",
            name="ck_billing_dispute_category",
        ),
        sa.CheckConstraint("disputed_units > 0", name="ck_billing_dispute_positive_units"),
        sa.CheckConstraint("version > 0", name="ck_billing_dispute_version"),
        sa.CheckConstraint(
            "(status IN ('open', 'investigating') AND resolved_at IS NULL AND resolved_by IS NULL "
            "AND resolution_code IS NULL) OR "
            "(status = 'resolved' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code IN ('credit', 'no_credit')) OR "
            "(status = 'rejected' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code = 'rejected') OR "
            "(status = 'cancelled' AND resolved_at IS NOT NULL AND resolved_by IS NOT NULL "
            "AND resolution_code = 'cancelled')",
            name="ck_billing_dispute_resolution_state",
        ),
        sa.CheckConstraint(
            "resolution_adjustment_key IS NULL OR (status = 'resolved' AND resolution_code = 'credit')",
            name="ck_billing_dispute_adjustment_state",
        ),
        sa.ForeignKeyConstraint(["billing_account_id"], ["billing_accounts.id"]),
        sa.ForeignKeyConstraint(["invoice_reference_id"], ["invoice_references.id"]),
        sa.ForeignKeyConstraint(["statement_id"], ["billing_period_statements.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["commercial_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "dispute_key"),
    )
    for column in (
        "tenant_id",
        "billing_account_id",
        "subscription_id",
        "statement_id",
        "invoice_reference_id",
        "status",
        "category",
        "opened_at",
        "assigned_to",
        "due_at",
        "resolved_at",
    ):
        op.create_index(f"ix_billing_disputes_{column}", "billing_disputes", [column])

    op.create_table(
        "billing_dispute_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("dispute_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=500), nullable=False),
        sa.Column("operation_key", sa.String(length=120), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("note", sa.String(length=4000), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('opened', 'investigating', 'resolved', 'rejected', 'cancelled')",
            name="ck_billing_dispute_event_type",
        ),
        sa.ForeignKeyConstraint(["dispute_id"], ["billing_disputes.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "dispute_id", "operation_key", name="uq_billing_dispute_operation"),
    )
    for column in ("tenant_id", "dispute_id", "event_type", "request_id", "occurred_at"):
        op.create_index(f"ix_billing_dispute_events_{column}", "billing_dispute_events", [column])

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in ("billing_disputes", "billing_dispute_events"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_billing_dispute_history" '
                'BEFORE UPDATE OR DELETE ON "billing_dispute_events" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_commercial_history_mutation()"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER IF EXISTS "immutable_billing_dispute_history" ON "billing_dispute_events"'))
        for table in ("billing_dispute_events", "billing_disputes"):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("billing_dispute_events")
    op.drop_table("billing_disputes")
