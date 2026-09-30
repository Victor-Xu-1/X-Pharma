"""expand source lifecycle controls

Revision ID: b83e0f5c7d21
Revises: a72d9e4b6c10
Create Date: 2026-07-19 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b83e0f5c7d21"
down_revision: str | Sequence[str] | None = "a72d9e4b6c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("data_retention_policies") as batch_op:
        batch_op.drop_constraint("ck_retention_policy_data_class", type_="check")
        batch_op.create_check_constraint(
            "ck_retention_policy_data_class",
            "data_class IN ('commercial_export_artifact', 'source_asset_snapshot')",
        )
    with op.batch_alter_table("legal_holds") as batch_op:
        batch_op.drop_constraint("ck_legal_hold_scope_type", type_="check")
        batch_op.create_check_constraint(
            "ck_legal_hold_scope_type",
            "scope_type IN ('tenant', 'billing_account', 'data_export_job', 'data_source', 'source_asset')",
        )


def downgrade() -> None:
    connection = op.get_bind()
    source_policies = connection.scalar(
        sa.text("SELECT count(*) FROM data_retention_policies WHERE data_class = 'source_asset_snapshot'")
    )
    source_holds = connection.scalar(
        sa.text("SELECT count(*) FROM legal_holds WHERE scope_type IN ('data_source', 'source_asset')")
    )
    if int(source_policies or 0) or int(source_holds or 0):
        raise RuntimeError("remove source lifecycle policies and holds before downgrading")
    with op.batch_alter_table("legal_holds") as batch_op:
        batch_op.drop_constraint("ck_legal_hold_scope_type", type_="check")
        batch_op.create_check_constraint(
            "ck_legal_hold_scope_type",
            "scope_type IN ('tenant', 'billing_account', 'data_export_job')",
        )
    with op.batch_alter_table("data_retention_policies") as batch_op:
        batch_op.drop_constraint("ck_retention_policy_data_class", type_="check")
        batch_op.create_check_constraint(
            "ck_retention_policy_data_class",
            "data_class IN ('commercial_export_artifact')",
        )
