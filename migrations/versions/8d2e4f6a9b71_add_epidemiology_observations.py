"""add epidemiology observations

Revision ID: 8d2e4f6a9b71
Revises: 7c1a9e4b2d60
Create Date: 2026-07-22 22:20:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d2e4f6a9b71"
down_revision: str | Sequence[str] | None = "7c1a9e4b2d60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "epidemiology_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("observation_identifier", sa.String(length=200), nullable=False),
        sa.Column("disease_entity_id", sa.String(length=36), nullable=False),
        sa.Column("measure", sa.String(length=40), nullable=False),
        sa.Column("value", sa.Numeric(precision=24, scale=6), nullable=False),
        sa.Column("lower_bound", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("upper_bound", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("unit", sa.String(length=120), nullable=False),
        sa.Column("geography", sa.String(length=160), nullable=False),
        sa.Column("population_scope", sa.String(length=500), nullable=False),
        sa.Column("age_group", sa.String(length=120), nullable=True),
        sa.Column("sex", sa.String(length=80), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sample_size", sa.Numeric(precision=24, scale=0), nullable=True),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("publisher_entity_id", sa.String(length=36), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "measure IN ('prevalence', 'incidence', 'mortality', 'patient_count', "
            "'diagnosed_count', 'treated_count', 'survival_rate', 'daly', 'other')",
            name="ck_epidemiology_measure",
        ),
        sa.CheckConstraint("value >= 0", name="ck_epidemiology_value_nonnegative"),
        sa.CheckConstraint(
            "lower_bound IS NULL OR lower_bound >= 0",
            name="ck_epidemiology_lower_bound_nonnegative",
        ),
        sa.CheckConstraint(
            "lower_bound IS NULL OR lower_bound <= value",
            name="ck_epidemiology_lower_bound_order",
        ),
        sa.CheckConstraint(
            "upper_bound IS NULL OR upper_bound >= value",
            name="ck_epidemiology_upper_bound_order",
        ),
        sa.CheckConstraint(
            "period_end IS NULL OR period_start IS NULL OR period_end >= period_start",
            name="ck_epidemiology_period_order",
        ),
        sa.CheckConstraint(
            "sample_size IS NULL OR sample_size > 0",
            name="ck_epidemiology_sample_size_positive",
        ),
        sa.ForeignKeyConstraint(["disease_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["publisher_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "observation_identifier"),
    )
    for column in (
        "tenant_id",
        "observation_identifier",
        "disease_entity_id",
        "measure",
        "unit",
        "geography",
        "age_group",
        "sex",
        "period_start",
        "period_end",
        "publisher_entity_id",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_epidemiology_observations_{column}"), "epidemiology_observations", [column])
    op.create_index(
        "ix_epidemiology_disease_period",
        "epidemiology_observations",
        ["tenant_id", "disease_entity_id", "period_end"],
    )
    op.create_index(
        "ix_epidemiology_geography_measure",
        "epidemiology_observations",
        ["tenant_id", "geography", "measure"],
    )
    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "epidemiology_observations" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "epidemiology_observations" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "epidemiology_observations" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "epidemiology_observations"'))
        op.execute(sa.text('ALTER TABLE "epidemiology_observations" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_epidemiology_geography_measure", table_name="epidemiology_observations")
    op.drop_index("ix_epidemiology_disease_period", table_name="epidemiology_observations")
    for column in reversed(
        (
            "tenant_id",
            "observation_identifier",
            "disease_entity_id",
            "measure",
            "unit",
            "geography",
            "age_group",
            "sex",
            "period_start",
            "period_end",
            "publisher_entity_id",
            "source_document_id",
        )
    ):
        op.drop_index(op.f(f"ix_epidemiology_observations_{column}"), table_name="epidemiology_observations")
    op.drop_table("epidemiology_observations")
