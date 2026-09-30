"""add projection delivery state

Revision ID: f52a6d7e8c31
Revises: e41f7c8a9b20
Create Date: 2026-07-16 03:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f52a6d7e8c31"
down_revision: str | Sequence[str] | None = "e41f7c8a9b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DELIVERY_STATE = sa.Enum(
    "PROCESSING",
    "RETRY",
    "SUCCEEDED",
    "DEAD",
    name="projectiondeliverystate",
)


def upgrade() -> None:
    op.create_table(
        "projection_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("consumer_name", sa.String(length=120), nullable=False),
        sa.Column("outbox_event_id", sa.String(length=36), nullable=False),
        sa.Column("state", DELIVERY_STATE, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts > 0", name="ck_projection_delivery_attempts"),
        sa.ForeignKeyConstraint(["outbox_event_id"], ["outbox_events.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("consumer_name", "outbox_event_id"),
    )
    op.create_index(
        "ix_projection_delivery_due",
        "projection_deliveries",
        ["consumer_name", "state", "available_at"],
        unique=False,
    )
    for column in (
        "available_at",
        "consumer_name",
        "lease_expires_at",
        "outbox_event_id",
        "processed_at",
        "state",
        "tenant_id",
        "worker_id",
    ):
        op.create_index(op.f(f"ix_projection_deliveries_{column}"), "projection_deliveries", [column], unique=False)

    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "projection_deliveries" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "projection_deliveries" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "projection_deliveries" '
                "USING (tenant_id = public.app_current_tenant_id()) "
                "WITH CHECK (tenant_id = public.app_current_tenant_id())"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "projection_deliveries"'))
        op.execute(sa.text('ALTER TABLE "projection_deliveries" DISABLE ROW LEVEL SECURITY'))

    for column in reversed(
        (
            "available_at",
            "consumer_name",
            "lease_expires_at",
            "outbox_event_id",
            "processed_at",
            "state",
            "tenant_id",
            "worker_id",
        )
    ):
        op.drop_index(op.f(f"ix_projection_deliveries_{column}"), table_name="projection_deliveries")
    op.drop_index("ix_projection_delivery_due", table_name="projection_deliveries")
    op.drop_table("projection_deliveries")
    if op.get_bind().dialect.name == "postgresql":
        DELIVERY_STATE.drop(op.get_bind(), checkfirst=True)
