"""add governed data lifecycle controls

Revision ID: a72d9e4b6c10
Revises: 91c4e7a2d5b8
Create Date: 2026-07-19 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a72d9e4b6c10"
down_revision: str | Sequence[str] | None = "91c4e7a2d5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_retention_policies",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("data_class", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("retention_seconds", sa.Integer(), nullable=False),
        sa.Column("legal_basis", sa.String(500), nullable=False),
        sa.Column("geographic_scope", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("configured_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("retention_seconds >= 300", name="ck_retention_policy_minimum"),
        sa.CheckConstraint(
            "data_class IN ('commercial_export_artifact')",
            name="ck_retention_policy_data_class",
        ),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "data_class"),
    )
    for column in ("tenant_id", "data_class", "active"):
        op.create_index(f"ix_data_retention_policies_{column}", "data_retention_policies", [column])

    op.create_table(
        "legal_holds",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_id", sa.String(36), nullable=True),
        sa.Column("matter_reference", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("placed_by_user_id", sa.String(36), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_by_user_id", sa.String(36), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(2000), nullable=True),
        sa.CheckConstraint(
            "scope_type IN ('tenant', 'billing_account', 'data_export_job')",
            name="ck_legal_hold_scope_type",
        ),
        sa.CheckConstraint("status IN ('active', 'released')", name="ck_legal_hold_status"),
        sa.CheckConstraint(
            "(scope_type = 'tenant' AND scope_id IS NULL) OR "
            "(scope_type <> 'tenant' AND scope_id IS NOT NULL)",
            name="ck_legal_hold_scope_id",
        ),
        sa.ForeignKeyConstraint(["placed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "scope_type", "scope_id", "matter_reference", "status"):
        op.create_index(f"ix_legal_holds_{column}", "legal_holds", [column])
    op.create_index(
        "ix_legal_holds_active_scope",
        "legal_holds",
        ["tenant_id", "status", "scope_type", "scope_id"],
    )

    op.create_table(
        "data_lifecycle_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("data_class", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(80), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(36), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("legal_hold_ids", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('purge', 'blocked')", name="ck_data_lifecycle_event_action"),
        sa.CheckConstraint("outcome IN ('succeeded', 'blocked')", name="ck_data_lifecycle_event_outcome"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["data_retention_policies.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key"),
    )
    for column in ("tenant_id", "data_class", "target_id", "action", "outcome", "created_at"):
        op.create_index(f"ix_data_lifecycle_events_{column}", "data_lifecycle_events", [column])
    op.create_index(
        "ix_data_lifecycle_target",
        "data_lifecycle_events",
        ["tenant_id", "target_type", "target_id", "created_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in ("data_retention_policies", "legal_holds", "data_lifecycle_events"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_lifecycle_event_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'data lifecycle events are append-only'; END; $$"
            )
        )
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_data_lifecycle_events" '
                'BEFORE UPDATE OR DELETE ON "data_lifecycle_events" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_lifecycle_event_mutation()"
            )
        )


def downgrade() -> None:
    tables = ("data_lifecycle_events", "legal_holds", "data_retention_policies")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER "immutable_data_lifecycle_events" ON "data_lifecycle_events"'))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_lifecycle_event_mutation()"))
        for table in tables:
            op.execute(sa.text(f'DROP POLICY "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    for table in tables:
        op.drop_table(table)
