"""expand governed deal intelligence

Revision ID: 2a5c8e1f4b76
Revises: 1f4a7c9e2d63
Create Date: 2026-07-24 02:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2a5c8e1f4b76"
down_revision: str | Sequence[str] | None = "1f4a7c9e2d63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEAL_STATUSES = "'announced','active','completed','terminated','withdrawn','superseded','unknown'"
_DEAL_DIRECTIONS = "'domestic','inbound','outbound','cross_border','global','undisclosed'"
_PARTY_ROLES = "'licensor','licensee','seller','buyer','acquirer','target','partner','investor','investee','other'"
_RIGHT_TYPES = (
    "'research','development','manufacturing','commercialization','co_development','co_promotion',"
    "'distribution','option','other'"
)
_DEVELOPMENT_PHASES = (
    "'discovery','preclinical','ind','phase_1','phase_1_2','phase_2','phase_2_3','phase_3',"
    "'filed','approved','discontinued'"
)
_RLS_TABLES = ("deal_party_associations", "deal_asset_associations", "deal_rights")


def upgrade() -> None:
    op.add_column(
        "deal_profiles",
        sa.Column("status", sa.String(length=40), server_default="unknown", nullable=False),
    )
    op.add_column(
        "deal_profiles",
        sa.Column("direction", sa.String(length=40), server_default="undisclosed", nullable=False),
    )
    op.add_column(
        "deal_profiles",
        sa.Column("direction_reference_jurisdiction", sa.String(length=120), nullable=True),
    )
    op.add_column("deal_profiles", sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deal_profiles", sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("deal_profiles") as batch_op:
        batch_op.create_check_constraint("ck_deal_profile_status", f"status IN ({_DEAL_STATUSES})")
        batch_op.create_check_constraint("ck_deal_profile_direction", f"direction IN ({_DEAL_DIRECTIONS})")
        batch_op.create_check_constraint(
            "ck_deal_direction_reference",
            "direction NOT IN ('inbound','outbound') OR direction_reference_jurisdiction IS NOT NULL",
        )
        batch_op.create_check_constraint(
            "ck_deal_termination_window",
            "terminated_at IS NULL OR announced_at IS NULL OR terminated_at >= announced_at",
        )
        for column in (
            "status",
            "direction",
            "direction_reference_jurisdiction",
            "terminated_at",
            "source_updated_at",
        ):
            batch_op.create_index(op.f(f"ix_deal_profiles_{column}"), [column])
        batch_op.create_index(
            "ix_deal_profiles_tenant_status_date",
            ["tenant_id", "status", "announced_at"],
        )
        batch_op.create_index(
            "ix_deal_profiles_tenant_direction",
            ["tenant_id", "direction"],
        )
        batch_op.alter_column("status", server_default=None)
        batch_op.alter_column("direction", server_default=None)

    op.create_table(
        "deal_party_associations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("deal_id", sa.String(length=36), nullable=False),
        sa.Column("party_entity_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("country_region", sa.String(length=120), nullable=True),
        sa.Column("organization_type", sa.String(length=120), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"role IN ({_PARTY_ROLES})", name="ck_deal_party_role"),
        sa.ForeignKeyConstraint(["deal_id"], ["deal_profiles.id"]),
        sa.ForeignKeyConstraint(["party_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "deal_id", "party_entity_id", "role"),
    )
    for column in (
        "tenant_id",
        "deal_id",
        "party_entity_id",
        "role",
        "country_region",
        "organization_type",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_deal_party_associations_{column}"), "deal_party_associations", [column])
    op.create_index(
        "ix_deal_party_role_lookup",
        "deal_party_associations",
        ["tenant_id", "role", "party_entity_id", "deal_id"],
    )

    op.create_table(
        "deal_asset_associations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("deal_id", sa.String(length=36), nullable=False),
        sa.Column("asset_entity_id", sa.String(length=36), nullable=False),
        sa.Column("development_phase_at_transaction", sa.String(length=40), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"development_phase_at_transaction IS NULL OR development_phase_at_transaction IN ({_DEVELOPMENT_PHASES})",
            name="ck_deal_asset_transaction_phase",
        ),
        sa.ForeignKeyConstraint(["asset_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["deal_id"], ["deal_profiles.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "deal_id", "asset_entity_id"),
    )
    for column in (
        "tenant_id",
        "deal_id",
        "asset_entity_id",
        "development_phase_at_transaction",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_deal_asset_associations_{column}"), "deal_asset_associations", [column])
    op.create_index(
        "ix_deal_asset_phase_lookup",
        "deal_asset_associations",
        ["tenant_id", "development_phase_at_transaction", "asset_entity_id", "deal_id"],
    )

    op.create_table(
        "deal_rights",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("deal_id", sa.String(length=36), nullable=False),
        sa.Column("holder_entity_id", sa.String(length=36), nullable=False),
        sa.Column("right_type", sa.String(length=40), nullable=False),
        sa.Column("territory", sa.String(length=240), nullable=False),
        sa.Column("exclusive", sa.Boolean(), nullable=True),
        sa.Column("scope_description", sa.Text(), nullable=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(f"right_type IN ({_RIGHT_TYPES})", name="ck_deal_right_type"),
        sa.ForeignKeyConstraint(["deal_id"], ["deal_profiles.id"]),
        sa.ForeignKeyConstraint(["holder_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "deal_id", "holder_entity_id", "right_type", "territory"),
    )
    for column in (
        "tenant_id",
        "deal_id",
        "holder_entity_id",
        "right_type",
        "territory",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_deal_rights_{column}"), "deal_rights", [column])
    op.create_index(
        "ix_deal_right_lookup",
        "deal_rights",
        ["tenant_id", "right_type", "territory", "deal_id"],
    )

    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in _RLS_TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in reversed(_RLS_TABLES):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    for table in reversed(_RLS_TABLES):
        op.drop_table(table)

    with op.batch_alter_table("deal_profiles") as batch_op:
        batch_op.drop_index("ix_deal_profiles_tenant_direction")
        batch_op.drop_index("ix_deal_profiles_tenant_status_date")
        for column in reversed(
            ("status", "direction", "direction_reference_jurisdiction", "terminated_at", "source_updated_at")
        ):
            batch_op.drop_index(op.f(f"ix_deal_profiles_{column}"))
        batch_op.drop_constraint("ck_deal_termination_window", type_="check")
        batch_op.drop_constraint("ck_deal_direction_reference", type_="check")
        batch_op.drop_constraint("ck_deal_profile_direction", type_="check")
        batch_op.drop_constraint("ck_deal_profile_status", type_="check")
        batch_op.drop_column("source_updated_at")
        batch_op.drop_column("terminated_at")
        batch_op.drop_column("direction_reference_jurisdiction")
        batch_op.drop_column("direction")
        batch_op.drop_column("status")
