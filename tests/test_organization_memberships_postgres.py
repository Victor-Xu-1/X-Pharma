from __future__ import annotations

import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from pharma_intel.accounts.contracts import InvitationCreate
from pharma_intel.accounts.identity import create_account
from pharma_intel.accounts.service import AccountAccessDenied, AccountConflict, AccountRegistrationService
from pharma_intel.config import get_settings
from pharma_intel.db import set_account_context, set_tenant_context
from pharma_intel.models import AccountInvitation, Entity, EntityType, OrganizationMembership, Tenant, User, UserRole
from pharma_intel.security import Principal, authenticate_user, hash_password

pytestmark = pytest.mark.integration


def _prepare(engine: Engine) -> tuple[str, str, str, str, str]:
    first_id, second_id = str(uuid4()), str(uuid4())
    password = secrets.token_urlsafe(24)
    account_email = f"organization-member-{uuid4()}@example.test"
    with Session(engine, expire_on_commit=False) as session:
        set_tenant_context(session, first_id)
        first = Tenant(id=first_id, slug=f"org-test-{first_id}", name="Disposable first organization")
        session.add(first)
        session.flush()
        account = create_account(
            tenant_id=first_id,
            email=account_email,
            normalized_email=account_email,
            display_name="Shared identity",
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
        session.add(account)
        session.add(
            Entity(
                tenant_id=first_id,
                entity_type=EntityType.TARGET,
                name="First isolated target",
                normalized_name="first isolated target",
            )
        )
        session.commit()
        account_id = account.id
        set_tenant_context(session, second_id)
        session.add(Tenant(id=second_id, slug=f"org-test-{second_id}", name="Disposable second organization"))
        session.flush()
        sponsor_email = f"organization-sponsor-{uuid4()}@example.test"
        sponsor = create_account(
            tenant_id=second_id,
            email=sponsor_email,
            normalized_email=sponsor_email,
            display_name="Sponsor",
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
        session.add(sponsor)
        session.add(
            Entity(
                tenant_id=second_id,
                entity_type=EntityType.TARGET,
                name="Second isolated target",
                normalized_name="second isolated target",
            )
        )
        session.commit()
        issued = AccountRegistrationService(session, "postgres-multi-org").issue_invitation(
            Principal(second_id, sponsor.id, "user", frozenset()),
            InvitationCreate(email=account_email),
        )
    return first_id, second_id, account_id, password, issued.code


def test_signed_account_catalog_does_not_grant_cross_organization_write_or_business_read(
    account_engine: Engine,
) -> None:
    first_id, second_id, account_id, password, code = _prepare(account_engine)
    with Session(account_engine) as session:
        account = session.get(User, account_id)
        assert account is not None
        verified = authenticate_user(session, account.email, password)
        assert verified is not None
        joined = AccountRegistrationService(session, "postgres-membership-join").accept_invitation(verified, code)
        assert joined.role == UserRole.ANALYST and verified.home_tenant_id == first_id
    with Session(account_engine) as session:
        assert session.scalar(select(func.count()).select_from(OrganizationMembership)) == 0
        assert session.scalar(select(func.count()).select_from(Entity)) == 0
        session.execute(
            text("SELECT set_config('app.account_id', :id, true), set_config('app.account_signature', 'forged', true)"),
            {"id": account_id},
        )
        assert session.scalar(select(func.count()).select_from(OrganizationMembership)) == 0
        set_account_context(session, account_id)
        assert {item.tenant_id for item in session.scalars(select(OrganizationMembership))} == {first_id, second_id}
        assert session.scalar(select(func.count()).select_from(Entity)) == 0
        set_tenant_context(session, first_id)
        assert [item.name for item in session.scalars(select(Entity))] == ["First isolated target"]
        changed = session.execute(
            update(OrganizationMembership)
            .where(
                OrganizationMembership.tenant_id == second_id,
                OrganizationMembership.user_id == account_id,
            )
            .values(role=UserRole.ADMIN)
        )
        assert changed.rowcount == 0
        candidate_email = f"rls-candidate-{uuid4()}@example.test"
        candidate = create_account(
            tenant_id=first_id,
            email=candidate_email,
            normalized_email=candidate_email,
            display_name="Valid foreign key candidate",
            password_hash=secrets.token_urlsafe(32),
        )
        session.add(candidate)
        session.flush()
        with pytest.raises(DBAPIError) as denied:
            session.add(OrganizationMembership(tenant_id=second_id, user_id=candidate.id, role=UserRole.ADMIN))
            session.flush()
        assert getattr(denied.value.orig, "sqlstate", None) == "42501"
        session.rollback()
        member = session.get(OrganizationMembership, (second_id, account_id))
        assert member is not None and member.role == UserRole.ANALYST


def test_only_one_concurrent_acceptance_can_join_an_existing_identity(account_engine: Engine) -> None:
    first_id, second_id, account_id, password, code = _prepare(account_engine)
    barrier = threading.Barrier(2)

    def accept() -> bool:
        with Session(account_engine) as session:
            account = session.get(User, account_id)
            assert account is not None
            verified = authenticate_user(session, account.email, password)
            assert verified is not None
            barrier.wait(timeout=10)
            try:
                AccountRegistrationService(session, "postgres-concurrent-membership").accept_invitation(verified, code)
                return True
            except (AccountAccessDenied, AccountConflict):
                return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(lambda _: accept(), range(2))).count(True) == 1
    with Session(account_engine) as session:
        set_tenant_context(session, second_id)
        assert (
            session.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.tenant_id == second_id,
                    OrganizationMembership.user_id == account_id,
                )
            )
            == 1
        )
        account = session.get(User, account_id)
        invitation = session.scalar(select(AccountInvitation).where(AccountInvitation.claimed_user_id == account_id))
        assert account is not None and account.home_tenant_id == first_id and account.token_version == 1
        assert invitation is not None and invitation.claimed_at is not None


def test_switching_account_and_tenant_context_reuses_the_explicit_session_signing_key(
    account_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_id, _, account_id, _, _ = _prepare(account_engine)
    signing_key = get_settings().effective_tenant_context_signing_secret
    monkeypatch.setenv("TENANT_CONTEXT_SIGNING_SECRET", secrets.token_urlsafe(48))
    get_settings.cache_clear()
    with Session(account_engine) as session:
        assert session.scalar(text("SELECT public.app_current_account_id()")) is None
        set_account_context(session, account_id, signing_secret=signing_key)
        assert session.scalar(text("SELECT public.app_current_account_id()")) == account_id
        set_tenant_context(session, first_id)
        assert session.scalar(text("SELECT public.app_current_tenant_id()")) == first_id
        session.commit()
        assert session.scalar(text("SELECT public.app_current_account_id()")) == account_id
        assert session.scalar(text("SELECT public.app_current_tenant_id()")) == first_id
