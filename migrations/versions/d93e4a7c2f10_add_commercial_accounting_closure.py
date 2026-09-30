"""add commercial accounting closure

Revision ID: d93e4a7c2f10
Revises: 6b4a2f9d7e31
Create Date: 2026-07-16 02:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d93e4a7c2f10"
down_revision: str | Sequence[str] | None = "6b4a2f9d7e31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TENANT_TABLES = (
    "commercial_reconciliation_runs",
    "billing_period_statements",
)


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"
    if is_postgres:
        op.execute(sa.text('DROP TRIGGER IF EXISTS "immutable_commercial_history" ON "billing_adjustments"'))

    with op.batch_alter_table("billing_adjustments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "adjustment_kind",
                sa.String(length=40),
                server_default="usage_adjustment",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("reverses_settlement_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("request_id", sa.String(length=100), server_default="schema-migration", nullable=False)
        )
        batch_op.add_column(
            sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )
        batch_op.create_foreign_key(
            "fk_billing_adjustments_reverses_settlement_id",
            "usage_settlements",
            ["reverses_settlement_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_billing_adjustment_single_reversal",
            ["tenant_id", "reverses_adjustment_id"],
        )
        batch_op.create_unique_constraint(
            "uq_billing_settlement_single_reversal",
            ["tenant_id", "reverses_settlement_id"],
        )
        batch_op.create_check_constraint(
            "ck_billing_adjustment_kind",
            "adjustment_kind IN ('usage_adjustment', 'settlement_reversal', 'adjustment_reversal')",
        )
        batch_op.create_check_constraint(
            "ck_billing_adjustment_reference",
            "(adjustment_kind = 'usage_adjustment' "
            "AND reverses_adjustment_id IS NULL AND reverses_settlement_id IS NULL) "
            "OR (adjustment_kind = 'settlement_reversal' "
            "AND reverses_adjustment_id IS NULL AND reverses_settlement_id IS NOT NULL AND units_delta < 0) "
            "OR (adjustment_kind = 'adjustment_reversal' "
            "AND reverses_adjustment_id IS NOT NULL AND reverses_settlement_id IS NULL)",
        )
    op.create_index(
        "ix_billing_adjustments_reverses_settlement_id",
        "billing_adjustments",
        ["reverses_settlement_id"],
    )
    op.create_index("ix_billing_adjustments_request_id", "billing_adjustments", ["request_id"])

    with op.batch_alter_table("commercial_ledger_entries") as batch_op:
        batch_op.add_column(sa.Column("adjustment_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_commercial_ledger_entries_adjustment_id",
            "billing_adjustments",
            ["adjustment_id"],
            ["id"],
        )
    op.create_index(
        "ix_commercial_ledger_entries_adjustment_id",
        "commercial_ledger_entries",
        ["adjustment_id"],
    )

    op.create_table(
        "commercial_reconciliation_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("run_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_granted_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("snapshot_reserved_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("snapshot_consumed_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("ledger_granted_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("ledger_reserved_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("ledger_consumed_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("source_granted_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("source_reserved_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("source_consumed_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("issues_json", sa.JSON(), nullable=False),
        sa.Column("requested_by", sa.String(length=500), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('clean', 'drift')", name="ck_commercial_reconciliation_status"),
        sa.CheckConstraint("issue_count >= 0", name="ck_commercial_reconciliation_issue_count"),
        sa.ForeignKeyConstraint(["subscription_id"], ["commercial_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_key"),
    )
    for column in ("tenant_id", "subscription_id", "status", "request_id", "completed_at"):
        op.create_index(
            f"ix_commercial_reconciliation_runs_{column}",
            "commercial_reconciliation_runs",
            [column],
        )

    op.create_table(
        "billing_period_statements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("billing_account_id", sa.String(length=36), nullable=False),
        sa.Column("statement_key", sa.String(length=200), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settlement_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("adjustment_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("net_consumed_units", sa.Numeric(28, 8), nullable=False),
        sa.Column("settlement_count", sa.Integer(), nullable=False),
        sa.Column("adjustment_count", sa.Integer(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("response_bytes", sa.Integer(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("signature_key_id", sa.String(length=120), nullable=False),
        sa.Column("manifest_signature", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("generated_by", sa.String(length=500), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("period_end > period_start", name="ck_billing_statement_period"),
        sa.CheckConstraint("revision > 0", name="ck_billing_statement_revision"),
        sa.CheckConstraint("settlement_count >= 0", name="ck_billing_statement_settlement_count"),
        sa.CheckConstraint("adjustment_count >= 0", name="ck_billing_statement_adjustment_count"),
        sa.CheckConstraint("result_count >= 0", name="ck_billing_statement_result_count"),
        sa.CheckConstraint("response_bytes >= 0", name="ck_billing_statement_response_bytes"),
        sa.ForeignKeyConstraint(["billing_account_id"], ["billing_accounts.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["commercial_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "statement_key"),
        sa.UniqueConstraint("tenant_id", "manifest_sha256", name="uq_billing_statement_manifest"),
        sa.UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "period_start",
            "period_end",
            "revision",
            name="uq_billing_statement_period_revision",
        ),
    )
    for column in (
        "tenant_id",
        "subscription_id",
        "billing_account_id",
        "period_start",
        "period_end",
        "request_id",
        "generated_at",
    ):
        op.create_index(f"ix_billing_period_statements_{column}", "billing_period_statements", [column])

    with op.batch_alter_table("invoice_references") as batch_op:
        batch_op.add_column(sa.Column("statement_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("request_id", sa.String(length=100), nullable=True))
        batch_op.create_foreign_key(
            "fk_invoice_references_statement_id",
            "billing_period_statements",
            ["statement_id"],
            ["id"],
        )
        batch_op.create_unique_constraint("uq_invoice_reference_statement", ["statement_id"])
    op.create_index("ix_invoice_references_statement_id", "invoice_references", ["statement_id"])
    op.create_index("ix_invoice_references_request_id", "invoice_references", ["request_id"])

    with op.batch_alter_table("billing_adjustments") as batch_op:
        batch_op.alter_column("adjustment_kind", server_default=None)
        batch_op.alter_column("request_id", server_default=None)
        batch_op.alter_column("metadata_json", server_default=None)

    if is_postgres:
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in NEW_TENANT_TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f'CREATE POLICY "tenant_isolation" ON "{table}" '
                    f"USING ({predicate}) WITH CHECK ({predicate})"
                )
            )
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "immutable_commercial_history" BEFORE UPDATE OR DELETE ON "{table}" '
                    "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_commercial_history_mutation()"
                )
            )
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_commercial_history" BEFORE UPDATE OR DELETE ON "billing_adjustments" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_commercial_history_mutation()"
            )
        )


def downgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"
    if is_postgres:
        op.execute(sa.text('DROP TRIGGER IF EXISTS "immutable_commercial_history" ON "billing_adjustments"'))
        for table in reversed(NEW_TENANT_TABLES):
            op.execute(sa.text(f'DROP TRIGGER IF EXISTS "immutable_commercial_history" ON "{table}"'))
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))

    op.drop_index("ix_invoice_references_request_id", table_name="invoice_references")
    op.drop_index("ix_invoice_references_statement_id", table_name="invoice_references")
    with op.batch_alter_table("invoice_references") as batch_op:
        batch_op.drop_constraint("uq_invoice_reference_statement", type_="unique")
        batch_op.drop_constraint("fk_invoice_references_statement_id", type_="foreignkey")
        batch_op.drop_column("request_id")
        batch_op.drop_column("statement_id")

    op.drop_table("billing_period_statements")
    op.drop_table("commercial_reconciliation_runs")

    op.drop_index("ix_commercial_ledger_entries_adjustment_id", table_name="commercial_ledger_entries")
    with op.batch_alter_table("commercial_ledger_entries") as batch_op:
        batch_op.drop_constraint("fk_commercial_ledger_entries_adjustment_id", type_="foreignkey")
        batch_op.drop_column("adjustment_id")

    op.drop_index("ix_billing_adjustments_request_id", table_name="billing_adjustments")
    op.drop_index("ix_billing_adjustments_reverses_settlement_id", table_name="billing_adjustments")
    with op.batch_alter_table("billing_adjustments") as batch_op:
        batch_op.drop_constraint("ck_billing_adjustment_reference", type_="check")
        batch_op.drop_constraint("ck_billing_adjustment_kind", type_="check")
        batch_op.drop_constraint("uq_billing_settlement_single_reversal", type_="unique")
        batch_op.drop_constraint("uq_billing_adjustment_single_reversal", type_="unique")
        batch_op.drop_constraint("fk_billing_adjustments_reverses_settlement_id", type_="foreignkey")
        batch_op.drop_column("metadata_json")
        batch_op.drop_column("request_id")
        batch_op.drop_column("reverses_settlement_id")
        batch_op.drop_column("adjustment_kind")

    if is_postgres:
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_commercial_history" BEFORE UPDATE OR DELETE ON "billing_adjustments" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_commercial_history_mutation()"
            )
        )
