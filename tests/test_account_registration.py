from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.accounts.contracts import InvitationCreate, RegistrationRequest
from pharma_intel.accounts.invitation_codes import verify_invitation_code
from pharma_intel.accounts.registration_budget import RegistrationRateExceeded, consume_registration_budget
from pharma_intel.accounts.service import (
    AccountAccessDenied,
    AccountConflict,
    AccountNotFound,
    AccountRegistrationService,
)
from pharma_intel.config import get_settings
from pharma_intel.models import AccountInvitation, AccountRegistrationBudget, Tenant, User, UserRole
from pharma_intel.security import Principal, hash_password, verify_password

PASSWORD = "account-fixture-not-a-real-password"  # noqa: S105


@pytest.fixture(autouse=True)
def registration_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HUMAN_AUTH_MODE", "local")
    monkeypatch.setenv("HUMAN_SELF_REGISTRATION_ENABLED", "true")
    get_settings.cache_clear()


def _payload(email: str, *, workbench: str = "research", code: str | None = None) -> RegistrationRequest:
    return RegistrationRequest.model_validate(
        {
            "email": email,
            "display_name": "Registered User",
            "password": PASSWORD,
            "workbench": workbench,
            "invitation_code": code,
        }
    )


def _admin(session: Session, tenant: Tenant) -> Principal:
    actor = User(
        tenant_id=tenant.id,
        email="admin@example.test",
        normalized_email="admin@example.test",
        display_name="Admin",
        role=UserRole.ADMIN,
        password_hash=hash_password(PASSWORD),
    )
    session.add(actor)
    session.commit()
    return Principal(tenant.id, actor.id, "user", frozenset())


def test_independent_registration_is_isolated_and_never_grants_internal_admin(session: Session, tenant: Tenant) -> None:
    user = AccountRegistrationService(session, "test-registration").register(_payload("new@example.test"))
    assert user.tenant_id != tenant.id
    assert user.role == UserRole.VIEWER
    assert verify_password(PASSWORD, user.password_hash)
    assert user.password_hash != PASSWORD
    assert session.scalar(select(func.count()).select_from(Tenant)) == 2


def test_duplicate_registration_does_not_create_an_orphan_tenant(session: Session) -> None:
    service = AccountRegistrationService(session, "test-registration")
    service.register(_payload("new@example.test"))
    with pytest.raises(AccountConflict):
        service.register(_payload("NEW@example.test"))
    assert session.scalar(select(func.count()).select_from(User)) == 1
    assert session.scalar(select(func.count()).select_from(Tenant)) == 1


def test_password_hasher_failure_rolls_back_a_new_independent_space(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unavailable(_password: str) -> str:
        raise RuntimeError("Controlled password hasher failure")

    monkeypatch.setattr("pharma_intel.accounts.service.hash_password", unavailable)
    with pytest.raises(RuntimeError, match="Controlled password hasher failure"):
        AccountRegistrationService(session, "failed-registration").register(_payload("new@example.test"))
    assert session.scalar(select(func.count()).select_from(User)) == 0
    assert session.scalar(select(func.count()).select_from(Tenant)) == 0


def test_internal_invitation_is_email_bound_single_use_and_only_stores_a_digest(
    session: Session, tenant: Tenant
) -> None:
    actor = _admin(session, tenant)
    service = AccountRegistrationService(session, "test-invitation")
    issued = service.issue_invitation(actor, InvitationCreate(email="employee@example.test"))
    row = session.get(AccountInvitation, issued.invitation.id)
    assert row is not None and row.token_digest != issued.code
    assert verify_invitation_code(issued.code).tenant_id == tenant.id
    with pytest.raises(AccountAccessDenied):
        service.register(_payload("other@example.test", workbench="internal", code=issued.code))
    member = service.register(_payload("employee@example.test", workbench="internal", code=issued.code))
    assert member.tenant_id == tenant.id and member.role == UserRole.ANALYST
    with pytest.raises(AccountAccessDenied):
        service.issue_invitation(
            Principal(tenant.id, member.id, "user", frozenset()), InvitationCreate(email="new-member@example.test")
        )
    session.refresh(row)
    assert row.claimed_at is not None and row.claimed_user_id == member.id
    with pytest.raises(AccountConflict):
        service.register(_payload("employee@example.test", workbench="internal", code=issued.code))


@pytest.mark.parametrize("failure", ["revoked", "expired", "tampered", "sponsor_inactive"])
def test_unusable_invitation_cannot_create_a_user(session: Session, tenant: Tenant, failure: str) -> None:
    actor = _admin(session, tenant)
    service = AccountRegistrationService(session, "test-invitation")
    issued = service.issue_invitation(actor, InvitationCreate(email="employee@example.test"))
    row = session.get(AccountInvitation, issued.invitation.id)
    assert row is not None
    code = issued.code
    if failure == "revoked":
        service.revoke_invitation(actor, row.id)
    elif failure == "expired":
        row.created_at = datetime.now(UTC) - timedelta(days=2)
        row.expires_at = datetime.now(UTC) - timedelta(days=1)
        session.commit()
    elif failure == "tampered":
        code = code[:-1] + ("a" if code[-1] != "a" else "b")
    else:
        sponsor = session.get(User, actor.user_id)
        assert sponsor is not None
        sponsor.active = False
        session.commit()
    with pytest.raises(AccountAccessDenied):
        service.register(_payload("employee@example.test", workbench="internal", code=code))
    assert session.scalar(select(func.count()).select_from(User)) == 1


def test_invitation_management_enforces_the_actor_and_tenant(session: Session, tenant: Tenant) -> None:
    actor = _admin(session, tenant)
    service = AccountRegistrationService(session, "test-invitation")
    issued = service.issue_invitation(actor, InvitationCreate(email="employee@example.test"))
    with pytest.raises(AccountAccessDenied):
        service.list_invitations(Principal(tenant.id, "not-an-admin", "user", frozenset()))
    other_tenant = Tenant(slug="other", name="Other")
    session.add(other_tenant)
    session.commit()
    outsider = User(
        tenant_id=other_tenant.id,
        email="other-admin@example.test",
        normalized_email="other-admin@example.test",
        display_name="Other",
        role=UserRole.ADMIN,
        password_hash=hash_password(PASSWORD),
    )
    session.add(outsider)
    session.commit()
    other = Principal(other_tenant.id, outsider.id, "user", frozenset())
    assert service.list_invitations(other) == []
    with pytest.raises(AccountNotFound):
        service.revoke_invitation(other, issued.invitation.id)


def test_registration_attempt_budget_is_persistent_and_bounded(session: Session) -> None:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    for _ in range(10):
        consume_registration_budget(session, "test-peer", now=now)
    with pytest.raises(RegistrationRateExceeded):
        consume_registration_budget(session, "test-peer", now=now)
    row = session.scalar(select(AccountRegistrationBudget))
    assert row is not None and row.attempts == 11 and "test-peer" not in row.peer_digest
    consume_registration_budget(session, "test-peer", now=now + timedelta(minutes=10))
    session.refresh(row)
    assert row.attempts == 1


@pytest.mark.parametrize("policy", ["closed", "oidc"])
def test_registration_never_bypasses_a_closed_or_organization_identity_policy(
    session: Session, monkeypatch: pytest.MonkeyPatch, policy: str
) -> None:
    if policy == "closed":
        monkeypatch.setenv("HUMAN_SELF_REGISTRATION_ENABLED", "false")
    else:
        monkeypatch.setenv("HUMAN_AUTH_MODE", "oidc")
    get_settings.cache_clear()
    with pytest.raises(AccountAccessDenied):
        AccountRegistrationService(session, "closed-account-policy").register(_payload("new@example.test"))
    assert session.scalar(select(func.count()).select_from(User)) == 0
    assert session.scalar(select(func.count()).select_from(Tenant)) == 0
