from __future__ import annotations

from pharma_intel.models.accounts import OrganizationMembership, User
from pharma_intel.models.base import new_uuid
from pharma_intel.models.enums import UserRole


def create_account(
    *,
    tenant_id: str,
    email: str,
    normalized_email: str,
    display_name: str,
    password_hash: str,
    role: UserRole = UserRole.VIEWER,
    active: bool = True,
    token_version: int = 1,
    id: str | None = None,
    phone: str | None = None,
    avatar_url: str | None = None,
    oidc_issuer: str | None = None,
    oidc_subject: str | None = None,
) -> User:
    """Create a new identity and its first membership atomically via ORM cascade.

    Existing identities must join through invitation acceptance, not this factory.
    Organization status belongs to the membership, never to the global account.
    """
    return User(
        id=id or new_uuid(),
        home_tenant_id=tenant_id,
        email=email,
        normalized_email=normalized_email,
        display_name=display_name,
        password_hash=password_hash,
        active=True,
        token_version=token_version,
        phone=phone,
        avatar_url=avatar_url,
        oidc_issuer=oidc_issuer,
        oidc_subject=oidc_subject,
        memberships=[
            OrganizationMembership(tenant_id=tenant_id, role=role, active=active, token_version=token_version)
        ],
    )
