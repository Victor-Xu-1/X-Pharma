from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from pharma_intel.accounts.access import organization_administrator
from pharma_intel.accounts.identity import create_account
from pharma_intel.licensing import EvidenceLicensePolicy
from pharma_intel.models import (
    AuditEvent,
    DataSource,
    DataSourceState,
    OrganizationMembership,
    Tenant,
    TenantDataset,
    User,
    UserGroup,
    UserGroupMembership,
    UserRole,
    UserSession,
)
from pharma_intel.security import hash_password, normalize_email


class EnterpriseAdminError(RuntimeError):
    pass


class EnterpriseAdminNotFound(EnterpriseAdminError):
    pass


class EnterpriseAdminConflict(EnterpriseAdminError):
    pass


class EnterpriseAdminAccessDenied(EnterpriseAdminError):
    pass


@dataclass(frozen=True)
class CreateUserCommand:
    email: str
    display_name: str
    role: UserRole
    auth_mode: Literal["local", "oidc"]
    initial_password: str | None = None
    oidc_issuer: str | None = None
    oidc_subject: str | None = None


@dataclass(frozen=True)
class UpdateUserRoleCommand:
    expected_token_version: int
    role: UserRole
    reason: str


@dataclass(frozen=True)
class UpdateUserStatusCommand:
    expected_token_version: int
    active: bool
    reason: str


@dataclass(frozen=True)
class CreateGroupCommand:
    name: str
    description: str


@dataclass(frozen=True)
class UpdateGroupCommand:
    expected_version: int
    name: str
    description: str
    active: bool
    reason: str


@dataclass(frozen=True)
class UpdateGroupMembersCommand:
    expected_version: int
    user_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class UpdateDatasetStatusCommand:
    expected_version: int
    active: bool
    reason: str


@dataclass(frozen=True)
class SessionView:
    session: UserSession
    user: User


@dataclass(frozen=True)
class GroupView:
    group: UserGroup
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuditPage:
    items: tuple[AuditEvent, ...]
    next_cursor: str | None


class AuditCursorCodec:
    def __init__(self, secret: str, *, ttl_seconds: int = 900, max_chars: int = 4096) -> None:
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("Audit cursor signing secret must contain at least 32 bytes")
        self._secret = secret.encode("utf-8")
        self._ttl_seconds = ttl_seconds
        self._max_chars = max_chars

    def issue(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        filter_sha256: str,
        occurred_at: datetime,
        event_id: str,
        now_epoch: int | None = None,
    ) -> str:
        issued_at = int(time.time()) if now_epoch is None else now_epoch
        payload = {
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "filter_sha256": filter_sha256,
            "occurred_at": occurred_at.astimezone(UTC).isoformat(),
            "event_id": event_id,
            "expires_at": issued_at + self._ttl_seconds,
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self._secret, body, hashlib.sha256).digest()
        return f"{_encode(body)}.{_encode(signature)}"

    def verify(
        self,
        token: str,
        *,
        tenant_id: str,
        actor_id: str,
        filter_sha256: str,
        now_epoch: int | None = None,
    ) -> tuple[datetime, str]:
        try:
            if len(token) > self._max_chars:
                raise ValueError
            encoded_body, encoded_signature = token.split(".", 1)
            body = _decode(encoded_body)
            signature = _decode(encoded_signature)
            if not hmac.compare_digest(signature, hmac.new(self._secret, body, hashlib.sha256).digest()):
                raise ValueError
            payload = json.loads(body)
            if not isinstance(payload, dict) or set(payload) != {
                "tenant_id",
                "actor_id",
                "filter_sha256",
                "occurred_at",
                "event_id",
                "expires_at",
            }:
                raise ValueError
            expires_at = payload["expires_at"]
            if type(expires_at) is not int or expires_at <= (int(time.time()) if now_epoch is None else now_epoch):
                raise ValueError
            if (
                payload["tenant_id"] != tenant_id
                or payload["actor_id"] != actor_id
                or payload["filter_sha256"] != filter_sha256
                or not isinstance(payload["event_id"], str)
            ):
                raise ValueError
            occurred_at = datetime.fromisoformat(payload["occurred_at"])
            if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
                raise ValueError
            return occurred_at.astimezone(UTC), payload["event_id"]
        except (json.JSONDecodeError, TypeError, UnicodeError, ValueError) as exc:
            raise EnterpriseAdminConflict("Audit pagination cursor is invalid or expired") from exc


class EnterpriseAdminService:
    def __init__(
        self,
        session: Session,
        *,
        tenant_id: str,
        actor_id: str,
        request_id: str,
        cursor_codec: AuditCursorCodec,
    ) -> None:
        self._session = session
        self._tenant_id = tenant_id
        self._actor_id = actor_id
        self._request_id = request_id
        self._cursor_codec = cursor_codec

    def overview(self) -> dict[str, object]:
        tenant = self._session.scalar(select(Tenant).where(Tenant.id == self._tenant_id))
        if tenant is None:
            raise EnterpriseAdminNotFound("Tenant not found")
        since = datetime.now(UTC) - timedelta(hours=24)
        return {
            "tenant": tenant,
            "user_count": self._count(OrganizationMembership),
            "active_user_count": self._count(OrganizationMembership, OrganizationMembership.active.is_(True)),
            "admin_count": self._count(
                OrganizationMembership,
                OrganizationMembership.active.is_(True),
                OrganizationMembership.role == UserRole.ADMIN,
            ),
            "group_count": self._count(UserGroup),
            "active_group_count": self._count(UserGroup, UserGroup.active.is_(True)),
            "dataset_count": self._count(TenantDataset, TenantDataset.active.is_(True)),
            "active_source_count": self._count(DataSource, DataSource.state == DataSourceState.ACTIVE),
            "audit_event_count_24h": self._count(AuditEvent, AuditEvent.occurred_at >= since),
        }

    def list_users(self) -> list[OrganizationMembership]:
        return list(
            self._session.scalars(
                select(OrganizationMembership)
                .join(User, User.id == OrganizationMembership.user_id)
                .where(OrganizationMembership.tenant_id == self._tenant_id)
                .options(joinedload(OrganizationMembership.account))
                .order_by(User.normalized_email, User.id)
            )
        )

    def create_user(self, command: CreateUserCommand) -> OrganizationMembership:
        self._lock_tenant()
        email = command.email.strip()
        normalized_email = normalize_email(email)
        if self._session.scalar(select(User.id).where(User.normalized_email == normalized_email)) is not None:
            raise EnterpriseAdminConflict("An account with this identity already exists")
        if command.auth_mode == "local":
            if command.initial_password is None or command.oidc_issuer is not None or command.oidc_subject is not None:
                raise EnterpriseAdminConflict("Local accounts require only an initial password")
            password_hash = hash_password(command.initial_password)
            oidc_issuer = None
            oidc_subject = None
        else:
            if command.initial_password is not None or not command.oidc_issuer or not command.oidc_subject:
                raise EnterpriseAdminConflict("OIDC accounts require an issuer and subject")
            password_hash = hash_password(secrets.token_urlsafe(48))
            oidc_issuer = command.oidc_issuer.strip()
            oidc_subject = command.oidc_subject.strip()
            if (
                self._session.scalar(
                    select(User.id).where(User.oidc_issuer == oidc_issuer, User.oidc_subject == oidc_subject)
                )
                is not None
            ):
                raise EnterpriseAdminConflict("An account with this identity already exists")
        user = create_account(
            tenant_id=self._tenant_id,
            email=email,
            normalized_email=normalized_email,
            display_name=command.display_name.strip(),
            password_hash=password_hash,
            role=command.role,
            oidc_issuer=oidc_issuer,
            oidc_subject=oidc_subject,
        )
        self._session.add(user)
        self._session.flush()
        self._record(
            action="enterprise.user.created",
            resource_type="user",
            resource_id=user.id,
            details={"role": command.role.value, "auth_mode": command.auth_mode},
        )
        self._session.commit()
        self._session.refresh(user)
        return user.memberships[0]

    def update_user_role(self, user_id: str, command: UpdateUserRoleCommand) -> OrganizationMembership:
        self._lock_tenant()
        user = self._locked_user(user_id)
        self._assert_user_mutation(user, command.expected_token_version)
        previous_role = user.role
        if previous_role == command.role:
            raise EnterpriseAdminConflict("User already has the requested role")
        if previous_role == UserRole.ADMIN:
            self._assert_admin_remains()
        user.role = command.role
        user.token_version += 1
        self._revoke_user_sessions(user.id, "Role changed")
        self._record(
            action="enterprise.user.role_changed",
            resource_type="user",
            resource_id=user.id,
            details={"from": previous_role.value, "to": command.role.value, "reason": command.reason.strip()},
        )
        self._session.commit()
        self._session.refresh(user)
        return user

    def update_user_status(self, user_id: str, command: UpdateUserStatusCommand) -> OrganizationMembership:
        self._lock_tenant()
        user = self._locked_user(user_id)
        self._assert_user_mutation(user, command.expected_token_version)
        if user.active == command.active:
            raise EnterpriseAdminConflict("User already has the requested status")
        if user.role == UserRole.ADMIN and user.active and not command.active:
            self._assert_admin_remains()
        previous = user.active
        user.active = command.active
        user.token_version += 1
        self._revoke_user_sessions(user.id, "Account status changed")
        self._record(
            action="enterprise.user.status_changed",
            resource_type="user",
            resource_id=user.id,
            details={"from": previous, "to": command.active, "reason": command.reason.strip()},
        )
        self._session.commit()
        self._session.refresh(user)
        return user

    def list_groups(self) -> list[GroupView]:
        groups = list(
            self._session.scalars(
                select(UserGroup)
                .where(UserGroup.tenant_id == self._tenant_id)
                .order_by(UserGroup.normalized_name, UserGroup.id)
            )
        )
        memberships = self._session.execute(
            select(UserGroupMembership.group_id, UserGroupMembership.user_id).where(
                UserGroupMembership.tenant_id == self._tenant_id
            )
        ).all()
        members_by_group: dict[str, list[str]] = {group.id: [] for group in groups}
        for group_id, user_id in memberships:
            members_by_group.setdefault(group_id, []).append(user_id)
        return [GroupView(group, tuple(sorted(members_by_group[group.id]))) for group in groups]

    def create_group(self, command: CreateGroupCommand) -> GroupView:
        self._lock_tenant()
        name = command.name.strip()
        normalized_name = name.casefold()
        if (
            self._session.scalar(
                select(UserGroup.id).where(
                    UserGroup.tenant_id == self._tenant_id,
                    UserGroup.normalized_name == normalized_name,
                )
            )
            is not None
        ):
            raise EnterpriseAdminConflict("A group with this name already exists")
        group = UserGroup(
            tenant_id=self._tenant_id,
            name=name,
            normalized_name=normalized_name,
            description=command.description.strip(),
        )
        self._session.add(group)
        self._session.flush()
        self._record("enterprise.group.created", "user_group", group.id, {"name": group.name})
        self._session.commit()
        self._session.refresh(group)
        return GroupView(group, ())

    def update_group(self, group_id: str, command: UpdateGroupCommand) -> GroupView:
        self._lock_tenant()
        group = self._locked_group(group_id)
        if group.version != command.expected_version:
            raise EnterpriseAdminConflict("Group changed; refresh before retrying")
        name = command.name.strip()
        normalized_name = name.casefold()
        duplicate = self._session.scalar(
            select(UserGroup.id).where(
                UserGroup.tenant_id == self._tenant_id,
                UserGroup.normalized_name == normalized_name,
                UserGroup.id != group.id,
            )
        )
        if duplicate is not None:
            raise EnterpriseAdminConflict("A group with this name already exists")
        previous = {"name": group.name, "description": group.description, "active": group.active}
        group.name = name
        group.normalized_name = normalized_name
        group.description = command.description.strip()
        group.active = command.active
        group.version += 1
        self._record(
            "enterprise.group.updated",
            "user_group",
            group.id,
            {
                "from": previous,
                "to": {"name": group.name, "description": group.description, "active": group.active},
                "reason": command.reason.strip(),
            },
        )
        self._session.commit()
        self._session.refresh(group)
        member_ids = tuple(
            self._session.scalars(
                select(UserGroupMembership.user_id).where(
                    UserGroupMembership.tenant_id == self._tenant_id,
                    UserGroupMembership.group_id == group.id,
                )
            )
        )
        return GroupView(group, tuple(sorted(member_ids)))

    def update_group_members(self, group_id: str, command: UpdateGroupMembersCommand) -> GroupView:
        self._lock_tenant()
        group = self._locked_group(group_id)
        if group.version != command.expected_version:
            raise EnterpriseAdminConflict("Group changed; refresh before retrying")
        requested = tuple(sorted(set(command.user_ids)))
        if len(requested) != len(command.user_ids):
            raise EnterpriseAdminConflict("Group member list contains duplicates")
        users = (
            list(
                self._session.scalars(
                    select(User).where(
                        User.id.in_(requested),
                        User.active.is_(True),
                        User.id.in_(
                            select(OrganizationMembership.user_id).where(
                                OrganizationMembership.tenant_id == self._tenant_id,
                                OrganizationMembership.active.is_(True),
                            )
                        ),
                    )
                )
            )
            if requested
            else []
        )
        if {user.id for user in users} != set(requested):
            raise EnterpriseAdminConflict("Group members must be active users in this tenant")
        previous = tuple(
            sorted(
                self._session.scalars(
                    select(UserGroupMembership.user_id).where(
                        UserGroupMembership.tenant_id == self._tenant_id,
                        UserGroupMembership.group_id == group.id,
                    )
                )
            )
        )
        self._session.execute(
            delete(UserGroupMembership).where(
                UserGroupMembership.tenant_id == self._tenant_id,
                UserGroupMembership.group_id == group.id,
            )
        )
        self._session.add_all(
            [
                UserGroupMembership(tenant_id=self._tenant_id, group_id=group.id, user_id=user_id)
                for user_id in requested
            ]
        )
        group.version += 1
        self._record(
            "enterprise.group.members_changed",
            "user_group",
            group.id,
            {"from": list(previous), "to": list(requested), "reason": command.reason.strip()},
        )
        self._session.commit()
        self._session.refresh(group)
        return GroupView(group, requested)

    def list_datasets(self) -> list[TenantDataset]:
        return list(
            self._session.scalars(
                select(TenantDataset)
                .where(TenantDataset.tenant_id == self._tenant_id)
                .order_by(TenantDataset.display_name, TenantDataset.id)
            )
        )

    def update_dataset_status(self, dataset_id: str, command: UpdateDatasetStatusCommand) -> TenantDataset:
        self._lock_tenant()
        dataset = self._session.scalar(
            select(TenantDataset)
            .where(TenantDataset.tenant_id == self._tenant_id, TenantDataset.id == dataset_id)
            .with_for_update()
        )
        if dataset is None:
            raise EnterpriseAdminNotFound("Dataset not found")
        if dataset.version != command.expected_version:
            raise EnterpriseAdminConflict("Dataset changed; refresh before retrying")
        if dataset.active == command.active:
            raise EnterpriseAdminConflict("Dataset already has the requested status")
        if command.active:
            try:
                policy = EvidenceLicensePolicy.model_validate(dataset.license_policy)
            except ValueError as exc:
                raise EnterpriseAdminConflict("Dataset license policy is invalid") from exc
            now = datetime.now(UTC)
            if not policy.permits("web", now) and not policy.permits("mcp", now):
                raise EnterpriseAdminConflict("Dataset license is not currently valid for web or MCP delivery")
        active_sources = self._count(
            DataSource,
            DataSource.dataset_key == dataset.dataset_key,
            DataSource.state == DataSourceState.ACTIVE,
        )
        previous = dataset.active
        dataset.active = command.active
        dataset.version += 1
        self._record(
            "enterprise.dataset.status_changed",
            "tenant_dataset",
            dataset.id,
            {
                "from": previous,
                "to": dataset.active,
                "active_source_count": active_sources,
                "reason": command.reason.strip(),
            },
        )
        self._session.commit()
        self._session.refresh(dataset)
        return dataset

    def list_sessions(self, *, limit: int = 500) -> list[SessionView]:
        rows = self._session.execute(
            select(UserSession, User)
            .join(User, User.id == UserSession.user_id)
            .where(UserSession.tenant_id == self._tenant_id)
            .order_by(UserSession.issued_at.desc(), UserSession.id.desc())
            .limit(limit)
        ).all()
        return [SessionView(user_session, user) for user_session, user in rows]

    def revoke_session(self, session_id: str, *, reason: str) -> SessionView:
        self._lock_tenant()
        target = self._session.scalar(
            select(UserSession)
            .where(UserSession.tenant_id == self._tenant_id, UserSession.id == session_id)
            .with_for_update()
        )
        if target is None:
            raise EnterpriseAdminNotFound("Session not found")
        user = self._session.get(User, target.user_id)
        if user is None:
            raise EnterpriseAdminNotFound("Session user not found")
        if target.revoked_at is not None:
            return SessionView(target, user)
        target.revoked_at = datetime.now(UTC)
        target.revoked_by_user_id = self._actor_id
        target.revoke_reason = reason.strip()
        self._record(
            "enterprise.session.revoked",
            "user_session",
            target.id,
            {"user_id": target.user_id, "reason": target.revoke_reason},
        )
        self._session.commit()
        self._session.refresh(target)
        return SessionView(target, user)

    def list_audit_events(
        self,
        *,
        limit: int,
        cursor: str | None,
        action: str | None,
        outcome: str | None,
        actor_type: str | None,
    ) -> AuditPage:
        filters = {"action": action or "", "outcome": outcome or "", "actor_type": actor_type or "", "limit": limit}
        filter_sha256 = hashlib.sha256(json.dumps(filters, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        query = select(AuditEvent).where(AuditEvent.tenant_id == self._tenant_id)
        if action:
            query = query.where(AuditEvent.action == action)
        if outcome:
            query = query.where(AuditEvent.outcome == outcome)
        if actor_type:
            query = query.where(AuditEvent.actor_type == actor_type)
        if cursor:
            occurred_at, event_id = self._cursor_codec.verify(
                cursor,
                tenant_id=self._tenant_id,
                actor_id=self._actor_id,
                filter_sha256=filter_sha256,
            )
            query = query.where(
                or_(
                    AuditEvent.occurred_at < occurred_at,
                    and_(AuditEvent.occurred_at == occurred_at, AuditEvent.id < event_id),
                )
            )
        events = list(
            self._session.scalars(query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit + 1))
        )
        has_more = len(events) > limit
        items = tuple(events[:limit])
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = self._cursor_codec.issue(
                tenant_id=self._tenant_id,
                actor_id=self._actor_id,
                filter_sha256=filter_sha256,
                occurred_at=last.occurred_at,
                event_id=last.id,
            )
        return AuditPage(items, next_cursor)

    def _count(self, model: type[Any], *conditions: Any) -> int:
        return int(
            self._session.scalar(
                select(func.count()).select_from(model).where(model.tenant_id == self._tenant_id, *conditions)
            )
            or 0
        )

    def _lock_tenant(self) -> Tenant:
        tenant = self._session.scalar(select(Tenant).where(Tenant.id == self._tenant_id).with_for_update())
        if tenant is None or not tenant.active:
            raise EnterpriseAdminNotFound("Active tenant not found")
        actor = organization_administrator(self._session, self._tenant_id, self._actor_id)
        if actor is None:
            raise EnterpriseAdminAccessDenied("An active organization administrator is required")
        return tenant

    def _locked_user(self, user_id: str) -> OrganizationMembership:
        user = self._session.scalar(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.tenant_id == self._tenant_id,
                OrganizationMembership.user_id == user_id,
            )
            .with_for_update()
        )
        if user is None:
            raise EnterpriseAdminNotFound("User not found")
        return user

    def _locked_group(self, group_id: str) -> UserGroup:
        group = self._session.scalar(
            select(UserGroup).where(UserGroup.tenant_id == self._tenant_id, UserGroup.id == group_id).with_for_update()
        )
        if group is None:
            raise EnterpriseAdminNotFound("User group not found")
        return group

    def _assert_user_mutation(self, user: OrganizationMembership, expected_token_version: int) -> None:
        if user.id == self._actor_id:
            raise EnterpriseAdminConflict("Administrators cannot change their own role or status")
        if user.token_version != expected_token_version:
            raise EnterpriseAdminConflict("User changed; refresh before retrying")

    def _assert_admin_remains(self) -> None:
        active_admins = self._count(
            OrganizationMembership,
            OrganizationMembership.active.is_(True),
            OrganizationMembership.role == UserRole.ADMIN,
        )
        if active_admins <= 1:
            raise EnterpriseAdminConflict("At least one active administrator must remain")

    def _revoke_user_sessions(self, user_id: str, reason: str) -> None:
        now = datetime.now(UTC)
        self._session.execute(
            update(UserSession)
            .where(
                UserSession.tenant_id == self._tenant_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, revoked_by_user_id=self._actor_id, revoke_reason=reason)
        )

    def _record(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, object],
    ) -> None:
        self._session.add(
            AuditEvent(
                tenant_id=self._tenant_id,
                actor_type="user",
                actor_id=self._actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                request_id=self._request_id,
                details=details,
            )
        )


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    decoded = base64.b64decode(value + padding, altchars=b"-_", validate=True)
    if _encode(decoded) != value:
        raise ValueError("Non-canonical Base64URL value")
    return decoded
