from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel import entry_consistency_fixture
from pharma_intel.models import Entity, EntityType, OutboxEvent, ReviewStatus, Tenant
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate


def test_publication_is_limited_to_the_exact_synthetic_marker(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(
            entity_type=EntityType.TARGET,
            name="Entry acceptance synthetic target",
            attributes={
                "acceptance_fixture": True,
                "acceptance_fixture_kind": "entry_consistency",
                "acceptance_fixture_marker": "entry-0123456789abcdef",
            },
        )
    )
    monkeypatch.setattr(entry_consistency_fixture, "get_session_factory", lambda: lambda: session)
    before = len(list(session.scalars(select(OutboxEvent))))
    entry_consistency_fixture.publish_fixture(tenant.id, entity.id, "entry-0123456789abcdef")
    published = session.get(Entity, entity.id)
    assert published is not None and published.review_status == ReviewStatus.VERIFIED
    assert len(list(session.scalars(select(OutboxEvent)))) == before + 1


@pytest.mark.parametrize(
    "attributes",
    [
        {},
        {
            "acceptance_fixture": True,
            "acceptance_fixture_kind": "entry_consistency",
            "acceptance_fixture_marker": "entry-fedcba9876543210",
        },
    ],
)
def test_publication_refuses_regular_entities_and_mismatched_markers(
    session: Session,
    tenant: Tenant,
    monkeypatch: pytest.MonkeyPatch,
    attributes: dict[str, object],
) -> None:
    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(
            entity_type=EntityType.TARGET,
            name=f"Protected target {uuid.uuid4()}",
            attributes=attributes,
        )
    )
    monkeypatch.setattr(entry_consistency_fixture, "get_session_factory", lambda: lambda: session)
    with pytest.raises(ValueError, match="exact synthetic"):
        entry_consistency_fixture.publish_fixture(tenant.id, entity.id, "entry-0123456789abcdef")
    protected = session.get(Entity, entity.id)
    assert protected is not None and protected.review_status == ReviewStatus.DRAFT
