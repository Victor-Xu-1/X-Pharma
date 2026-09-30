"""align export dataset allowlists with licensed fields

Revision ID: 9a2d4f6b8c10
Revises: 7c9e1a4b6d20
Create Date: 2026-07-19 18:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9a2d4f6b8c10"
down_revision: str | Sequence[str] | None = "7c9e1a4b6d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REPAIRED_DATASETS = ("regulatory_events", "fact_provenance")


def _policy_table() -> sa.TableClause:
    return sa.table(
        "commercial_export_policies",
        sa.column("id", sa.String()),
        sa.column("allowed_datasets", sa.JSON()),
        sa.column("field_policy", sa.JSON()),
    )


def _licensed_datasets(field_policy: object) -> set[str]:
    if not isinstance(field_policy, dict):
        return set()
    datasets = field_policy.get("datasets")
    if not isinstance(datasets, dict):
        return set()
    return {key for key in datasets if isinstance(key, str)}


def _allowed_datasets(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return []
    return list(value)


def upgrade() -> None:
    table = _policy_table()
    connection = op.get_bind()
    rows = connection.execute(sa.select(table.c.id, table.c.allowed_datasets, table.c.field_policy)).mappings()
    for row in rows:
        allowed = _allowed_datasets(row["allowed_datasets"])
        licensed = _licensed_datasets(row["field_policy"])
        repaired = sorted(set(allowed).union(licensed.intersection(_REPAIRED_DATASETS)))
        if repaired != allowed:
            connection.execute(sa.update(table).where(table.c.id == row["id"]).values(allowed_datasets=repaired))


def downgrade() -> None:
    table = _policy_table()
    connection = op.get_bind()
    rows = connection.execute(sa.select(table.c.id, table.c.allowed_datasets)).mappings()
    for row in rows:
        allowed = _allowed_datasets(row["allowed_datasets"])
        downgraded = [item for item in allowed if item != "fact_provenance"]
        if downgraded != allowed:
            connection.execute(sa.update(table).where(table.c.id == row["id"]).values(allowed_datasets=downgraded))
