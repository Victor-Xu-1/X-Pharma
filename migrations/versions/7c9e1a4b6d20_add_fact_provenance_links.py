"""add fact provenance links

Revision ID: 7c9e1a4b6d20
Revises: 0b8d3f6a9c42
Create Date: 2026-07-19 16:30:00
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "7c9e1a4b6d20"
down_revision: str | Sequence[str] | None = "0b8d3f6a9c42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fact_provenance_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("staged_fact_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_claim_id", sa.String(length=36), nullable=False),
        sa.Column("source_asset_id", sa.String(length=36), nullable=False),
        sa.Column("source_version_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("dataset_key", sa.String(length=80), nullable=False),
        sa.Column("source_locator", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["evidence_claim_id"], ["evidence_claims.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["source_assets.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"]),
        sa.ForeignKeyConstraint(["staged_fact_id"], ["staged_facts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "resource_type",
            "resource_id",
            "staged_fact_id",
        ),
    )
    for column in (
        "tenant_id",
        "resource_type",
        "resource_id",
        "staged_fact_id",
        "evidence_claim_id",
        "source_asset_id",
        "source_version_id",
        "source_document_id",
        "dataset_key",
    ):
        op.create_index(
            op.f(f"ix_fact_provenance_links_{column}"),
            "fact_provenance_links",
            [column],
            unique=False,
        )
    op.create_index(
        "ix_fact_provenance_resource",
        "fact_provenance_links",
        ["tenant_id", "resource_type", "resource_id"],
        unique=False,
    )
    op.create_index(
        "ix_fact_provenance_dataset_created",
        "fact_provenance_links",
        ["tenant_id", "dataset_key", "created_at"],
        unique=False,
    )
    _backfill_links(op.get_bind())
    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "fact_provenance_links" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "fact_provenance_links" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(
                'CREATE POLICY "tenant_isolation" ON "fact_provenance_links" '
                f"USING ({predicate}) WITH CHECK ({predicate})"
            )
        )


def _backfill_links(connection: sa.Connection) -> None:
    # SQLAlchemy cannot portably address JSON fields across SQLite and PostgreSQL,
    # so stream publication events and resolve their relational source chain in batches.
    statement = sa.text(
        """
        SELECT id, tenant_id, payload, created_at
          FROM outbox_events
         WHERE event_type = 'governance.fact.published'
         ORDER BY created_at, id
        """
    )
    for batch in _stream_batches(connection, statement, batch_size=500):
        parsed_events: list[tuple[Any, dict[str, Any], str, str]] = []
        for event in batch:
            payload = _payload(event.payload)
            staged_fact_id = payload.get("staged_fact_id")
            claim_id = payload.get("evidence_claim_id")
            if not isinstance(staged_fact_id, str) or not isinstance(claim_id, str):
                continue
            parsed_events.append((event, payload, staged_fact_id, claim_id))
        if not parsed_events:
            continue
        staged_fact_ids = sorted({event[2] for event in parsed_events})
        source_statement = sa.text(
            """
            SELECT sf.id AS staged_fact_id, sf.tenant_id, sf.source_document_id, sf.source_locator,
                   er.source_version_id, sv.source_asset_id, ds.dataset_key
              FROM staged_facts AS sf
              JOIN extraction_runs AS er ON er.id = sf.extraction_run_id
              JOIN source_versions AS sv ON sv.id = er.source_version_id
              JOIN source_assets AS source_asset ON source_asset.id = sv.source_asset_id
              JOIN data_sources AS ds ON ds.id = source_asset.data_source_id
             WHERE sf.id IN :staged_fact_ids
            """
        ).bindparams(sa.bindparam("staged_fact_ids", expanding=True))
        sources = {
            (row["tenant_id"], row["staged_fact_id"]): row
            for row in connection.execute(
                source_statement,
                {"staged_fact_ids": staged_fact_ids},
            ).mappings()
        }
        pending: dict[str, dict[str, Any]] = {}
        for event, payload, staged_fact_id, claim_id in parsed_events:
            source = sources.get((event.tenant_id, staged_fact_id))
            if source is None or not source["source_document_id"] or not source["dataset_key"]:
                continue
            projections: list[tuple[str, str]] = [("evidence_claim", claim_id)]
            raw_projections = payload.get("structured_projections")
            if isinstance(raw_projections, list):
                for projection in raw_projections:
                    if not isinstance(projection, dict):
                        continue
                    resource_type = projection.get("resource_type")
                    resource_id = projection.get("resource_id")
                    if isinstance(resource_type, str) and isinstance(resource_id, str):
                        projections.append((resource_type, resource_id))
            created_at = event.created_at or datetime.now(UTC)
            for resource_type, resource_id in projections:
                link_id = _link_id(event.tenant_id, staged_fact_id, resource_type, resource_id)
                pending[link_id] = {
                    "id": link_id,
                    "tenant_id": event.tenant_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "staged_fact_id": staged_fact_id,
                    "evidence_claim_id": claim_id,
                    "source_asset_id": source["source_asset_id"],
                    "source_version_id": source["source_version_id"],
                    "source_document_id": source["source_document_id"],
                    "dataset_key": source["dataset_key"],
                    "source_locator": source["source_locator"],
                    "created_at": created_at,
                }
        if pending:
            existing_statement = sa.text("SELECT id FROM fact_provenance_links WHERE id IN :link_ids").bindparams(
                sa.bindparam("link_ids", expanding=True)
            )
            existing = set(
                connection.scalars(
                    existing_statement,
                    {"link_ids": sorted(pending)},
                )
            )
            rows = [row for link_id, row in pending.items() if link_id not in existing]
        else:
            rows = []
        if rows:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO fact_provenance_links
                        (id, tenant_id, resource_type, resource_id, staged_fact_id,
                         evidence_claim_id, source_asset_id, source_version_id,
                         source_document_id, dataset_key, source_locator, created_at)
                    VALUES
                        (:id, :tenant_id, :resource_type, :resource_id, :staged_fact_id,
                         :evidence_claim_id, :source_asset_id, :source_version_id,
                         :source_document_id, :dataset_key, :source_locator, :created_at)
                    """
                ),
                rows,
            )


def _stream_batches(
    connection: sa.Connection,
    statement: sa.TextClause,
    *,
    batch_size: int,
) -> Iterator[Sequence[Any]]:
    # Keep streaming scoped to this SELECT. Connection-level execution options
    # would leak server-side cursors into the subsequent PostgreSQL DDL.
    result = connection.execute(
        statement.execution_options(
            stream_results=True,
            max_row_buffer=batch_size,
            yield_per=batch_size,
        )
    )
    try:
        while batch := result.fetchmany(batch_size):
            yield batch
    finally:
        result.close()


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _link_id(tenant_id: str, staged_fact_id: str, resource_type: str, resource_id: str) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"pharma-provenance:{tenant_id}:{staged_fact_id}:{resource_type}:{resource_id}",
        )
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "fact_provenance_links"'))
        op.execute(sa.text('ALTER TABLE "fact_provenance_links" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_fact_provenance_dataset_created", table_name="fact_provenance_links")
    op.drop_index("ix_fact_provenance_resource", table_name="fact_provenance_links")
    for column in reversed(
        (
            "tenant_id",
            "resource_type",
            "resource_id",
            "staged_fact_id",
            "evidence_claim_id",
            "source_asset_id",
            "source_version_id",
            "source_document_id",
            "dataset_key",
        )
    ):
        op.drop_index(op.f(f"ix_fact_provenance_links_{column}"), table_name="fact_provenance_links")
    op.drop_table("fact_provenance_links")
