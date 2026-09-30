"""add governed trial roles and result disclosures

Revision ID: 0c9e2b4d6f18
Revises: f7b3d5a1c902
Create Date: 2026-07-24 00:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0c9e2b4d6f18"
down_revision: str | Sequence[str] | None = "f7b3d5a1c902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_VALUES = "'investigational_drug','combination_drug','investigational_target','combination_target'"
_DISCLOSURE_VALUES = (
    "'journal_article','conference_abstract','conference_presentation','registry_result',"
    "'press_release','poster','other'"
)
_EVALUATION_VALUES = "'unfavorable','not_superior','non_inferior','similar','positive','superior','terminated'"
_TABLES = ("clinical_trial_entity_roles", "clinical_trial_result_disclosures")


def upgrade() -> None:
    op.create_table(
        "clinical_trial_entity_roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("trial_id", sa.String(length=36), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"role IN ({_ROLE_VALUES})", name="ck_clinical_trial_entity_role"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["trial_id"], ["clinical_trial_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "trial_id", "entity_id", "role"),
    )
    for column in ("tenant_id", "trial_id", "entity_id", "role", "source_document_id"):
        op.create_index(op.f(f"ix_clinical_trial_entity_roles_{column}"), "clinical_trial_entity_roles", [column])
    op.create_index(
        "ix_clinical_trial_entity_roles_lookup",
        "clinical_trial_entity_roles",
        ["tenant_id", "role", "entity_id", "trial_id"],
    )

    op.create_table(
        "clinical_trial_result_disclosures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("trial_id", sa.String(length=36), nullable=False),
        sa.Column("disclosure_key", sa.String(length=240), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("disclosure_type", sa.String(length=40), nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("disclosed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conference_name", sa.String(length=500), nullable=True),
        sa.Column("is_key_result", sa.Boolean(), nullable=False),
        sa.Column("result_evaluation", sa.String(length=40), nullable=True),
        sa.Column("source_locator", sa.String(length=500), nullable=True),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_clinical_trial_disclosure_version"),
        sa.CheckConstraint(
            f"disclosure_type IN ({_DISCLOSURE_VALUES})",
            name="ck_clinical_trial_disclosure_type",
        ),
        sa.CheckConstraint(
            f"result_evaluation IS NULL OR result_evaluation IN ({_EVALUATION_VALUES})",
            name="ck_clinical_trial_disclosure_evaluation",
        ),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["trial_id"], ["clinical_trial_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "trial_id", "disclosure_key", "version"),
    )
    for column in (
        "tenant_id",
        "trial_id",
        "disclosure_key",
        "disclosure_type",
        "external_id",
        "disclosed_at",
        "conference_name",
        "is_key_result",
        "result_evaluation",
        "source_document_id",
    ):
        op.create_index(
            op.f(f"ix_clinical_trial_result_disclosures_{column}"),
            "clinical_trial_result_disclosures",
            [column],
        )
    op.create_index(
        "ix_clinical_trial_disclosures_trial_date",
        "clinical_trial_result_disclosures",
        ["tenant_id", "trial_id", "disclosed_at"],
    )
    op.create_index(
        "ix_clinical_trial_disclosures_external_id",
        "clinical_trial_result_disclosures",
        ["tenant_id", "external_id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in _TABLES:
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
        for table in reversed(_TABLES):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("clinical_trial_result_disclosures")
    op.drop_table("clinical_trial_entity_roles")
