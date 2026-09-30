"""add account scoped commercial risk policies

Revision ID: d46b8e0f3a52
Revises: c35a7d9e2f41
Create Date: 2026-07-16 15:30:00

"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "d46b8e0f3a52"
down_revision: str | Sequence[str] | None = "c35a7d9e2f41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_risk_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("billing_account_id", sa.String(length=36), nullable=False),
        sa.Column("policy_version", sa.String(length=100), server_default="risk-v1", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("account_daily_unique_record_limit", sa.Integer(), server_default="20000", nullable=False),
        sa.Column("partition_window_seconds", sa.Integer(), server_default="900", nullable=False),
        sa.Column("max_requests_per_window", sa.Integer(), server_default="50000", nullable=False),
        sa.Column("max_partition_queries_per_window", sa.Integer(), server_default="8", nullable=False),
        sa.Column(
            "max_cross_client_partition_queries_per_window",
            sa.Integer(),
            server_default="4",
            nullable=False,
        ),
        sa.Column("max_distinct_clients_per_window", sa.Integer(), server_default="20", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "account_daily_unique_record_limit > 0",
            name="ck_risk_account_daily_coverage",
        ),
        sa.CheckConstraint("partition_window_seconds > 0", name="ck_risk_partition_window"),
        sa.CheckConstraint("max_requests_per_window > 0", name="ck_risk_requests_per_window"),
        sa.CheckConstraint(
            "max_partition_queries_per_window > 0",
            name="ck_risk_partition_queries",
        ),
        sa.CheckConstraint(
            "max_cross_client_partition_queries_per_window > 0",
            name="ck_risk_cross_client_partition_queries",
        ),
        sa.CheckConstraint(
            "max_cross_client_partition_queries_per_window <= max_partition_queries_per_window",
            name="ck_risk_cross_client_within_partition_limit",
        ),
        sa.CheckConstraint(
            "max_distinct_clients_per_window > 0",
            name="ck_risk_distinct_clients",
        ),
        sa.ForeignKeyConstraint(["billing_account_id"], ["billing_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "billing_account_id"),
        sa.UniqueConstraint("billing_account_id"),
    )
    op.create_index(
        "ix_commercial_risk_policies_tenant_id",
        "commercial_risk_policies",
        ["tenant_id"],
    )
    op.create_index(
        "ix_commercial_risk_policies_billing_account_id",
        "commercial_risk_policies",
        ["billing_account_id"],
    )
    op.create_index(
        "ix_commercial_risk_policies_enabled",
        "commercial_risk_policies",
        ["enabled"],
    )

    bind = op.get_bind()
    accounts = bind.execute(sa.text("SELECT id, tenant_id FROM billing_accounts")).mappings()
    for account in accounts:
        bind.execute(
            sa.text(
                "INSERT INTO commercial_risk_policies "
                "(id, tenant_id, billing_account_id, policy_version, enabled, "
                "account_daily_unique_record_limit, partition_window_seconds, "
                "max_requests_per_window, "
                "max_partition_queries_per_window, max_cross_client_partition_queries_per_window, "
                "max_distinct_clients_per_window, created_at, updated_at) "
                "VALUES (:id, :tenant_id, :billing_account_id, 'risk-v1', true, "
                "20000, 900, 50000, 8, 4, 20, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": account["tenant_id"],
                "billing_account_id": account["id"],
            },
        )

    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "commercial_risk_policies" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "commercial_risk_policies" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "commercial_risk_policies" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "commercial_risk_policies"'))
        op.execute(sa.text('ALTER TABLE "commercial_risk_policies" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("commercial_risk_policies")
