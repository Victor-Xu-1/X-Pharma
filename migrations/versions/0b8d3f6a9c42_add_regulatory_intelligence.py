"""add regulatory intelligence

Revision ID: 0b8d3f6a9c42
Revises: f27c4d9e1a65
Create Date: 2026-07-19 14:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0b8d3f6a9c42"
down_revision: str | Sequence[str] | None = "f27c4d9e1a65"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "regulatory_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("subject_entity_id", sa.String(length=36), nullable=False),
        sa.Column("agency", sa.String(length=80), nullable=False),
        sa.Column("jurisdiction", sa.String(length=120), nullable=False),
        sa.Column("event_identifier", sa.String(length=160), nullable=False),
        sa.Column("application_number", sa.String(length=120), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=120), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("decision_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indication_entity_id", sa.String(length=36), nullable=True),
        sa.Column("organization_entity_id", sa.String(length=36), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('submission', 'acceptance', 'priority_review', 'approval', "
            "'conditional_approval', 'designation', 'label_update', 'safety_signal', "
            "'safety_communication', 'rejection', "
            "'withdrawal', 'suspension', 'other')",
            name="ck_regulatory_event_type",
        ),
        sa.ForeignKeyConstraint(["indication_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["organization_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["subject_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "agency", "event_identifier"),
    )
    for column in (
        "tenant_id",
        "subject_entity_id",
        "agency",
        "jurisdiction",
        "event_identifier",
        "application_number",
        "event_type",
        "status",
        "decision_date",
        "indication_entity_id",
        "organization_entity_id",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_regulatory_events_{column}"), "regulatory_events", [column], unique=False)
    op.create_index(
        "ix_regulatory_subject_date",
        "regulatory_events",
        ["tenant_id", "subject_entity_id", "decision_date"],
        unique=False,
    )
    op.create_index(
        "ix_regulatory_application",
        "regulatory_events",
        ["tenant_id", "application_number"],
        unique=False,
    )
    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "regulatory_events" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "regulatory_events" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "regulatory_events" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "regulatory_events"'))
        op.execute(sa.text('ALTER TABLE "regulatory_events" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_regulatory_application", table_name="regulatory_events")
    op.drop_index("ix_regulatory_subject_date", table_name="regulatory_events")
    for column in reversed(
        (
            "tenant_id",
            "subject_entity_id",
            "agency",
            "jurisdiction",
            "event_identifier",
            "application_number",
            "event_type",
            "status",
            "decision_date",
            "indication_entity_id",
            "organization_entity_id",
            "source_document_id",
        )
    ):
        op.drop_index(op.f(f"ix_regulatory_events_{column}"), table_name="regulatory_events")
    op.drop_table("regulatory_events")
