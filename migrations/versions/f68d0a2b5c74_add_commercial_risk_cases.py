"""add commercial risk case reviews

Revision ID: f68d0a2b5c74
Revises: e57c9f1a4b63
Create Date: 2026-07-16 17:45:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f68d0a2b5c74"
down_revision: str | Sequence[str] | None = "e57c9f1a4b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_risk_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("policy_event_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=False),
        sa.Column("reviewed_by", sa.String(length=500), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('acknowledged', 'resolved', 'dismissed')",
            name="ck_commercial_risk_case_status",
        ),
        sa.ForeignKeyConstraint(["policy_event_id"], ["commercial_policy_events.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "policy_event_id"),
    )
    for column in ("policy_event_id", "reviewed_at", "status", "tenant_id"):
        op.create_index(f"ix_commercial_risk_cases_{column}", "commercial_risk_cases", [column])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "commercial_risk_cases" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "commercial_risk_cases" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "commercial_risk_cases" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "commercial_risk_cases"'))
        op.execute(sa.text('ALTER TABLE "commercial_risk_cases" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("commercial_risk_cases")
