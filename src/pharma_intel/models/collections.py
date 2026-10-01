from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid
from .enums import SavedSearchVisibility


class ComparisonSet(Base, TimestampMixin):
    __tablename__ = "comparison_sets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "owner_user_id", "name"),
        CheckConstraint("version > 0", name="ck_comparison_set_version_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    visibility: Mapped[SavedSearchVisibility] = mapped_column(
        String(20), default=SavedSearchVisibility.PRIVATE, index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class ComparisonSetMember(Base):
    __tablename__ = "comparison_set_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "comparison_set_id", "entity_id"),
        UniqueConstraint("tenant_id", "comparison_set_id", "position"),
        CheckConstraint("position >= 0", name="ck_comparison_set_member_position"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    comparison_set_id: Mapped[str] = mapped_column(ForeignKey("comparison_sets.id"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)
    added_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )


class ComparisonSetVersion(Base):
    __tablename__ = "comparison_set_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "comparison_set_id", "version"),
        CheckConstraint("version > 0", name="ck_comparison_set_history_version_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    comparison_set_id: Mapped[str] = mapped_column(ForeignKey("comparison_sets.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True, nullable=False
    )
