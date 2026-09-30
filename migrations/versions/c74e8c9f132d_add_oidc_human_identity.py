"""add OIDC human identity

Revision ID: c74e8c9f132d
Revises: 9a62f73d41e8
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c74e8c9f132d"
down_revision: str | Sequence[str] | None = "9a62f73d41e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("oidc_issuer", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("oidc_subject", sa.String(length=500), nullable=True))
        batch.create_unique_constraint("uq_users_oidc_identity", ["oidc_issuer", "oidc_subject"])
        batch.create_check_constraint(
            "ck_users_oidc_identity_complete",
            "(oidc_issuer IS NULL) = (oidc_subject IS NULL)",
        )
        batch.create_index("ix_users_oidc_issuer", ["oidc_issuer"], unique=False)
        batch.create_index("ix_users_oidc_subject", ["oidc_subject"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_oidc_subject")
        batch.drop_index("ix_users_oidc_issuer")
        batch.drop_constraint("ck_users_oidc_identity_complete", type_="check")
        batch.drop_constraint("uq_users_oidc_identity", type_="unique")
        batch.drop_column("oidc_subject")
        batch.drop_column("oidc_issuer")
