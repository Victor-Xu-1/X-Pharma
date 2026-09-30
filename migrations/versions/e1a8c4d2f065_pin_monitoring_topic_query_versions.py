"""pin monitoring topics to saved search versions

Revision ID: e1a8c4d2f065
Revises: d9f7b1c5e234
Create Date: 2026-07-23 21:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1a8c4d2f065"
down_revision: str | Sequence[str] | None = "d9f7b1c5e234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("monitoring_topics") as batch_op:
        batch_op.add_column(sa.Column("query_version", sa.Integer(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE monitoring_topics AS topic "
            "SET query_version = saved.query_version "
            "FROM saved_searches AS saved "
            "WHERE saved.id = topic.saved_search_id AND saved.tenant_id = topic.tenant_id"
        )
    )
    with op.batch_alter_table("monitoring_topics") as batch_op:
        batch_op.alter_column("query_version", existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(
            "ck_monitoring_topic_query_version_positive",
            "query_version > 0",
        )
        batch_op.create_index(
            "ix_monitoring_topic_saved_search_version",
            ["tenant_id", "saved_search_id", "query_version"],
        )
        batch_op.create_foreign_key(
            "fk_monitoring_topic_saved_search_version",
            "saved_search_versions",
            ["tenant_id", "saved_search_id", "query_version"],
            ["tenant_id", "saved_search_id", "version"],
        )


def downgrade() -> None:
    with op.batch_alter_table("monitoring_topics") as batch_op:
        batch_op.drop_constraint("fk_monitoring_topic_saved_search_version", type_="foreignkey")
        batch_op.drop_index("ix_monitoring_topic_saved_search_version")
        batch_op.drop_constraint("ck_monitoring_topic_query_version_positive", type_="check")
        batch_op.drop_column("query_version")
