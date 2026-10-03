"""Publish only an explicitly marked synthetic Web/MCP acceptance entity."""

from __future__ import annotations

import argparse
import re
import uuid

from pharma_intel.db import get_session_factory, set_tenant_context
from pharma_intel.identity import EntityIdentityService
from pharma_intel.models import OutboxEvent, ReviewStatus
from pharma_intel.repository import EntityRepository


def publish_fixture(tenant_id: str, entity_id: str, marker: str) -> None:
    uuid.UUID(tenant_id)
    uuid.UUID(entity_id)
    if re.fullmatch(r"entry-[0-9a-f]{16}", marker) is None:
        raise ValueError("Invalid entry consistency fixture marker")
    with get_session_factory()() as session:
        set_tenant_context(session, tenant_id)
        entity = EntityRepository(session, tenant_id).get(entity_id)
        if (
            entity is None
            or entity.attributes.get("acceptance_fixture") is not True
            or entity.attributes.get("acceptance_fixture_kind") != "entry_consistency"
            or entity.attributes.get("acceptance_fixture_marker") != marker
        ):
            raise ValueError("Publication is restricted to the exact synthetic entry fixture")
        entity.review_status = ReviewStatus.VERIFIED
        EntityIdentityService(session, tenant_id).sync_identifiers(
            entity,
            entity.external_ids,
            review_status=ReviewStatus.VERIFIED,
            provenance={"origin": "entry_consistency_acceptance"},
        )
        session.add(
            OutboxEvent(
                tenant_id=tenant_id,
                aggregate_type="entity",
                aggregate_id=entity_id,
                event_type="canonical.entity.upserted",
                payload={"entity_id": entity_id, "schema_version": 1},
            )
        )
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--entity-id", required=True)
    parser.add_argument("--marker", required=True)
    args = parser.parse_args()
    publish_fixture(args.tenant_id, args.entity_id, args.marker)


if __name__ == "__main__":
    main()
