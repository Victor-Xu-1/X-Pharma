"""add authoritative delivery license policies

Revision ID: 6e2a9c1d4f70
Revises: 1b8e6d3a9f24
Create Date: 2026-07-17 15:40:00

"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "6e2a9c1d4f70"
down_revision: str | Sequence[str] | None = "1b8e6d3a9f24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXPORT_DATASETS = (
    "entities",
    "structures",
    "bioactivities",
    "competitive_programs",
    "clinical_trials",
    "patents",
    "deals",
)


def _restricted_export_policy() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "policy_version": "migration-restricted-v1",
        "attribution": "Tenant-owned authoritative data",
        "datasets": {dataset: {"fields": ["id"], "filter_fields": ["id"]} for dataset in _EXPORT_DATASETS},
    }


def _internal_evidence_policy(legacy: object) -> dict[str, Any]:
    legacy_hash = hashlib.sha256(
        json.dumps(
            legacy,
            ensure_ascii=True,
            default=str,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "1.0",
        "license_id": "tenant-owned-internal",
        "policy_version": "migration-tenant-owned-v1",
        "permitted_channels": ["mcp", "web"],
        "allowed_fields": [
            "content",
            "content_sha256",
            "document_name",
            "evidence_claim_id",
            "locator",
            "review_status",
            "source_uri",
            "source_version_id",
            "subject_entity_id",
        ],
        "max_content_chars": 5000,
        "attribution": "Tenant-provided source material",
        "metadata": {
            "migration": revision,
            "legacy_policy_sha256": legacy_hash,
        },
    }


def upgrade() -> None:
    op.add_column(
        "commercial_export_policies",
        sa.Column("field_policy", sa.JSON(), nullable=True),
    )
    op.add_column(
        "data_export_jobs",
        sa.Column("license_policy_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "data_export_jobs",
        sa.Column("license_policy_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "data_export_jobs",
        sa.Column("license_attribution", sa.String(length=500), nullable=True),
    )

    bind = op.get_bind()
    export_policies = sa.table(
        "commercial_export_policies",
        sa.column("field_policy", sa.JSON()),
    )
    bind.execute(export_policies.update().values(field_policy=_restricted_export_policy()))

    export_jobs = sa.table(
        "data_export_jobs",
        sa.column("license_policy_version", sa.String(length=100)),
        sa.column("license_policy_sha256", sa.String(length=64)),
        sa.column("license_attribution", sa.String(length=500)),
    )
    bind.execute(
        export_jobs.update().values(
            license_policy_version="legacy-pre-field-license-v0",
            license_policy_sha256="0" * 64,
            license_attribution="Legacy export; delivery disabled until recreated",
        )
    )

    tenant_datasets = sa.table(
        "tenant_datasets",
        sa.column("id", sa.String(length=36)),
        sa.column("license_policy", sa.JSON()),
    )
    rows = bind.execute(sa.select(tenant_datasets.c.id, tenant_datasets.c.license_policy)).mappings()
    required_policy_keys = {
        "schema_version",
        "license_id",
        "policy_version",
        "permitted_channels",
        "allowed_fields",
        "attribution",
    }
    for row in rows:
        policy = row["license_policy"]
        if not isinstance(policy, dict) or not required_policy_keys.issubset(policy):
            bind.execute(
                tenant_datasets.update()
                .where(tenant_datasets.c.id == row["id"])
                .values(license_policy=_internal_evidence_policy(policy))
            )

    with op.batch_alter_table("commercial_export_policies") as batch_op:
        batch_op.alter_column(
            "field_policy",
            existing_type=sa.JSON(),
            nullable=False,
        )
    with op.batch_alter_table("data_export_jobs") as batch_op:
        batch_op.alter_column(
            "license_policy_version",
            existing_type=sa.String(length=100),
            nullable=False,
        )
        batch_op.alter_column(
            "license_policy_sha256",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.alter_column(
            "license_attribution",
            existing_type=sa.String(length=500),
            nullable=False,
        )


def downgrade() -> None:
    op.drop_column("data_export_jobs", "license_attribution")
    op.drop_column("data_export_jobs", "license_policy_sha256")
    op.drop_column("data_export_jobs", "license_policy_version")
    op.drop_column("commercial_export_policies", "field_policy")
