"""add governed asynchronous exports

Revision ID: e57c9f1a4b63
Revises: d46b8e0f3a52
Create Date: 2026-07-16 16:20:00

"""

from collections.abc import Sequence
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "e57c9f1a4b63"
down_revision: str | Sequence[str] | None = "d46b8e0f3a52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commercial_export_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("billing_account_id", sa.String(length=36), nullable=False),
        sa.Column("policy_version", sa.String(length=100), server_default="export-v1", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("allowed_datasets", sa.JSON(), nullable=False),
        sa.Column("allowed_formats", sa.JSON(), nullable=False),
        sa.Column("max_records_per_job", sa.Integer(), server_default="5000", nullable=False),
        sa.Column("daily_record_limit", sa.Integer(), server_default="20000", nullable=False),
        sa.Column("approval_required_above", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("max_artifact_bytes", sa.Integer(), server_default="100000000", nullable=False),
        sa.Column("artifact_ttl_seconds", sa.Integer(), server_default="86400", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("max_records_per_job > 0", name="ck_export_policy_records_per_job"),
        sa.CheckConstraint("daily_record_limit > 0", name="ck_export_policy_daily_records"),
        sa.CheckConstraint("approval_required_above >= 0", name="ck_export_policy_approval_threshold"),
        sa.CheckConstraint(
            "approval_required_above <= max_records_per_job",
            name="ck_export_policy_approval_within_job_limit",
        ),
        sa.CheckConstraint("max_artifact_bytes > 0", name="ck_export_policy_artifact_bytes"),
        sa.CheckConstraint("artifact_ttl_seconds > 0", name="ck_export_policy_artifact_ttl"),
        sa.ForeignKeyConstraint(["billing_account_id"], ["billing_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("billing_account_id"),
        sa.UniqueConstraint("tenant_id", "billing_account_id"),
    )
    for column in ("billing_account_id", "enabled", "tenant_id"):
        op.create_index(
            f"ix_commercial_export_policies_{column}",
            "commercial_export_policies",
            [column],
        )

    op.create_table(
        "data_export_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("billing_account_id", sa.String(length=36), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=False),
        sa.Column("agent_client_id", sa.String(length=36), nullable=False),
        sa.Column("reservation_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.String(length=500), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_sha256", sa.String(length=64), nullable=False),
        sa.Column("dataset", sa.String(length=100), nullable=False),
        sa.Column("export_format", sa.String(length=20), nullable=False),
        sa.Column("filters_json", sa.JSON(), nullable=False),
        sa.Column("fields_json", sa.JSON(), nullable=False),
        sa.Column("max_records", sa.Integer(), nullable=False),
        sa.Column("max_billable_units", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("approved_by", sa.String(length=500), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workflow_id", sa.String(length=200), nullable=False),
        sa.Column("record_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("artifact_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("manifest_uri", sa.Text(), nullable=True),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("manifest_signature", sa.String(length=128), nullable=True),
        sa.Column("manifest_key_id", sa.String(length=120), nullable=True),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("actor_type IN ('agent', 'api_key')", name="ck_export_job_actor_type"),
        sa.CheckConstraint("export_format IN ('jsonl', 'csv')", name="ck_export_job_format"),
        sa.CheckConstraint(
            "state IN ('pending_approval', 'queued', 'running', 'completed', 'failed', "
            "'cancel_requested', 'cancelled', 'expired')",
            name="ck_export_job_state",
        ),
        sa.CheckConstraint("max_records > 0", name="ck_export_job_max_records"),
        sa.CheckConstraint("record_count >= 0", name="ck_export_job_record_count"),
        sa.CheckConstraint("artifact_bytes >= 0", name="ck_export_job_artifact_bytes"),
        sa.ForeignKeyConstraint(["agent_client_id"], ["agent_clients.id"]),
        sa.ForeignKeyConstraint(["billing_account_id"], ["billing_accounts.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["usage_reservations.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["commercial_subscriptions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_id"),
        sa.UniqueConstraint("tenant_id", "agent_client_id", "idempotency_key"),
        sa.UniqueConstraint("workflow_id"),
    )
    for column in (
        "agent_client_id",
        "billing_account_id",
        "created_at",
        "dataset",
        "expires_at",
        "requested_at",
        "reservation_id",
        "state",
        "subject_id",
        "subscription_id",
        "tenant_id",
    ):
        op.create_index(f"ix_data_export_jobs_{column}", "data_export_jobs", [column])
    op.create_index(
        "ix_data_export_jobs_state_created",
        "data_export_jobs",
        ["tenant_id", "state", "created_at"],
    )

    bind = op.get_bind()
    datasets = [
        "entities",
        "structures",
        "bioactivities",
        "competitive_programs",
        "clinical_trials",
        "patents",
        "deals",
    ]
    formats = ["jsonl", "csv"]
    accounts = bind.execute(sa.text("SELECT id, tenant_id FROM billing_accounts")).mappings()
    for account in accounts:
        statement = sa.text(
            "INSERT INTO commercial_export_policies "
            "(id, tenant_id, billing_account_id, policy_version, enabled, allowed_datasets, allowed_formats, "
            "max_records_per_job, daily_record_limit, approval_required_above, max_artifact_bytes, "
            "artifact_ttl_seconds, created_at, updated_at) VALUES "
            "(:id, :tenant_id, :billing_account_id, 'export-v1', true, :datasets, :formats, "
            "5000, 20000, 1000, 100000000, 86400, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ).bindparams(
            sa.bindparam("datasets", type_=sa.JSON()),
            sa.bindparam("formats", type_=sa.JSON()),
        )
        bind.execute(
            statement,
            {
                "id": str(uuid.uuid4()),
                "tenant_id": account["tenant_id"],
                "billing_account_id": account["id"],
                "datasets": datasets,
                "formats": formats,
            },
        )

    if bind.dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        for table in ("commercial_export_policies", "data_export_jobs"):
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
        for table in ("data_export_jobs", "commercial_export_policies"):
            op.execute(sa.text(f'DROP POLICY IF EXISTS "tenant_isolation" ON "{table}"'))
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    op.drop_table("data_export_jobs")
    op.drop_table("commercial_export_policies")
