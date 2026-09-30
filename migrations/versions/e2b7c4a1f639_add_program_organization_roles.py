"""add program organization roles

Revision ID: e2b7c4a1f639
Revises: d1a6b3f9e528
Create Date: 2026-07-27 09:10:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2b7c4a1f639"
down_revision: str | Sequence[str] | None = "d1a6b3f9e528"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES = "('originator','collaborator','licensee','licensor','manufacturer','other')"


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("development_programs") as batch:
        batch.add_column(sa.Column("organization_set_version", sa.Integer(), server_default="1", nullable=False))
        batch.create_check_constraint("ck_development_program_org_set_version", "organization_set_version > 0")
    op.create_table(
        "development_program_organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "program_id",
            sa.String(length=36),
            sa.ForeignKey("development_programs.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("organization_set_version", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "organization_entity_id",
            sa.String(length=36),
            sa.ForeignKey("entities.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(length=40), nullable=False, index=True),
        sa.Column("country_region", sa.String(length=120), nullable=True, index=True),
        sa.Column("organization_type", sa.String(length=120), nullable=True, index=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "source_document_id",
            sa.String(length=36),
            sa.ForeignKey("source_documents.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "program_id",
            "organization_set_version",
            "organization_entity_id",
            name="uq_program_org_entity",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "program_id",
            "organization_set_version",
            "position",
            name="uq_program_org_position",
        ),
        sa.CheckConstraint("organization_set_version > 0", name="ck_program_org_set_version"),
        sa.CheckConstraint("position >= 0 AND position < 20", name="ck_program_org_position"),
        sa.CheckConstraint(f"role IN {_ROLES}", name="ck_program_org_role"),
    )
    op.create_index(
        "ix_program_orgs_current_lookup",
        "development_program_organizations",
        ["tenant_id", "program_id", "organization_set_version", "position"],
    )
    op.create_index(
        "ix_program_orgs_entity_lookup",
        "development_program_organizations",
        ["tenant_id", "organization_entity_id", "program_id", "organization_set_version"],
    )
    # Deterministic backfill: the existing single organization column carries no role
    # semantics, so it is promoted as the originator at version 1 only where present.
    # No attributes are invented — country_region and organization_type stay NULL until
    # a governed source supplies them.
    op.execute(
        "INSERT INTO development_program_organizations "
        "(id, tenant_id, program_id, organization_set_version, organization_entity_id, role, "
        " country_region, organization_type, position, source_document_id, created_at, updated_at) "
        "SELECT lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || "
        "       substr(lower(hex(randomblob(2))),2) || '-a' || substr(lower(hex(randomblob(2))),2) || "
        "       '-' || lower(hex(randomblob(6))), "
        "       tenant_id, id, 1, organization_entity_id, 'originator', NULL, NULL, 0, source_document_id, "
        "       CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
        "FROM development_programs WHERE organization_entity_id IS NOT NULL"
        if bind.dialect.name == "sqlite"
        else "INSERT INTO development_program_organizations "
        "(id, tenant_id, program_id, organization_set_version, organization_entity_id, role, "
        " country_region, organization_type, position, source_document_id, created_at, updated_at) "
        "SELECT gen_random_uuid()::text, tenant_id, id, 1, organization_entity_id, 'originator', "
        "       NULL, NULL, 0, source_document_id, now(), now() "
        "FROM development_programs WHERE organization_entity_id IS NOT NULL"
    )
    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "development_program_organizations" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "development_program_organizations" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "development_program_organizations" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_program_organization_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'program organization history is append-only'; END; $$"
            )
        )
        op.execute(
            sa.text(
                "CREATE TRIGGER immutable_development_program_organizations "
                "BEFORE UPDATE OR DELETE ON development_program_organizations "
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_program_organization_mutation()"
            )
        )
    with op.batch_alter_table("development_programs") as batch:
        batch.alter_column("organization_set_version", existing_type=sa.Integer(), server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text("DROP TRIGGER immutable_development_program_organizations ON development_program_organizations")
        )
        op.execute(sa.text("DROP FUNCTION platform_private.reject_program_organization_mutation()"))
        op.execute(sa.text('DROP POLICY "tenant_isolation" ON "development_program_organizations"'))
        op.execute(sa.text('ALTER TABLE "development_program_organizations" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "development_program_organizations" DISABLE ROW LEVEL SECURITY'))
    with op.batch_alter_table("development_programs") as batch:
        batch.drop_constraint("ck_development_program_org_set_version", type_="check")
        batch.drop_column("organization_set_version")
    op.drop_index("ix_program_orgs_entity_lookup", table_name="development_program_organizations")
    op.drop_index("ix_program_orgs_current_lookup", table_name="development_program_organizations")
    op.drop_table("development_program_organizations")
