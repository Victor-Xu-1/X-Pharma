from __future__ import annotations

from sqlalchemy import case, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from pharma_intel.db import set_account_context
from pharma_intel.models.accounts import OrganizationMembership, User
from pharma_intel.models.tenancy import Tenant


def select_membership(
    session: Session, account: User, organization_id: str | None = None
) -> OrganizationMembership | None:
    """Choose one authorized organization, never create a membership on login."""
    set_account_context(session, account.id)
    query = (
        select(OrganizationMembership)
        .join(Tenant, Tenant.id == OrganizationMembership.tenant_id)
        .where(
            OrganizationMembership.user_id == account.id,
            OrganizationMembership.active.is_(True),
            Tenant.active.is_(True),
        )
        .options(joinedload(OrganizationMembership.account), contains_eager(OrganizationMembership.organization))
    )
    if organization_id is not None:
        query = query.where(OrganizationMembership.tenant_id == organization_id)
    return session.scalar(
        query.order_by(
            case((OrganizationMembership.tenant_id == account.home_tenant_id, 0), else_=1),
            OrganizationMembership.created_at,
            OrganizationMembership.tenant_id,
        ).limit(1)
    )
