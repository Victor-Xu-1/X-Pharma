"""add saved search version history

Revision ID: 5e8b1d3f7a24
Revises: 4d7a9c2e6f13
Create Date: 2026-07-18 21:45:00
"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "5e8b1d3f7a24"
down_revision: str | Sequence[str] | None = "4d7a9c2e6f13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_search_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("saved_search_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("query_type", sa.String(80), nullable=False),
        sa.Column("query_json", sa.JSON(), nullable=False),
        sa.Column("changed_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_saved_search_version_positive"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["saved_search_id"], ["saved_searches.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "saved_search_id", "version"),
    )
    for column in ("tenant_id", "saved_search_id", "changed_by_user_id", "created_at"):
        op.create_index(f"ix_saved_search_versions_{column}", "saved_search_versions", [column])
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, tenant_id, query_version, query_type, query_json, owner_user_id, updated_at "
            "FROM saved_searches"
        )
    ).mappings()
    insert = sa.text(
        "INSERT INTO saved_search_versions "
        "(id, tenant_id, saved_search_id, version, query_type, query_json, changed_by_user_id, created_at) "
        "VALUES (:id, :tenant_id, :saved_search_id, :version, :query_type, :query_json, :changed_by_user_id, :created_at)"
    ).bindparams(sa.bindparam("query_json", type_=sa.JSON()))
    for row in rows:
        connection.execute(
            insert,
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"pharma:saved-search:{row['id']}:{row['query_version']}")),
                "tenant_id": row["tenant_id"],
                "saved_search_id": row["id"],
                "version": row["query_version"],
                "query_type": row["query_type"],
                "query_json": row["query_json"],
                "changed_by_user_id": row["owner_user_id"],
                "created_at": row["updated_at"],
            },
        )

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "saved_search_versions" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "saved_search_versions" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "saved_search_versions" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )
        op.execute(sa.text('DROP TRIGGER "immutable_monitoring_alerts" ON "monitoring_alerts"'))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_monitoring_alert_mutation()"))
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_monitoring_history_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'monitoring history is append-only: %', TG_TABLE_NAME; "
                "END; $$"
            )
        )
        for trigger, table in (
            ("immutable_monitoring_alerts", "monitoring_alerts"),
            ("immutable_saved_search_versions", "saved_search_versions"),
        ):
            op.execute(
                sa.text(
                    f'CREATE TRIGGER "{trigger}" BEFORE UPDATE OR DELETE ON "{table}" '
                    "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_monitoring_history_mutation()"
                )
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER "immutable_saved_search_versions" ON "saved_search_versions"'))
        op.execute(sa.text('DROP TRIGGER "immutable_monitoring_alerts" ON "monitoring_alerts"'))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_monitoring_history_mutation()"))
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
        op.execute(sa.text('DROP POLICY "tenant_isolation" ON "saved_search_versions"'))
        op.execute(sa.text('ALTER TABLE "saved_search_versions" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("saved_search_versions")
