"""add RDKit structure authority

Revision ID: a13b7c4d9e02
Revises: f52a6d7e8c31
Create Date: 2026-07-16 09:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a13b7c4d9e02"
down_revision: str | Sequence[str] | None = "f52a6d7e8c31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FINGERPRINT_VERSION = "morganbv-radius2-2048/rdkit-2026.03.3"
LEGACY_STANDARDIZATION_VERSION = "legacy-source/v1"


class RDKitMol(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "mol"


class RDKitBitFingerprint(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "bfp"


def upgrade() -> None:
    op.add_column(
        "compound_structures",
        sa.Column(
            "standardization_version",
            sa.String(length=100),
            server_default=LEGACY_STANDARDIZATION_VERSION,
            nullable=False,
        ),
    )
    op.add_column(
        "compound_structures",
        sa.Column(
            "fingerprint_version",
            sa.String(length=100),
            server_default=FINGERPRINT_VERSION,
            nullable=False,
        ),
    )

    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS rdkit"))
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    op.add_column("compound_structures", sa.Column("rdkit_mol", RDKitMol(), nullable=True))
    op.add_column("compound_structures", sa.Column("morgan_bfp", RDKitBitFingerprint(), nullable=True))
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION platform_private.materialize_compound_structure()
            RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = pg_catalog, public
            AS $$
            DECLARE
                parsed_mol public.mol;
            BEGIN
                IF NEW.canonical_smiles IS NULL OR btrim(NEW.canonical_smiles) = '' THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '22023',
                        MESSAGE = 'canonical_smiles must contain a valid chemical structure';
                END IF;
                IF NOT public.is_valid_smiles(NEW.canonical_smiles::cstring) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '22023',
                        MESSAGE = 'canonical_smiles is not valid SMILES';
                END IF;
                parsed_mol := public.mol_from_smiles(NEW.canonical_smiles);
                IF parsed_mol IS NULL THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '22023',
                        MESSAGE = 'canonical_smiles could not be materialized by RDKit';
                END IF;
                NEW.rdkit_mol := parsed_mol;
                NEW.morgan_bfp := public.morganbv_fp(parsed_mol, 2);
                NEW.fingerprint_version := '{FINGERPRINT_VERSION}';
                IF NEW.standardization_version IS NULL OR btrim(NEW.standardization_version) = '' THEN
                    NEW.standardization_version := '{LEGACY_STANDARDIZATION_VERSION}';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER materialize_compound_structure "
            "BEFORE INSERT OR UPDATE ON compound_structures "
            "FOR EACH ROW EXECUTE FUNCTION platform_private.materialize_compound_structure()"
        )
    )
    op.execute(sa.text("UPDATE compound_structures SET canonical_smiles = canonical_smiles"))
    op.execute(
        sa.text(
            "ALTER TABLE compound_structures ADD CONSTRAINT ck_compound_structures_rdkit_mol_materialized "
            "CHECK (rdkit_mol IS NOT NULL) NOT VALID"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE compound_structures ADD CONSTRAINT ck_compound_structures_morgan_bfp_materialized "
            "CHECK (morgan_bfp IS NOT NULL) NOT VALID"
        )
    )
    op.execute(
        sa.text("ALTER TABLE compound_structures VALIDATE CONSTRAINT ck_compound_structures_rdkit_mol_materialized")
    )
    op.execute(
        sa.text("ALTER TABLE compound_structures VALIDATE CONSTRAINT ck_compound_structures_morgan_bfp_materialized")
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_compound_structures_rdkit_mol_gist "
            "ON compound_structures USING gist (tenant_id, rdkit_mol)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_compound_structures_morgan_bfp_gist "
            "ON compound_structures USING gist (tenant_id, morgan_bfp)"
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                rls_enabled boolean;
                rls_forced boolean;
                policy_present boolean;
            BEGIN
                SELECT relrowsecurity, relforcerowsecurity
                INTO rls_enabled, rls_forced
                FROM pg_class
                WHERE oid = 'public.compound_structures'::regclass;
                SELECT EXISTS (
                    SELECT 1 FROM pg_policy
                    WHERE polrelid = 'public.compound_structures'::regclass
                      AND polname = 'tenant_isolation'
                ) INTO policy_present;
                IF NOT rls_enabled OR NOT rls_forced OR NOT policy_present THEN
                    RAISE EXCEPTION 'compound_structures must retain forced tenant RLS';
                END IF;
            END;
            $$
            """
        )
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS ix_compound_structures_morgan_bfp_gist"))
        op.execute(sa.text("DROP INDEX IF EXISTS ix_compound_structures_rdkit_mol_gist"))
        op.execute(
            sa.text(
                "ALTER TABLE compound_structures "
                "DROP CONSTRAINT IF EXISTS ck_compound_structures_morgan_bfp_materialized"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE compound_structures "
                "DROP CONSTRAINT IF EXISTS ck_compound_structures_rdkit_mol_materialized"
            )
        )
        op.execute(sa.text("DROP TRIGGER IF EXISTS materialize_compound_structure ON compound_structures"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS platform_private.materialize_compound_structure()"))
        op.drop_column("compound_structures", "morgan_bfp")
        op.drop_column("compound_structures", "rdkit_mol")

    op.drop_column("compound_structures", "fingerprint_version")
    op.drop_column("compound_structures", "standardization_version")
