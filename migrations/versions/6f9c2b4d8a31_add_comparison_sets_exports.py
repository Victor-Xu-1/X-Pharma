"""add comparison sets and governed workspace exports

Revision ID: 6f9c2b4d8a31
Revises: 5e8b1d3f7a24
Create Date: 2026-07-18 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6f9c2b4d8a31"
down_revision: str | Sequence[str] | None = "5e8b1d3f7a24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "comparison_sets",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("owner_user_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_comparison_set_version_positive"),
        sa.CheckConstraint("visibility IN ('private', 'tenant')", name="ck_comparison_set_visibility"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "owner_user_id", "name"),
    )
    op.create_table(
        "comparison_set_members",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("comparison_set_id", sa.String(36), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("added_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_comparison_set_member_position"),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["comparison_set_id"], ["comparison_sets.id"]),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "comparison_set_id", "entity_id"),
        sa.UniqueConstraint("tenant_id", "comparison_set_id", "position"),
    )
    op.create_table(
        "comparison_set_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("comparison_set_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("changed_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_comparison_set_history_version_positive"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["comparison_set_id"], ["comparison_sets.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "comparison_set_id", "version"),
    )
    op.create_table(
        "workspace_export_policies",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("allowed_formats", sa.JSON(), nullable=False),
        sa.Column("allowed_fields", sa.JSON(), nullable=False),
        sa.Column("max_records_per_export", sa.Integer(), nullable=False),
        sa.Column("attribution", sa.String(500), nullable=False),
        sa.Column("configured_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_records_per_export > 0", name="ck_workspace_export_policy_records_positive"),
        sa.CheckConstraint("max_records_per_export <= 100", name="ck_workspace_export_policy_records_bounded"),
        sa.ForeignKeyConstraint(["configured_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_table(
        "workspace_export_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("comparison_set_id", sa.String(36), nullable=False),
        sa.Column("comparison_set_version", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("export_format", sa.String(20), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("records_json", sa.JSON(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(100), nullable=False),
        sa.Column("policy_sha256", sa.String(64), nullable=False),
        sa.Column("attribution", sa.String(500), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("content_bytes", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("comparison_set_version > 0", name="ck_workspace_export_event_set_version_positive"),
        sa.CheckConstraint("record_count > 0", name="ck_workspace_export_event_records_positive"),
        sa.CheckConstraint("content_bytes > 0", name="ck_workspace_export_event_bytes_positive"),
        sa.CheckConstraint("export_format IN ('csv', 'json', 'xlsx')", name="ck_workspace_export_event_format"),
        sa.ForeignKeyConstraint(["comparison_set_id"], ["comparison_sets.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "requested_by_user_id", "idempotency_key"),
    )
    tables = {
        "comparison_sets": ("tenant_id", "owner_user_id", "visibility"),
        "comparison_set_members": ("tenant_id", "comparison_set_id", "entity_id", "added_by_user_id", "created_at"),
        "comparison_set_versions": ("tenant_id", "comparison_set_id", "changed_by_user_id", "created_at"),
        "workspace_export_policies": ("tenant_id", "enabled", "configured_by_user_id"),
        "workspace_export_events": ("tenant_id", "comparison_set_id", "requested_by_user_id", "generated_at"),
    }
    for table, columns in tables.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in tables:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_workspace_history_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'workspace history is append-only: %', TG_TABLE_NAME; "
                "END; $$"
            )
        )
        for trigger, table in (
            ("immutable_comparison_set_versions", "comparison_set_versions"),
            ("immutable_workspace_export_events", "workspace_export_events"),
        ):
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "{trigger}" BEFORE UPDATE OR DELETE ON "{table}" '
                    "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_workspace_history_mutation()"
                )
            )


def downgrade() -> None:
    tables = (
        "workspace_export_events",
        "workspace_export_policies",
        "comparison_set_versions",
        "comparison_set_members",
        "comparison_sets",
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER "immutable_workspace_export_events" ON "workspace_export_events"'))
        op.execute(sa.text('DROP TRIGGER "immutable_comparison_set_versions" ON "comparison_set_versions"'))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_workspace_history_mutation()"))
        for table in tables:
            op.execute(sa.text(f'DROP POLICY "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    for table in tables:
        op.drop_table(table)
