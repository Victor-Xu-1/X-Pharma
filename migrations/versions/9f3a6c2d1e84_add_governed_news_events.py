"""add governed news events

Revision ID: 9f3a6c2d1e84
Revises: 8d2e4f6a9b71
Create Date: 2026-07-22 23:40:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f3a6c2d1e84"
down_revision: str | Sequence[str] | None = "8d2e4f6a9b71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "news_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("event_identifier", sa.String(length=240), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=True),
        sa.Column("publisher_entity_id", sa.String(length=36), nullable=True),
        sa.Column("related_entity_ids", sa.JSON(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("venue", sa.String(length=240), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('news', 'press_release', 'corporate_announcement', 'publication', "
            "'conference_abstract', 'poster', 'presentation', 'other')",
            name="ck_news_event_type",
        ),
        sa.ForeignKeyConstraint(["publisher_entity_id"], ["entities.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "event_identifier"),
    )
    for column in (
        "tenant_id",
        "event_identifier",
        "event_type",
        "published_at",
        "language",
        "publisher_entity_id",
        "venue",
        "source_document_id",
    ):
        op.create_index(op.f(f"ix_news_events_{column}"), "news_events", [column])
    op.create_index("ix_news_event_published", "news_events", ["tenant_id", "published_at"])
    op.create_index(
        "ix_news_event_publisher",
        "news_events",
        ["tenant_id", "publisher_entity_id", "published_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        predicate = "tenant_id = public.app_current_tenant_id()"
        op.execute(sa.text('ALTER TABLE "news_events" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "news_events" FORCE ROW LEVEL SECURITY'))
        op.execute(
            sa.text(f'CREATE POLICY "tenant_isolation" ON "news_events" USING ({predicate}) WITH CHECK ({predicate})')
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('DROP POLICY IF EXISTS "tenant_isolation" ON "news_events"'))
        op.execute(sa.text('ALTER TABLE "news_events" DISABLE ROW LEVEL SECURITY'))
    op.drop_index("ix_news_event_publisher", table_name="news_events")
    op.drop_index("ix_news_event_published", table_name="news_events")
    for column in reversed(
        (
            "tenant_id",
            "event_identifier",
            "event_type",
            "published_at",
            "language",
            "publisher_entity_id",
            "venue",
            "source_document_id",
        )
    ):
        op.drop_index(op.f(f"ix_news_events_{column}"), table_name="news_events")
    op.drop_table("news_events")
