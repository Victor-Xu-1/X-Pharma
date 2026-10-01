from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from pharma_intel.accounts.contracts import InvitationCreate, RegistrationRequest
from pharma_intel.accounts.identity import create_account
from pharma_intel.accounts.request_budget import AccountRateExceeded, consume_account_budget
from pharma_intel.accounts.service import AccountAccessDenied, AccountConflict, AccountRegistrationService
from pharma_intel.db import set_tenant_context
from pharma_intel.models import AccountInvitation, AccountRegistrationBudget, Tenant, User, UserRole
from pharma_intel.security import Principal

pytestmark = pytest.mark.integration


def _invitation(engine: Engine) -> tuple[str, str, str]:
    tenant_id = str(uuid4())
    email = f"employee-{uuid4()}@example.test"
    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, tenant_id)
        tenant = Tenant(id=tenant_id, slug=f"account-test-{tenant_id}", name="Disposable invitation test")
        session.add(tenant)
        session.flush()
        admin_email = f"admin-{uuid4()}@example.test"
        admin = create_account(
            tenant_id=tenant_id,
            email=admin_email,
            normalized_email=admin_email,
            display_name="Test administrator",
            role=UserRole.ADMIN,
            password_hash="not-a-login-account",  # noqa: S106  # No password can authenticate this fixture.
        )
        session.add(admin)
        session.commit()
        principal = Principal(tenant_id, admin.id, "user", frozenset())
        issued = AccountRegistrationService(session, "postgres-invitation-test").issue_invitation(
            principal,
            InvitationCreate(email=email),
        )
        return tenant_id, email, issued.code


def test_postgres_invitation_rls_rejects_unsigned_and_other_tenant_context(account_engine: Engine) -> None:
    tenant_id, _, _ = _invitation(account_engine)
    with Session(account_engine) as session:
        assert session.scalar(select(func.count()).select_from(AccountInvitation)) == 0
        session.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant, true), set_config('app.tenant_signature', 'forged', true)"
            ),
            {"tenant": tenant_id},
        )
        assert session.scalar(select(func.count()).select_from(AccountInvitation)) == 0
        set_tenant_context(session, str(uuid4()))
        assert session.scalar(select(func.count()).select_from(AccountInvitation)) == 0
        set_tenant_context(session, tenant_id)
        assert session.scalar(select(func.count()).select_from(AccountInvitation)) == 1


def test_postgres_only_one_concurrent_registration_can_claim_an_invitation(account_engine: Engine) -> None:
    tenant_id, email, code = _invitation(account_engine)
    start = threading.Barrier(2)
    payload = RegistrationRequest.model_validate(
        {
            "workbench": "internal",
            "email": email,
            "display_name": "Invited User",
            "password": "disposable-test-only-account-password",
            "invitation_code": code,
        }
    )

    def register() -> bool:
        with Session(account_engine, expire_on_commit=False) as session:
            start.wait(timeout=10)
            try:
                user = AccountRegistrationService(session, "postgres-concurrent-claim").register(payload)
                assert user.role == UserRole.ANALYST and user.tenant_id == tenant_id
                return True
            except (AccountAccessDenied, AccountConflict):
                session.rollback()
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: register(), range(2)))
    assert results.count(True) == 1
    with Session(account_engine) as session:
        set_tenant_context(session, tenant_id)
        assert session.scalar(select(func.count()).select_from(User).where(User.email == email)) == 1
        invitation = session.scalar(select(AccountInvitation))
        assert invitation is not None and invitation.claimed_at is not None
        assert invitation.claimed_user_id == session.scalar(select(User.id).where(User.email == email))


def test_postgres_registration_budget_is_atomic_across_connections(account_engine: Engine) -> None:
    peer = f"disposable-peer-{uuid4()}"
    now = datetime(2026, 10, 1, tzinfo=UTC)
    start = threading.Barrier(12)
    with Session(account_engine) as session:
        previous_peers = set(session.scalars(select(AccountRegistrationBudget.peer_digest)))

    def attempt() -> bool:
        with Session(account_engine) as session:
            start.wait(timeout=10)
            try:
                consume_account_budget(session, peer, now=now)
                return True
            except AccountRateExceeded:
                return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: attempt(), range(12)))
    assert results.count(True) == 10
    with Session(account_engine) as session:
        added = [
            row for row in session.scalars(select(AccountRegistrationBudget)) if row.peer_digest not in previous_peers
        ]
        assert len(added) == 1 and added[0].attempts == 12


def test_postgres_self_registration_persists_a_separate_viewer_space(account_engine: Engine) -> None:
    with Session(account_engine, expire_on_commit=False) as session:
        service = AccountRegistrationService(session, "postgres-independent-account")
        payload = RegistrationRequest.model_validate(
            {
                "workbench": "research",
                "email": f"independent-{uuid4()}@example.test",
                "display_name": "Independent User",
                "password": "disposable-test-only-account-password",
            }
        )
        user = service.register(payload)
        assert user.role == UserRole.VIEWER
        assert session.get(Tenant, user.tenant_id) is not None
        with pytest.raises(AccountAccessDenied):
            service.list_invitations(Principal(user.tenant_id, user.id, "user", frozenset()))
        identity = user.id
    with Session(account_engine) as session:
        persisted = session.get(User, identity)
        assert persisted is not None and persisted.normalized_email == payload.email
        set_tenant_context(session, persisted.home_tenant_id)
        assert persisted.memberships[0].role == UserRole.VIEWER
