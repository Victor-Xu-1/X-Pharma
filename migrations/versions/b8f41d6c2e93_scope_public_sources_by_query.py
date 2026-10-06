"""Preserve independently configured public source topics.

Revision ID: b8f41d6c2e93
Revises: a3d7f2b9c641
"""

from __future__ import annotations

import hashlib
import json

import sqlalchemy as sa
from alembic import op

revision = "b8f41d6c2e93"
down_revision = "a3d7f2b9c641"
branch_labels = None
depends_on = None

_NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s"}


def _digest(kind: str, rules: list[dict[str, object]]) -> str:
    keys = {
        "CHEMBL": ("target_chembl_id",),
        "CLINICALTRIALS_GOV": ("query_term", "start_date"),
        "PUBMED": ("query_term", "include_abstract"),
    }.get(kind)
    if keys is None:
        return "root"
    if len(rules) != 1:
        raise RuntimeError("Public source scope must be reviewed before migration")
    scope = {key: rules[0].get(key, False if key == "include_abstract" else None) for key in keys}
    if kind == "CHEMBL" and isinstance(scope["target_chembl_id"], str):
        scope["target_chembl_id"] = scope["target_chembl_id"].strip().upper()
    if "query_term" in scope and isinstance(scope["query_term"], str):
        scope["query_term"] = scope["query_term"].strip()
    document = {"source_type": kind.lower(), "scope": scope}
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE data_sources IN ACCESS EXCLUSIVE MODE")
    constraints = sa.inspect(connection).get_unique_constraints("data_sources")
    previous = next(item for item in constraints if item["column_names"] == ["tenant_id", "root_uri"])
    with op.batch_alter_table("data_sources", naming_convention=_NAMING) as batch:
        batch.add_column(sa.Column("scope_digest", sa.String(64), nullable=False, server_default="root"))
        batch.drop_constraint(previous["name"] or "uq_data_sources_tenant_id_root_uri", type_="unique")
        batch.create_unique_constraint("uq_data_source_scope", ["tenant_id", "root_uri", "scope_digest"])
    sources = sa.table(
        "data_sources",
        sa.column("id"),
        sa.column("source_type"),
        sa.column("routing_rules", sa.JSON()),
        sa.column("scope_digest"),
    )
    for row in connection.execute(sa.select(sources.c.id, sources.c.source_type, sources.c.routing_rules)):
        connection.execute(
            sources.update()
            .where(sources.c.id == row.id)
            .values(scope_digest=_digest(row.source_type, row.routing_rules))
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        op.execute("SET LOCAL lock_timeout = '5s'")
        op.execute("SET LOCAL row_security = off")
        op.execute("LOCK TABLE data_sources IN ACCESS EXCLUSIVE MODE")
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM (SELECT tenant_id, root_uri FROM data_sources "
            "GROUP BY tenant_id, root_uri HAVING count(*) > 1) AS shared_roots"
        )
    ):
        raise RuntimeError("Multiple source topics require a preservation plan before downgrade")
    with op.batch_alter_table("data_sources", naming_convention=_NAMING) as batch:
        batch.drop_constraint("uq_data_source_scope", type_="unique")
        batch.create_unique_constraint("uq_data_sources_tenant_id_root_uri", ["tenant_id", "root_uri"])
        batch.drop_column("scope_digest")
