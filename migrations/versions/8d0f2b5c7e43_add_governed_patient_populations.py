"""add governed patient populations

Revision ID: 8d0f2b5c7e43
Revises: 7c9e1a4b6d32
Create Date: 2026-07-24 14:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8d0f2b5c7e43"
down_revision: str | Sequence[str] | None = "7c9e1a4b6d32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEW_STATUSES = ("DRAFT", "VERIFIED", "REJECTED", "SUPERSEDED")


def _review_status_enum() -> sa.Enum:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.ENUM(*REVIEW_STATUSES, name="reviewstatus", create_type=False)
    return sa.Enum(*REVIEW_STATUSES, name="reviewstatus")


def upgrade() -> None:
    op.create_table(
        "patient_populations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("population_key", sa.String(200), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column("review_status", _review_status_enum(), nullable=False),
        sa.Column("source_document_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "population_key"),
    )
    op.create_index("ix_patient_populations_tenant_id", "patient_populations", ["tenant_id"])
    op.create_index("ix_patient_populations_source_document_id", "patient_populations", ["source_document_id"])
    op.create_index("ix_patient_populations_review_status", "patient_populations", ["review_status"])
    op.create_index("ix_patient_populations_tenant_name", "patient_populations", ["tenant_id", "name"])
    op.create_table(
        "patient_population_entity_links",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("patient_population_id", sa.String(36), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("relationship", sa.String(20), nullable=False),
        sa.Column("source_document_id", sa.String(36), nullable=True),
        sa.CheckConstraint(
            "relationship IN ('disease', 'target')",
            name="ck_patient_population_entity_relationship",
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["patient_population_id"], ["patient_populations.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "patient_population_id", "entity_id", "relationship"),
    )
    for column in ("tenant_id", "patient_population_id", "entity_id", "relationship", "source_document_id"):
        op.create_index(
            f"ix_patient_population_entity_links_{column}",
            "patient_population_entity_links",
            [column],
        )
    with op.batch_alter_table("epidemiology_observations") as batch_op:
        batch_op.add_column(sa.Column("patient_population_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key(
            "fk_epidemiology_observations_patient_population_id",
            "patient_populations",
            ["patient_population_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_epidemiology_observations_patient_population_id",
            ["patient_population_id"],
        )

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in ("patient_populations", "patient_population_entity_links"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(
                    f'CREATE POLICY "tenant_isolation" ON "{table}" '
                    f"USING ({predicate}) WITH CHECK ({predicate})"
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("epidemiology_observations") as batch_op:
        batch_op.drop_index("ix_epidemiology_observations_patient_population_id")
        batch_op.drop_constraint(
            "fk_epidemiology_observations_patient_population_id",
            type_="foreignkey",
        )
        batch_op.drop_column("patient_population_id")
    op.drop_table("patient_population_entity_links")
    op.drop_table("patient_populations")
