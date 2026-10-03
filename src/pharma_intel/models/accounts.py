from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid
from .enums import UserRole
from .tenancy import Tenant


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_users_oidc_identity"),
        CheckConstraint(
            "(oidc_issuer IS NULL) = (oidc_subject IS NULL)",
            name="ck_users_oidc_identity_complete",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    home_tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    # This preference is not a permission. The relationship also establishes the
    # insert dependency when a new organization and identity share a transaction.
    home_organization: Mapped[Tenant] = relationship(foreign_keys=[home_tenant_id])
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    oidc_issuer: Mapped[str | None] = mapped_column(String(500), index=True)
    oidc_subject: Mapped[str | None] = mapped_column(String(500), index=True)
    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class OrganizationMembership(Base, TimestampMixin):
    """The only authority for an account's role and status in an organization."""

    __tablename__ = "organization_memberships"
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER, index=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(default=1, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    account: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Tenant] = relationship()

    @property
    def organization_name(self) -> str:
        return self.organization.name

    @property
    def id(self) -> str:
        return self.user_id

    @property
    def email(self) -> str:
        return self.account.email

    @property
    def normalized_email(self) -> str:
        return self.account.normalized_email

    @property
    def display_name(self) -> str:
        return self.account.display_name

    @property
    def phone(self) -> str | None:
        return self.account.phone

    @property
    def avatar_url(self) -> str | None:
        return self.account.avatar_url

    @property
    def oidc_issuer(self) -> str | None:
        return self.account.oidc_issuer


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["organization_memberships.tenant_id", "organization_memberships.user_id"],
            name="fk_user_sessions_membership",
        ),
        CheckConstraint("expires_at > issued_at", name="ck_user_session_expiry"),
        Index("ix_user_sessions_tenant_user_expiry", "tenant_id", "user_id", "expires_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    user_agent_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(500))


class AccountInvitation(Base, TimestampMixin):
    """Tenant-scoped invitations; signed codes establish the pre-auth tenant context."""

    __tablename__ = "account_invitations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["organization_memberships.tenant_id", "organization_memberships.user_id"],
            name="fk_account_invitation_sponsor_membership",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "claimed_user_id"],
            ["organization_memberships.tenant_id", "organization_memberships.user_id"],
            name="fk_account_invitation_claim_membership",
        ),
        CheckConstraint("expires_at > created_at", name="ck_account_invitation_expiry"),
        CheckConstraint(
            "(claimed_at IS NULL) = (claimed_user_id IS NULL)", name="ck_account_invitation_claim_complete"
        ),
        Index("ix_account_invitation_tenant_created", "tenant_id", "created_at"),
        Index(
            "uq_account_invitation_pending",
            "tenant_id",
            "normalized_email",
            unique=True,
            postgresql_where=text("claimed_at IS NULL AND revoked_at IS NULL"),
            sqlite_where=text("claimed_at IS NULL AND revoked_at IS NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_user_id: Mapped[str | None] = mapped_column(String(36))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AccountRegistrationBudget(Base):
    __tablename__ = "account_registration_budgets"
    __table_args__ = (CheckConstraint("attempts > 0", name="ck_account_registration_attempts"),)
    peer_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(nullable=False)


class UserGroup(Base, TimestampMixin):
    __tablename__ = "user_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_user_groups_tenant_id_id"),
        UniqueConstraint("tenant_id", "normalized_name", name="uq_user_groups_tenant_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class UserGroupMembership(Base):
    __tablename__ = "user_group_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "group_id"],
            ["user_groups.tenant_id", "user_groups.id"],
            name="fk_user_group_memberships_tenant_group",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "user_id"],
            ["organization_memberships.tenant_id", "organization_memberships.user_id"],
            name="fk_user_group_memberships_tenant_user",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "group_id", "user_id", name="uq_user_group_membership"),
        Index("ix_user_group_memberships_tenant_group", "tenant_id", "group_id"),
        Index("ix_user_group_memberships_tenant_user", "tenant_id", "user_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    group_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
