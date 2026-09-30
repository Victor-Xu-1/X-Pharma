from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pharma_intel.accounts.contracts import InvitationCreate, InvitationIssued, InvitationRead, RegistrationRequest
from pharma_intel.accounts.invitation_codes import issue_invitation_code, verify_invitation_code
from pharma_intel.config import get_settings
from pharma_intel.db import set_tenant_context
from pharma_intel.models import AccountInvitation, AuditEvent, Tenant, User, UserRole, new_uuid
from pharma_intel.security import Principal, hash_password, normalize_email


class AccountAccessDenied(RuntimeError):
    pass


class AccountConflict(RuntimeError):
    pass


class AccountNotFound(RuntimeError):
    pass


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AccountRegistrationService:
    def __init__(self, session: Session, request_id: str) -> None:
        self.session = session
        self.request_id = request_id

    def register(self, payload: RegistrationRequest) -> User:
        try:
            return self._register(payload)
        except IntegrityError as exc:
            self.session.rollback()
            raise AccountConflict("该邮箱无法用于新账号注册；已有账号请直接登录") from exc
        except Exception:
            self.session.rollback()
            raise

    def _register(self, payload: RegistrationRequest) -> User:
        settings = get_settings()
        if settings.human_auth_mode != "local":
            raise AccountAccessDenied("当前使用企业身份登录，请在组织身份系统申请账号")
        if payload.workbench == "research" and not settings.human_self_registration_enabled:
            raise AccountAccessDenied("独立账号注册未开放，请联系管理员")
        normalized = normalize_email(payload.email)
        if self.session.scalar(select(User.id).where(User.normalized_email == normalized)) is not None:
            raise AccountConflict("该邮箱无法用于新账号注册；已有账号请直接登录")
        now = datetime.now(UTC)
        invitation: AccountInvitation | None = None
        if payload.workbench == "internal":
            if payload.invitation_code is None:
                raise AccountAccessDenied("内部管理账号必须使用邀请码")
            try:
                verified = verify_invitation_code(payload.invitation_code.get_secret_value())
            except ValueError as exc:
                raise AccountAccessDenied("邀请码无效或已失效") from exc
            # A MAC-verified tenant is required before touching an RLS-protected invitation.
            set_tenant_context(self.session, verified.tenant_id)
            invitation = self.session.scalar(
                select(AccountInvitation)
                .where(
                    AccountInvitation.id == verified.invitation_id,
                    AccountInvitation.tenant_id == verified.tenant_id,
                    AccountInvitation.token_digest == verified.digest,
                )
                .with_for_update()
            )
            tenant = self.session.get(Tenant, verified.tenant_id)
            sponsor = self.session.get(User, invitation.created_by_user_id) if invitation is not None else None
            if (
                invitation is None
                or tenant is None
                or not tenant.active
                or invitation.normalized_email != normalized
                or invitation.claimed_at is not None
                or invitation.revoked_at is not None
                or _utc(invitation.expires_at) <= now
                or sponsor is None
                or not sponsor.active
                or sponsor.role != UserRole.ADMIN
            ):
                raise AccountAccessDenied("邀请码无效或已失效")
            tenant_id = verified.tenant_id
            role = UserRole.ANALYST
        else:
            tenant_id = new_uuid()
            self.session.add(
                Tenant(id=tenant_id, slug=f"personal-{new_uuid()}", name=f"{payload.display_name[:180]} · 独立空间")
            )
            self.session.flush()
            set_tenant_context(self.session, tenant_id)
            role = UserRole.VIEWER
        user = User(
            id=new_uuid(),
            tenant_id=tenant_id,
            email=payload.email,
            normalized_email=normalized,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password.get_secret_value()),
            role=role,
        )
        self.session.add(user)
        self.session.flush()
        if invitation is not None:
            claimed_at = datetime.now(UTC)
            claimed = self.session.scalar(
                update(AccountInvitation)
                .where(
                    AccountInvitation.id == invitation.id,
                    AccountInvitation.tenant_id == tenant_id,
                    AccountInvitation.claimed_at.is_(None),
                    AccountInvitation.revoked_at.is_(None),
                    AccountInvitation.expires_at > claimed_at,
                )
                .values(claimed_at=claimed_at, claimed_user_id=user.id)
                .returning(AccountInvitation.id)
                .execution_options(synchronize_session=False)
            )
            if claimed is None:
                raise AccountAccessDenied("邀请码无效或已失效")
        self._audit(
            tenant_id,
            user.id,
            "account.registered",
            "user",
            user.id,
            {"workbench": payload.workbench, "role": role.value},
        )
        self.session.commit()
        return user

    def issue_invitation(self, principal: Principal, payload: InvitationCreate) -> InvitationIssued:
        actor = self._administrator(principal)
        if get_settings().human_auth_mode != "local":
            raise AccountAccessDenied("企业身份模式的账号由组织身份系统管理")
        normalized = normalize_email(payload.email)
        if self.session.scalar(select(User.id).where(User.normalized_email == normalized)) is not None:
            raise AccountConflict("该邮箱已有账号；邀请码用于创建新的内部账号")
        now = datetime.now(UTC)
        pending = self.session.scalar(
            select(AccountInvitation.id).where(
                AccountInvitation.tenant_id == actor.tenant_id,
                AccountInvitation.normalized_email == normalized,
                AccountInvitation.claimed_at.is_(None),
                AccountInvitation.revoked_at.is_(None),
                AccountInvitation.expires_at > now,
            )
        )
        if pending is not None:
            raise AccountConflict("该邮箱已有有效邀请码；需要重新发放时请先撤销")
        self.session.execute(
            update(AccountInvitation)
            .where(
                AccountInvitation.tenant_id == actor.tenant_id,
                AccountInvitation.normalized_email == normalized,
                AccountInvitation.claimed_at.is_(None),
                AccountInvitation.revoked_at.is_(None),
                AccountInvitation.expires_at <= now,
            )
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        )
        identity = new_uuid()
        code = issue_invitation_code(actor.tenant_id, identity)
        item = AccountInvitation(
            id=identity,
            tenant_id=actor.tenant_id,
            created_by_user_id=actor.id,
            email=payload.email,
            normalized_email=normalized,
            token_digest=hashlib.sha256(code.encode("ascii")).hexdigest(),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(hours=payload.valid_hours),
        )
        self.session.add(item)
        self._audit(actor.tenant_id, actor.id, "account.invitation.issued", "account_invitation", identity, {})
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise AccountConflict("该邮箱已有有效邀请码；需要重新发放时请先撤销") from exc
        return InvitationIssued(invitation=InvitationRead.model_validate(item), code=code)

    def list_invitations(self, principal: Principal) -> list[InvitationRead]:
        actor = self._administrator(principal)
        rows = self.session.scalars(
            select(AccountInvitation)
            .where(AccountInvitation.tenant_id == actor.tenant_id)
            .order_by(AccountInvitation.created_at.desc())
            .limit(100)
        ).all()
        return [InvitationRead.model_validate(item) for item in rows]

    def revoke_invitation(self, principal: Principal, invitation_id: str) -> None:
        actor = self._administrator(principal)
        item = self.session.scalar(
            select(AccountInvitation)
            .where(AccountInvitation.id == invitation_id, AccountInvitation.tenant_id == actor.tenant_id)
            .with_for_update()
        )
        if item is None:
            raise AccountNotFound("邀请码不存在")
        if item.claimed_at is not None:
            raise AccountConflict("邀请码已使用，不能撤销；请在用户管理中处理账号")
        if item.revoked_at is None:
            item.revoked_at = datetime.now(UTC)
            self._audit(actor.tenant_id, actor.id, "account.invitation.revoked", "account_invitation", item.id, {})
            self.session.commit()

    def _administrator(self, principal: Principal) -> User:
        if principal.user_id is None:
            raise AccountAccessDenied("仅限已登录的管理员")
        set_tenant_context(self.session, principal.tenant_id)
        actor = self.session.scalar(
            select(User)
            .join(Tenant)
            .where(
                User.id == principal.user_id,
                User.tenant_id == principal.tenant_id,
                User.active.is_(True),
                User.role == UserRole.ADMIN,
                Tenant.active.is_(True),
            )
        )
        if actor is None:
            raise AccountAccessDenied("仅限管理员管理注册邀请码")
        return actor

    def _audit(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, object],
    ) -> None:
        self.session.add(
            AuditEvent(
                tenant_id=tenant_id,
                actor_type="user",
                actor_id=actor_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome="success",
                request_id=self.request_id,
                details=details,
            )
        )
