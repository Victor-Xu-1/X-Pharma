"""add tenant security boundary

Revision ID: 4c22f51cb18e
Revises: 2a7c951ef2b4
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c22f51cb18e"
down_revision: str | Sequence[str] | None = "2a7c951ef2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "activity_measurements",
    "assays",
    "audit_events",
    "clinical_trial_profiles",
    "compound_structures",
    "deal_profiles",
    "development_programs",
    "entities",
    "entity_aliases",
    "evidence_claims",
    "ingestion_assets",
    "patent_families",
    "relationships",
    "research_bundles",
    "source_documents",
    "target_profiles",
    "tenant_datasets",
)


def upgrade() -> None:
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(op.f("ix_api_keys_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(op.f("ix_api_keys_revoked_at"), ["revoked_at"], unique=False)

    op.create_table(
        "tenant_datasets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("ragflow_dataset_id", sa.String(length=64), nullable=False),
        sa.Column("license_policy", sa.JSON(), nullable=False),
        sa.Column("required_scopes", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "dataset_key"),
        sa.UniqueConstraint("tenant_id", "ragflow_dataset_id"),
    )
    op.create_index(op.f("ix_tenant_datasets_active"), "tenant_datasets", ["active"], unique=False)
    op.create_index(op.f("ix_tenant_datasets_dataset_key"), "tenant_datasets", ["dataset_key"], unique=False)
    op.create_index(
        op.f("ix_tenant_datasets_ragflow_dataset_id"),
        "tenant_datasets",
        ["ragflow_dataset_id"],
        unique=False,
    )
    op.create_index(op.f("ix_tenant_datasets_tenant_id"), "tenant_datasets", ["tenant_id"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=200), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("action", "actor_id", "actor_type", "outcome", "request_id", "resource_id", "resource_type", "tenant_id"):
        op.create_index(op.f(f"ix_audit_events_{column}"), "audit_events", [column], unique=False)
    op.create_index(op.f("ix_audit_events_occurred_at"), "audit_events", ["occurred_at"], unique=False)
    op.create_index("ix_audit_tenant_occurred", "audit_events", ["tenant_id", "occurred_at"], unique=False)

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')"
        for table in TENANT_TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f'CREATE POLICY "tenant_isolation" ON "{table}" '
                    f"USING ({predicate}) WITH CHECK ({predicate})"
                )
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in reversed(TENANT_TABLES):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))

    op.drop_index("ix_audit_tenant_occurred", table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_occurred_at"), table_name="audit_events")
    for column in reversed(("action", "actor_id", "actor_type", "outcome", "request_id", "resource_id", "resource_type", "tenant_id")):
        op.drop_index(op.f(f"ix_audit_events_{column}"), table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index(op.f("ix_tenant_datasets_tenant_id"), table_name="tenant_datasets")
    op.drop_index(op.f("ix_tenant_datasets_ragflow_dataset_id"), table_name="tenant_datasets")
    op.drop_index(op.f("ix_tenant_datasets_dataset_key"), table_name="tenant_datasets")
    op.drop_index(op.f("ix_tenant_datasets_active"), table_name="tenant_datasets")
    op.drop_table("tenant_datasets")

    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.drop_index(op.f("ix_api_keys_revoked_at"))
        batch_op.drop_index(op.f("ix_api_keys_expires_at"))
        batch_op.drop_column("revoked_at")
        batch_op.drop_column("expires_at")
