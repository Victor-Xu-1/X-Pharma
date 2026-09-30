"""sign tenant RLS context

Revision ID: 9a62f73d41e8
Revises: 332782d8b0cf
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a62f73d41e8"
down_revision: str | Sequence[str] | None = "332782d8b0cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = (
    "activity_measurements",
    "assays",
    "audit_events",
    "clinical_trial_profiles",
    "compound_structures",
    "data_sources",
    "deal_profiles",
    "development_programs",
    "entities",
    "entity_aliases",
    "evidence_claims",
    "extraction_runs",
    "ingestion_assets",
    "ingestion_findings",
    "ingestion_runs",
    "knowledge_citations",
    "knowledge_links",
    "knowledge_page_versions",
    "knowledge_pages",
    "outbox_events",
    "patent_families",
    "relationships",
    "research_bundles",
    "retrieval_projections",
    "review_tasks",
    "source_assets",
    "source_documents",
    "source_versions",
    "staged_facts",
    "target_profiles",
    "tenant_datasets",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS platform_private"))
    op.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS platform_private.runtime_secrets ("
            "secret_name text PRIMARY KEY, secret_value text NOT NULL)"
        )
    )
    op.execute(sa.text("REVOKE ALL ON SCHEMA platform_private FROM PUBLIC"))
    op.execute(sa.text("REVOKE ALL ON ALL TABLES IN SCHEMA platform_private FROM PUBLIC"))
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION public.app_current_tenant_id()
            RETURNS text
            LANGUAGE plpgsql
            STABLE
            SECURITY DEFINER
            SET search_path = pg_catalog, platform_private, public
            AS $$
            DECLARE
                requested_tenant text;
                supplied_signature text;
                signing_secret text;
                expected_signature text;
            BEGIN
                requested_tenant := current_setting('app.tenant_id', true);
                supplied_signature := current_setting('app.tenant_signature', true);
                SELECT secret_value INTO signing_secret
                FROM platform_private.runtime_secrets
                WHERE secret_name = 'tenant_context';

                IF requested_tenant IS NULL OR requested_tenant = '' OR signing_secret IS NULL THEN
                    RETURN NULL;
                END IF;
                expected_signature := encode(
                    public.hmac(
                        convert_to(requested_tenant, 'UTF8'),
                        convert_to(signing_secret, 'UTF8'),
                        'sha256'
                    ),
                    'hex'
                );
                IF supplied_signature IS DISTINCT FROM expected_signature THEN
                    RETURN NULL;
                END IF;
                RETURN requested_tenant;
            END;
            $$
            """
        )
    )
    op.execute(sa.text("REVOKE ALL ON FUNCTION public.app_current_tenant_id() FROM PUBLIC"))
    op.execute(sa.text("GRANT EXECUTE ON FUNCTION public.app_current_tenant_id() TO PUBLIC"))
    for table in TENANT_TABLES:
        op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
        op.execute(
            sa.text(
                f'CREATE POLICY "tenant_isolation" ON "{table}" '
                "USING (tenant_id = public.app_current_tenant_id()) "
                "WITH CHECK (tenant_id = public.app_current_tenant_id())"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    predicate = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')"
    for table in TENANT_TABLES:
        op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
        op.execute(
            sa.text(
                f'CREATE POLICY "tenant_isolation" ON "{table}" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )
    op.execute(sa.text("DROP FUNCTION IF EXISTS public.app_current_tenant_id()"))
    op.execute(sa.text("DROP TABLE IF EXISTS platform_private.runtime_secrets"))
    op.execute(sa.text("DROP SCHEMA IF EXISTS platform_private"))
