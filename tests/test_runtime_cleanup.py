from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from pharma_intel.models import Entity, EntityType, Tenant
from pharma_intel.runtime_cleanup import cleanup_runtime_hygiene


def test_shared_tenant_fixture_cleanup_requires_the_privileged_browser_recovery_path(
    session: Session,
) -> None:
    tenant = Tenant(slug="default", name="Default")
    session.add(tenant)
    session.flush()
    entity = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.TARGET,
        name="Interrupted browser fixture",
        normalized_name="interrupted browser fixture",
        attributes={"acceptance_fixture": True},
    )
    session.add(entity)
    session.commit()

    with pytest.raises(RuntimeError, match="recover-interrupted-run"):
        cleanup_runtime_hygiene(lambda: session, backup_sha256="a" * 64)

    assert session.get(Entity, entity.id) is not None
