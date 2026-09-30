"""add target evidence observations

Revision ID: d9f7b1c5e234
Revises: c8e6a0b4d123
Create Date: 2026-07-23 18:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9f7b1c5e234"
down_revision: str | Sequence[str] | None = "c8e6a0b4d123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "target_evidence_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("source_system", sa.String(length=80), nullable=False),
        sa.Column("source_record_id", sa.String(length=240), nullable=False),
        sa.Column("target_entity_id", sa.String(length=36), nullable=False),
        sa.Column("disease_entity_id", sa.String(length=36), nullable=True),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("direction", sa.String(length=40), nullable=False),
        sa.Column("study_name", sa.String(length=500), nullable=True),
        sa.Column("population", sa.String(length=500), nullable=True),
        sa.Column("tissue", sa.String(length=240), nullable=True),
        sa.Column("variant", sa.String(length=240), nullable=True),
        sa.Column("effect_size", sa.Float(), nullable=True),
        sa.Column("effect_unit", sa.String(length=80), nullable=True),
        sa.Column("p_value", sa.Float(), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qualifiers", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "evidence_type IN ('genetic_association', 'expression', 'functional', 'translational', "
            "'biomarker', 'safety')",
            name="ck_target_evidence_type",
        ),
        sa.CheckConstraint(
            "direction IN ('supports', 'opposes', 'neutral', 'unknown')",
            name="ck_target_evidence_direction",
        ),
        sa.CheckConstraint("p_value IS NULL OR (p_value >= 0 AND p_value <= 1)", name="ck_target_evidence_p_value"),
        sa.CheckConstraint("sample_size IS NULL OR sample_size > 0", name="ck_target_evidence_sample_size"),
        sa.ForeignKeyConstraint(["disease_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["target_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_system", "source_record_id"),
    )
    for column in (
        "tenant_id",
        "source_system",
        "source_record_id",
        "target_entity_id",
        "disease_entity_id",
        "evidence_type",
        "direction",
        "tissue",
        "variant",
        "observed_at",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_target_evidence_observations_{column}"), "target_evidence_observations", [column])
    op.create_index(
        "ix_target_evidence_target_type",
        "target_evidence_observations",
        ["tenant_id", "target_entity_id", "evidence_type"],
    )
    op.create_index(
        "ix_target_evidence_disease_type",
        "target_evidence_observations",
        ["tenant_id", "disease_entity_id", "evidence_type"],
    )
    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "target_evidence_observations" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "target_evidence_observations" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "target_evidence_observations" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "target_evidence_observations"'))
        op.execute(sa.text('ALTER TABLE "target_evidence_observations" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_target_evidence_disease_type", table_name="target_evidence_observations")
    op.drop_index("ix_target_evidence_target_type", table_name="target_evidence_observations")
    for column in reversed(
        (
            "tenant_id",
            "source_system",
            "source_record_id",
            "target_entity_id",
            "disease_entity_id",
            "evidence_type",
            "direction",
            "tissue",
            "variant",
            "observed_at",
            "source_document_id",
        )
    ):
        op.drop_index(op.f(f"ix_target_evidence_observations_{column}"), table_name="target_evidence_observations")
    op.drop_table("target_evidence_observations")
