"""add agent extraction controls

Revision ID: 6b4a2f9d7e31
Revises: 1dd8b6ad33c4
Create Date: 2026-07-16 09:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b4a2f9d7e31"
down_revision: str | Sequence[str] | None = "1dd8b6ad33c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TENANT_TABLES = (
    "commercial_coverage_records",
    "commercial_policy_events",
)


def upgrade() -> None:
    with op.batch_alter_table("commercial_entitlements") as batch_op:
        batch_op.add_column(sa.Column("max_page_depth", sa.Integer(), server_default="10", nullable=False))
        batch_op.add_column(
            sa.Column("daily_unique_record_limit", sa.Integer(), server_default="5000", nullable=True)
        )
        batch_op.add_column(
            sa.Column("max_response_bytes", sa.Integer(), server_default="2000000", nullable=False)
        )
        batch_op.create_check_constraint("ck_entitlement_max_page_depth", "max_page_depth > 0")
        batch_op.create_check_constraint(
            "ck_entitlement_daily_unique_records",
            "daily_unique_record_limit IS NULL OR daily_unique_record_limit > 0",
        )
        batch_op.create_check_constraint("ck_entitlement_max_response_bytes", "max_response_bytes > 0")

    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.add_column(sa.Column("query_sha256", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("cursor_chain_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("page_offset", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("page_depth", sa.Integer(), server_default="1", nullable=False))
        batch_op.create_check_constraint("ck_usage_reservation_page_offset", "page_offset >= 0")
        batch_op.create_check_constraint("ck_usage_reservation_page_depth", "page_depth > 0")
    op.execute(
        sa.text(
            "UPDATE usage_reservations "
            "SET query_sha256 = request_sha256, cursor_chain_id = id "
            "WHERE query_sha256 IS NULL OR cursor_chain_id IS NULL"
        )
    )
    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.alter_column("query_sha256", existing_type=sa.String(length=64), nullable=False)
        batch_op.alter_column("cursor_chain_id", existing_type=sa.String(length=36), nullable=False)
    op.create_index("ix_usage_reservations_query_sha256", "usage_reservations", ["query_sha256"])
    op.create_index("ix_usage_reservations_cursor_chain_id", "usage_reservations", ["cursor_chain_id"])

    with op.batch_alter_table("usage_events") as batch_op:
        batch_op.add_column(
            sa.Column("unique_record_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("new_unique_record_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_check_constraint("ck_usage_event_unique_record_count", "unique_record_count >= 0")
        batch_op.create_check_constraint(
            "ck_usage_event_new_unique_record_count",
            "new_unique_record_count >= 0",
        )
        batch_op.create_check_constraint(
            "ck_usage_event_new_unique_within_total",
            "new_unique_record_count <= unique_record_count",
        )

    op.create_table(
        "commercial_coverage_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("agent_client_id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.String(length=500), nullable=False),
        sa.Column("entitlement_key", sa.String(length=160), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_type", sa.String(length=160), nullable=False),
        sa.Column("record_identifier_sha256", sa.String(length=64), nullable=False),
        sa.Column("first_usage_event_id", sa.String(length=36), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_coverage_actor_type"),
        sa.ForeignKeyConstraint(["agent_client_id"], ["agent_clients.id"]),
        sa.ForeignKeyConstraint(["first_usage_event_id"], ["usage_events.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["commercial_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "subscription_id",
            "agent_client_id",
            "entitlement_key",
            "period_start",
            "record_type",
            "record_identifier_sha256",
            name="uq_commercial_coverage_exact_record",
        ),
    )
    op.create_index(
        "ix_commercial_coverage_budget",
        "commercial_coverage_records",
        ["tenant_id", "subscription_id", "entitlement_key", "period_start"],
    )
    for column in (
        "agent_client_id",
        "entitlement_key",
        "first_usage_event_id",
        "period_start",
        "subject_id",
        "subscription_id",
        "tenant_id",
    ):
        op.create_index(f"ix_commercial_coverage_records_{column}", "commercial_coverage_records", [column])

    op.create_table(
        "commercial_policy_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("agent_client_id", sa.String(length=36), nullable=False),
        sa.Column("reservation_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.String(length=500), nullable=False),
        sa.Column("entitlement_key", sa.String(length=160), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=120), nullable=False),
        sa.Column("query_sha256", sa.String(length=64), nullable=False),
        sa.Column("cursor_chain_id", sa.String(length=36), nullable=False),
        sa.Column("page_depth", sa.Integer(), nullable=False),
        sa.Column("requested_records", sa.Integer(), nullable=False),
        sa.Column("existing_unique_records", sa.Integer(), nullable=False),
        sa.Column("projected_unique_records", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_policy_actor_type"),
        sa.CheckConstraint("phase IN ('reserve', 'settle')", name="ck_policy_phase"),
        sa.CheckConstraint("decision IN ('allow', 'deny')", name="ck_policy_decision"),
        sa.CheckConstraint("page_depth > 0", name="ck_policy_page_depth"),
        sa.CheckConstraint("requested_records >= 0", name="ck_policy_requested_records"),
        sa.CheckConstraint("existing_unique_records >= 0", name="ck_policy_existing_records"),
        sa.CheckConstraint("projected_unique_records >= 0", name="ck_policy_projected_records"),
        sa.CheckConstraint(
            "projected_unique_records >= existing_unique_records",
            name="ck_policy_projected_after_existing",
        ),
        sa.ForeignKeyConstraint(["agent_client_id"], ["agent_clients.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["usage_reservations.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["commercial_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_commercial_policy_scope",
        "commercial_policy_events",
        ["tenant_id", "subscription_id", "occurred_at"],
    )
    for column in (
        "agent_client_id",
        "decision",
        "entitlement_key",
        "occurred_at",
        "phase",
        "reason_code",
        "request_id",
        "reservation_id",
        "subject_id",
        "subscription_id",
        "tenant_id",
    ):
        op.create_index(f"ix_commercial_policy_events_{column}", "commercial_policy_events", [column])

    if op.get_bind().dialect.name == "postgresql":
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


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in reversed(NEW_TENANT_TABLES):
            op.execute(sa.text(f'DROP TRIGGER IF EXISTS "immutable_commercial_history" ON "{table}"'))
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))

    op.drop_table("commercial_policy_events")
    op.drop_table("commercial_coverage_records")

    with op.batch_alter_table("usage_events") as batch_op:
        batch_op.drop_constraint("ck_usage_event_new_unique_within_total", type_="check")
        batch_op.drop_constraint("ck_usage_event_new_unique_record_count", type_="check")
        batch_op.drop_constraint("ck_usage_event_unique_record_count", type_="check")
        batch_op.drop_column("new_unique_record_count")
        batch_op.drop_column("unique_record_count")

    op.drop_index("ix_usage_reservations_cursor_chain_id", table_name="usage_reservations")
    op.drop_index("ix_usage_reservations_query_sha256", table_name="usage_reservations")
    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.drop_constraint("ck_usage_reservation_page_depth", type_="check")
        batch_op.drop_constraint("ck_usage_reservation_page_offset", type_="check")
        batch_op.drop_column("page_depth")
        batch_op.drop_column("page_offset")
        batch_op.drop_column("cursor_chain_id")
        batch_op.drop_column("query_sha256")

    with op.batch_alter_table("commercial_entitlements") as batch_op:
        batch_op.drop_constraint("ck_entitlement_max_response_bytes", type_="check")
        batch_op.drop_constraint("ck_entitlement_daily_unique_records", type_="check")
        batch_op.drop_constraint("ck_entitlement_max_page_depth", type_="check")
        batch_op.drop_column("max_response_bytes")
        batch_op.drop_column("daily_unique_record_limit")
        batch_op.drop_column("max_page_depth")
