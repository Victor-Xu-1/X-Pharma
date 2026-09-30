"""add tenant-scoped LLM provider catalog

Revision ID: a1c7e5d9b246
Revises: 9d7e3f1a2b46
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c7e5d9b246"
down_revision: str | Sequence[str] | None = "9d7e3f1a2b46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("model", sa.String(length=500), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("api_key_fingerprint", sa.String(length=16), nullable=False),
        sa.Column("response_format_mode", sa.String(length=32), nullable=False),
        sa.Column("thinking_mode", sa.String(length=32), nullable=False),
        sa.Column("include_schema_in_prompt", sa.Boolean(), nullable=False),
        sa.Column("max_output_tokens_per_segment", sa.Integer(), nullable=False),
        sa.Column("request_timeout_seconds", sa.Float(), nullable=False),
        sa.Column("request_attempts", sa.Integer(), nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=32), nullable=True),
        sa.Column("last_test_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority >= 0", name="ck_llm_provider_priority_nonnegative"),
        sa.CheckConstraint("version > 0", name="ck_llm_provider_version_positive"),
        sa.CheckConstraint("request_timeout_seconds BETWEEN 1 AND 600", name="ck_llm_provider_timeout"),
        sa.CheckConstraint("request_attempts BETWEEN 1 AND 8", name="ck_llm_provider_attempts"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_llm_provider_tenant_name"),
        sa.UniqueConstraint("tenant_id", "priority", name="uq_llm_provider_tenant_priority"),
    )
    op.create_index("ix_llm_provider_configs_tenant_id", "llm_provider_configs", ["tenant_id"])
    op.create_index("ix_llm_provider_configs_active", "llm_provider_configs", ["active"])
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "llm_provider_configs" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "llm_provider_configs" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "llm_provider_configs" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY "tenant_isolation" ON "llm_provider_configs"'))
        op.execute(sa.text('ALTER TABLE "llm_provider_configs" NO FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "llm_provider_configs" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_llm_provider_configs_active", table_name="llm_provider_configs")
    op.drop_index("ix_llm_provider_configs_tenant_id", table_name="llm_provider_configs")
    op.drop_table("llm_provider_configs")
