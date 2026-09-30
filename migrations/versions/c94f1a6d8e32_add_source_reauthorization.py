"""add source reauthorization

Revision ID: c94f1a6d8e32
Revises: b83e0f5c7d21
Create Date: 2026-07-19 03:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c94f1a6d8e32"
down_revision: str | Sequence[str] | None = "b83e0f5c7d21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_VERSION_UNIQUE_COLUMNS = ["tenant_id", "source_asset_id", "content_sha256"]
NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s_%(column_2_name)s"}
GENERATED_UNIQUE_NAME = "uq_source_versions_tenant_id_source_asset_id_content_sha256"


def _source_content_unique_name() -> str:
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("source_versions"):
        if list(constraint.get("column_names") or []) == SOURCE_VERSION_UNIQUE_COLUMNS:
            return str(constraint.get("name") or GENERATED_UNIQUE_NAME)
    raise RuntimeError("source version content uniqueness constraint was not found")


def upgrade() -> None:
    source_content_unique_name = _source_content_unique_name()
    with op.batch_alter_table("source_versions", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(source_content_unique_name, type_="unique")
    with op.batch_alter_table("data_lifecycle_events") as batch_op:
        batch_op.drop_constraint("ck_data_lifecycle_event_action", type_="check")
        batch_op.create_check_constraint(
            "ck_data_lifecycle_event_action",
            "action IN ('purge', 'blocked', 'reauthorize')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    reauthorization_events = connection.scalar(
        sa.text("SELECT count(*) FROM data_lifecycle_events WHERE action = 'reauthorize'")
    )
    duplicate_content = connection.execute(
        sa.text(
            "SELECT tenant_id, source_asset_id, content_sha256 "
            "FROM source_versions GROUP BY tenant_id, source_asset_id, content_sha256 HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if int(reauthorization_events or 0):
        raise RuntimeError("reauthorization lifecycle events prevent downgrade")
    if duplicate_content is not None:
        raise RuntimeError("duplicate historical source content prevents downgrade")
    with op.batch_alter_table("data_lifecycle_events") as batch_op:
        batch_op.drop_constraint("ck_data_lifecycle_event_action", type_="check")
        batch_op.create_check_constraint(
            "ck_data_lifecycle_event_action",
            "action IN ('purge', 'blocked')",
        )
    with op.batch_alter_table("source_versions", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.create_unique_constraint(GENERATED_UNIQUE_NAME, SOURCE_VERSION_UNIQUE_COLUMNS)
