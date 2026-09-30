"""add commercial correlation signals

Revision ID: f6a8c0e2d435
Revises: e5f7b9d1c324
Create Date: 2026-07-17 20:25:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a8c0e2d435"
down_revision: str | Sequence[str] | None = "e5f7b9d1c324"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("commercial_risk_policies") as batch_op:
        batch_op.add_column(
            sa.Column("max_distinct_networks_per_window", sa.Integer(), server_default="8", nullable=False)
        )
        batch_op.add_column(
            sa.Column("max_distinct_credentials_per_window", sa.Integer(), server_default="4", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_risk_distinct_networks",
            "max_distinct_networks_per_window > 0",
        )
        batch_op.create_check_constraint(
            "ck_risk_distinct_credentials",
            "max_distinct_credentials_per_window > 0",
        )
    op.execute(
        sa.text("UPDATE commercial_risk_policies SET policy_version = 'risk-v2' WHERE policy_version = 'risk-v1'")
    )
    with op.batch_alter_table("commercial_risk_policies") as batch_op:
        batch_op.alter_column("max_distinct_networks_per_window", server_default=None)
        batch_op.alter_column("max_distinct_credentials_per_window", server_default=None)

    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.add_column(sa.Column("network_fingerprint", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("credential_fingerprint", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "correlation_key_id",
                sa.String(length=120),
                server_default="legacy-correlation-v1",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_usage_reservation_network_fingerprint",
            "network_fingerprint IS NULL OR length(network_fingerprint) = 64",
        )
        batch_op.create_check_constraint(
            "ck_usage_reservation_credential_fingerprint",
            "credential_fingerprint IS NULL OR length(credential_fingerprint) = 64",
        )
    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.alter_column("correlation_key_id", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("usage_reservations") as batch_op:
        batch_op.drop_constraint("ck_usage_reservation_credential_fingerprint", type_="check")
        batch_op.drop_constraint("ck_usage_reservation_network_fingerprint", type_="check")
        batch_op.drop_column("correlation_key_id")
        batch_op.drop_column("credential_fingerprint")
        batch_op.drop_column("network_fingerprint")

    op.execute(
        sa.text("UPDATE commercial_risk_policies SET policy_version = 'risk-v1' WHERE policy_version = 'risk-v2'")
    )
    with op.batch_alter_table("commercial_risk_policies") as batch_op:
        batch_op.drop_constraint("ck_risk_distinct_credentials", type_="check")
        batch_op.drop_constraint("ck_risk_distinct_networks", type_="check")
        batch_op.drop_column("max_distinct_credentials_per_window")
        batch_op.drop_column("max_distinct_networks_per_window")
