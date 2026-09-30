"""enforce immutable knowledge history

Revision ID: 7c9e1a4b6d32
Revises: 5d7e1a3c9b24
Create Date: 2026-07-24 12:50:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c9e1a4b6d32"
down_revision: str | Sequence[str] | None = "5d7e1a3c9b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_IMMUTABLE_TABLES = (
    ("immutable_knowledge_page_versions", "knowledge_page_versions"),
    ("immutable_knowledge_citations", "knowledge_citations"),
    ("immutable_knowledge_links", "knowledge_links"),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        sa.text(
            "CREATE FUNCTION platform_private.reject_knowledge_history_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN "
            "RAISE EXCEPTION 'knowledge history is append-only: %', TG_TABLE_NAME; "
            "END; $$"
        )
    )
    for trigger, table in _IMMUTABLE_TABLES:
        op.execute(
            sa.text(
                f'CREATE TRIGGER "{trigger}" BEFORE UPDATE OR DELETE ON "{table}" '
                "FOR EACH ROW EXECUTE FUNCTION platform_private.reject_knowledge_history_mutation()"
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for trigger, table in reversed(_IMMUTABLE_TABLES):
        op.execute(sa.text(f'DROP TRIGGER "{trigger}" ON "{table}"'))
    op.execute(sa.text("DROP FUNCTION platform_private.reject_knowledge_history_mutation()"))
