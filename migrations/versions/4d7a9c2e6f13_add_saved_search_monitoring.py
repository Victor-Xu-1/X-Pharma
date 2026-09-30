"""add saved search monitoring

Revision ID: 4d7a9c2e6f13
Revises: 3c6f9a1d8b42
Create Date: 2026-07-18 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4d7a9c2e6f13"
down_revision: str | Sequence[str] | None = "3c6f9a1d8b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("query_type", sa.String(80), nullable=False),
        sa.Column("query_version", sa.Integer(), nullable=False),
        sa.Column("query_json", sa.JSON(), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("query_version > 0", name="ck_saved_search_query_version"),
        sa.CheckConstraint("visibility IN ('private', 'tenant')", name="ck_saved_search_visibility"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "owner_user_id", "name"),
    )
    op.create_index("ix_saved_searches_tenant_id", "saved_searches", ["tenant_id"])
    op.create_index("ix_saved_searches_owner_user_id", "saved_searches", ["owner_user_id"])
    op.create_index("ix_saved_searches_query_type", "saved_searches", ["query_type"])
    op.create_index("ix_saved_searches_visibility", "saved_searches", ["visibility"])

    op.create_table(
        "monitoring_topics",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("saved_search_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["saved_search_id"], ["saved_searches.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "owner_user_id", "name"),
    )
    for column in ("tenant_id", "owner_user_id", "saved_search_id", "active"):
        op.create_index(f"ix_monitoring_topics_{column}", "monitoring_topics", [column])

    op.create_table(
        "monitoring_alerts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("topic_id", sa.String(36), nullable=False),
        sa.Column("recipient_user_id", sa.String(36), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("source_outbox_event_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(160), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.String(2000), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_outbox_event_id"], ["outbox_events.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["monitoring_topics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "topic_id", "source_outbox_event_id"),
    )
    for column in (
        "tenant_id",
        "topic_id",
        "recipient_user_id",
        "entity_id",
        "source_outbox_event_id",
        "event_type",
        "occurred_at",
    ):
        op.create_index(f"ix_monitoring_alerts_{column}", "monitoring_alerts", [column])
    op.create_index(
        "ix_monitoring_alerts_inbox",
        "monitoring_alerts",
        ["tenant_id", "recipient_user_id", "occurred_at"],
    )

    op.create_table(
        "monitoring_alert_receipts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("alert_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["alert_id"], ["monitoring_alerts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "alert_id", "user_id"),
    )
    for column in ("tenant_id", "alert_id", "user_id", "read_at"):
        op.create_index(f"ix_monitoring_alert_receipts_{column}", "monitoring_alert_receipts", [column])

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in ("saved_searches", "monitoring_topics", "monitoring_alerts", "monitoring_alert_receipts"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_monitoring_alert_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'monitoring alerts are append-only: %', TG_TABLE_NAME; "
                "END; $$"
            )
        )
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_monitoring_alerts" '
                'BEFORE UPDATE OR DELETE ON "monitoring_alerts" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_monitoring_alert_mutation()"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER IF EXISTS "immutable_monitoring_alerts" ON "monitoring_alerts"'))
        op.execute(sa.text("DROP FUNCTION IF EXISTS platform_private.reject_monitoring_alert_mutation()"))
        for table in ("monitoring_alert_receipts", "monitoring_alerts", "monitoring_topics", "saved_searches"):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("monitoring_alert_receipts")
    op.drop_table("monitoring_alerts")
    op.drop_table("monitoring_topics")
    op.drop_table("saved_searches")
