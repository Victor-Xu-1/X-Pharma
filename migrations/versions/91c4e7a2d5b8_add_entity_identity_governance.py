"""add governed entity identity and ontology registry

Revision ID: 91c4e7a2d5b8
Revises: 6f9c2b4d8a31
Create Date: 2026-07-18 23:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "91c4e7a2d5b8"
down_revision: str | Sequence[str] | None = "6f9c2b4d8a31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENTITY_TYPES = (
    "DRUG",
    "TARGET",
    "DISEASE",
    "ORGANIZATION",
    "CLINICAL_TRIAL",
    "PATENT",
    "TRANSACTION",
    "PRODUCT",
    "TECHNOLOGY",
    "PERSON",
)
REVIEW_STATUSES = ("DRAFT", "VERIFIED", "REJECTED", "SUPERSEDED")
RESOLUTION_STATUSES = ("PENDING", "APPROVED", "REJECTED", "REVERTED")


def _enum(name: str, values: tuple[str, ...]) -> sa.Enum:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.ENUM(*values, name=name, create_type=False)
    return sa.Enum(*values, name=name)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text("ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_tenant_id_entity_type_normalized_name_key")
        )
    else:
        naming_convention = {"uq": "uq_%(table_name)s_%(column_0_N_name)s"}
        with op.batch_alter_table("entities", naming_convention=naming_convention) as batch_op:
            batch_op.drop_constraint(
                "uq_entities_tenant_id_entity_type_normalized_name",
                type_="unique",
            )
    op.create_index(
        "ix_entities_tenant_type_normalized_name",
        "entities",
        ["tenant_id", "entity_type", "normalized_name"],
        unique=False,
    )
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(*RESOLUTION_STATUSES, name="resolutionstatus").create(bind, checkfirst=True)
    entity_type = _enum("entitytype", ENTITY_TYPES)
    review_status = _enum("reviewstatus", REVIEW_STATUSES)
    resolution_status = _enum("resolutionstatus", RESOLUTION_STATUSES)

    op.create_table(
        "entity_identifiers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("entity_type", entity_type, nullable=False),
        sa.Column("namespace", sa.String(80), nullable=False),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("normalized_value", sa.String(500), nullable=False),
        sa.Column("trusted_namespace", sa.Boolean(), nullable=False),
        sa.Column("source_document_id", sa.String(36), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("review_status", review_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "entity_id", "namespace", "normalized_value"),
    )
    op.create_index(
        "ix_entity_identifiers_lookup",
        "entity_identifiers",
        ["tenant_id", "entity_type", "namespace", "normalized_value"],
    )
    for column in ("tenant_id", "entity_id", "entity_type", "source_document_id", "review_status"):
        op.create_index(f"ix_entity_identifiers_{column}", "entity_identifiers", [column])
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                INSERT INTO entity_identifiers
                    (id, tenant_id, entity_id, entity_type, namespace, value, normalized_value,
                     trusted_namespace, source_document_id, provenance, review_status, created_at, updated_at)
                SELECT
                    substr(md5(e.id || ':' || x.key || ':' || x.value), 1, 8) || '-' ||
                    substr(md5(e.id || ':' || x.key || ':' || x.value), 9, 4) || '-' ||
                    substr(md5(e.id || ':' || x.key || ':' || x.value), 13, 4) || '-' ||
                    substr(md5(e.id || ':' || x.key || ':' || x.value), 17, 4) || '-' ||
                    substr(md5(e.id || ':' || x.key || ':' || x.value), 21, 12),
                    e.tenant_id, e.id, e.entity_type,
                    CASE lower(replace(x.key, '-', '_'))
                        WHEN 'hgnc_id' THEN 'hgnc' WHEN 'uniprotkb' THEN 'uniprot'
                        WHEN 'uniprot_id' THEN 'uniprot' WHEN 'ensembl_id' THEN 'ensembl'
                        WHEN 'chembl_id' THEN 'chembl' WHEN 'drugbank_id' THEN 'drugbank'
                        WHEN 'pubchem' THEN 'pubchem_cid' WHEN 'cid' THEN 'pubchem_cid'
                        WHEN 'nct' THEN 'clinicaltrials' WHEN 'nct_id' THEN 'clinicaltrials'
                        WHEN 'efo_id' THEN 'efo' WHEN 'mesh_id' THEN 'mesh'
                        WHEN 'publication_number' THEN 'patent'
                        ELSE lower(replace(x.key, '-', '_'))
                    END,
                    x.value,
                    CASE
                        WHEN lower(x.key) = 'doi' THEN lower(
                            regexp_replace(
                                x.value,
                                '^(https?://(dx\\.)?doi\\.org/|doi:[[:space:]]*)',
                                '',
                                'i'
                            )
                        )
                        WHEN lower(x.key) IN ('hgnc', 'hgnc_id') THEN upper(regexp_replace(x.value, '^HGNC:', '', 'i'))
                        WHEN lower(x.key) IN ('patent', 'publication_number') THEN upper(
                            regexp_replace(x.value, '[[:space:]-]+', '', 'g')
                        )
                        WHEN lower(x.key) IN (
                            'uniprot', 'uniprotkb', 'uniprot_id', 'ensembl', 'ensembl_id',
                            'chembl', 'chembl_id', 'drugbank', 'drugbank_id', 'pubchem',
                            'pubchem_cid', 'cid', 'clinicaltrials', 'nct', 'nct_id',
                            'efo', 'efo_id', 'mesh', 'mesh_id'
                        ) THEN upper(x.value)
                        ELSE lower(x.value)
                    END,
                    lower(x.key) IN (
                        'hgnc', 'hgnc_id', 'uniprot', 'uniprotkb', 'uniprot_id',
                        'ensembl', 'ensembl_id', 'chembl', 'chembl_id', 'drugbank',
                        'drugbank_id', 'pubchem', 'pubchem_cid', 'cid', 'clinicaltrials',
                        'nct', 'nct_id', 'doi', 'efo', 'efo_id', 'mesh', 'mesh_id',
                        'patent', 'publication_number'
                    ),
                    NULL, '{"origin":"entity_external_ids_backfill"}'::json,
                    e.review_status, e.created_at, e.updated_at
                FROM entities e
                CROSS JOIN LATERAL json_each_text(e.external_ids) AS x(key, value)
                WHERE btrim(x.key) <> '' AND btrim(x.value) <> ''
                ON CONFLICT DO NOTHING
                """
            )
        )

    op.create_table(
        "ontology_terms",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("ontology_name", sa.String(100), nullable=False),
        sa.Column("ontology_version", sa.String(100), nullable=False),
        sa.Column("term_id", sa.String(200), nullable=False),
        sa.Column("entity_type", entity_type, nullable=False),
        sa.Column("preferred_label", sa.String(500), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("synonyms", sa.JSON(), nullable=False),
        sa.Column("parent_term_ids", sa.JSON(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "ontology_name", "ontology_version", "term_id"),
    )
    op.create_index("ix_ontology_terms_lookup", "ontology_terms", ["tenant_id", "ontology_name", "term_id"])
    for column in ("tenant_id", "entity_type", "active"):
        op.create_index(f"ix_ontology_terms_{column}", "ontology_terms", [column])

    op.create_table(
        "entity_ontology_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("ontology_term_id", sa.String(36), nullable=False),
        sa.Column("mapping_type", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_document_id", sa.String(36), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("review_status", review_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mapping_type IN ('exact', 'broad', 'narrow', 'related')", name="ck_ontology_mapping_type"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_ontology_mapping_confidence"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["ontology_term_id"], ["ontology_terms.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "entity_id", "ontology_term_id", "mapping_type"),
    )
    for column in ("tenant_id", "entity_id", "ontology_term_id", "source_document_id", "review_status"):
        op.create_index(f"ix_entity_ontology_mappings_{column}", "entity_ontology_mappings", [column])

    op.create_table(
        "entity_resolution_cases",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("source_entity_id", sa.String(36), nullable=False),
        sa.Column("candidate_entity_id", sa.String(36), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("risk_tier", sa.String(20), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("status", resolution_status, nullable=False),
        sa.Column("proposed_by", sa.String(100), nullable=False),
        sa.Column("reviewed_by_user_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.String(4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source_entity_id <> candidate_entity_id", name="ck_resolution_distinct_entities"),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_resolution_score"),
        sa.CheckConstraint("risk_tier IN ('low', 'medium', 'high')", name="ck_resolution_risk_tier"),
        sa.ForeignKeyConstraint(["candidate_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "source_entity_id", "candidate_entity_id"),
    )
    resolution_indexes = (
        "tenant_id",
        "source_entity_id",
        "candidate_entity_id",
        "risk_tier",
        "status",
        "reviewed_by_user_id",
    )
    for column in resolution_indexes:
        op.create_index(f"ix_entity_resolution_cases_{column}", "entity_resolution_cases", [column])

    op.create_table(
        "entity_canonical_links",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("alias_entity_id", sa.String(36), nullable=False),
        sa.Column("canonical_entity_id", sa.String(36), nullable=False),
        sa.Column("resolution_case_id", sa.String(36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("alias_entity_id <> canonical_entity_id", name="ck_canonical_link_distinct_entities"),
        sa.ForeignKeyConstraint(["alias_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["canonical_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["resolution_case_id"], ["entity_resolution_cases.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "alias_entity_id"),
    )
    for column in ("tenant_id", "alias_entity_id", "canonical_entity_id", "resolution_case_id", "active"):
        op.create_index(f"ix_entity_canonical_links_{column}", "entity_canonical_links", [column])

    op.create_table(
        "entity_resolution_decisions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("resolution_case_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("decided_by_user_id", sa.String(36), nullable=False),
        sa.Column("notes", sa.String(4000), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('approve', 'reject', 'revert')", name="ck_resolution_decision_action"),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["resolution_case_id"], ["entity_resolution_cases.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "resolution_case_id", "decided_by_user_id", "created_at"):
        op.create_index(f"ix_entity_resolution_decisions_{column}", "entity_resolution_decisions", [column])

    tables = (
        "entity_identifiers",
        "ontology_terms",
        "entity_ontology_mappings",
        "entity_resolution_cases",
        "entity_canonical_links",
        "entity_resolution_decisions",
    )
    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in tables:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            op.execute(
                sa.text(f'CREATE POLICY "tenant_isolation" ON "{table}" USING ({predicate}) WITH CHECK ({predicate})')
            )
        op.execute(
            sa.text(
                "CREATE FUNCTION platform_private.reject_identity_decision_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "RAISE EXCEPTION 'entity resolution decisions are append-only'; END; $$"
            )
        )
        op.execute(
            sa.text(
                'CREATE TRIGGER "immutable_entity_resolution_decisions" '
                'BEFORE UPDATE OR DELETE ON "entity_resolution_decisions" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_identity_decision_mutation()"
            )
        )


def downgrade() -> None:
    tables = (
        "entity_resolution_decisions",
        "entity_canonical_links",
        "entity_resolution_cases",
        "entity_ontology_mappings",
        "ontology_terms",
        "entity_identifiers",
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP TRIGGER "immutable_entity_resolution_decisions" ON "entity_resolution_decisions"'))
        op.execute(sa.text("DROP FUNCTION platform_private.reject_identity_decision_mutation()"))
        for table in tables:
            op.execute(sa.text(f'DROP POLICY "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    for table in tables:
        op.drop_table(table)
    op.drop_index("ix_entities_tenant_type_normalized_name", table_name="entities")
    unique_name = "entities_tenant_id_entity_type_normalized_name_key"
    if bind.dialect.name == "postgresql":
        op.create_unique_constraint(
            unique_name,
            "entities",
            ["tenant_id", "entity_type", "normalized_name"],
        )
    else:
        with op.batch_alter_table("entities") as batch_op:
            batch_op.create_unique_constraint(
                unique_name,
                ["tenant_id", "entity_type", "normalized_name"],
            )
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(*RESOLUTION_STATUSES, name="resolutionstatus").drop(bind, checkfirst=True)
