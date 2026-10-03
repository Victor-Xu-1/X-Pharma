from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.models.accounts import OrganizationMembership, User
from pharma_intel.models.enums import UserRole
from pharma_intel.models.tenancy import Tenant


def organization_administrator(session: Session, tenant_id: str, user_id: str) -> OrganizationMembership | None:
    """Read live organization authority; caller must already establish trusted RLS context."""
    return session.scalar(
        select(OrganizationMembership)
        .join(User, User.id == OrganizationMembership.user_id)
        .join(Tenant, Tenant.id == OrganizationMembership.tenant_id)
        .where(
            OrganizationMembership.tenant_id == tenant_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.active.is_(True),
            OrganizationMembership.role == UserRole.ADMIN,
            User.active.is_(True),
            Tenant.active.is_(True),
        )
        .execution_options(populate_existing=True)
    )
