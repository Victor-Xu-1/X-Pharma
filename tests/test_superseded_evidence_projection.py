from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pharma_intel.models import EvidenceClaim, GovernanceStatus, OutboxEvent, ReviewStatus, Tenant
from pharma_intel.search.client import OpenSearchGateway
from pharma_intel.search.documents import evidence_claim_projection
from pharma_intel.search.projector import ClaimedEvent, SearchProjectionConsumer
from pharma_intel.search.rebuild import SearchRebuilder
from tests.governance_revision_fixtures import published_official_revision
from tests.test_search_projection import RecordingGateway, _factory


def test_official_revision_retires_old_claims_without_deleting_the_audit_records(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    _, _, old_facts, new_facts = published_official_revision(session, tenant, tmp_path)
    old_claims = {fact.published_resource_id for fact in old_facts}
    assert all(fact.status == GovernanceStatus.WITHDRAWN for fact in old_facts)
    assert all(fact.status == GovernanceStatus.PUBLISHED for fact in new_facts)
    assert all(session.get(EvidenceClaim, claim_id) is not None for claim_id in old_claims)
    events = list(session.scalars(select(OutboxEvent).where(OutboxEvent.event_type == "governance.fact.withdrawn")))
    assert {event.payload["evidence_claim_id"] for event in events} == old_claims


@pytest.mark.parametrize("mode", ["rebuild", "late-publish", "late-withdraw"])
def test_superseded_claims_cannot_reappear_in_a_rebuild_or_delayed_event(
    session: Session, tenant: Tenant, tmp_path: Path, mode: str
) -> None:
    store, settings, old_facts, _ = published_official_revision(session, tenant, tmp_path)
    gateway = RecordingGateway()
    old_claims = {fact.published_resource_id for fact in old_facts}
    if mode == "rebuild":
        documents = list(
            SearchRebuilder(_factory(session), cast(OpenSearchGateway, gateway), store, settings).documents()
        )
        assert not any(document.source.get("evidence_claim_id") in old_claims for document in documents)
    else:
        consumer = SearchProjectionConsumer(_factory(session), cast(OpenSearchGateway, gateway), store, settings)
        for claim_id in old_claims:
            assert claim_id is not None
            consumer._project(
                ClaimedEvent(
                    "delivery",
                    "event",
                    tenant.id,
                    "evidence_claim",
                    claim_id,
                    "governance.fact.published" if mode == "late-publish" else "governance.fact.withdrawn",
                    {"evidence_claim_id": claim_id},
                    1,
                )
            )
        assert not any(document.source.get("evidence_claim_id") in old_claims for document in gateway.documents)
        assert {claim for _, claim in gateway.deleted_claims} == old_claims


def test_delayed_withdrawal_preserves_a_shared_claim_that_is_currently_published(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    store, settings, old_facts, new_facts = published_official_revision(session, tenant, tmp_path, same_document=True)
    old_claims = {fact.published_resource_id for fact in old_facts}
    assert old_claims == {fact.published_resource_id for fact in new_facts}
    gateway = RecordingGateway()
    consumer = SearchProjectionConsumer(_factory(session), cast(OpenSearchGateway, gateway), store, settings)
    for claim_id in old_claims:
        assert claim_id is not None
        consumer._project(
            ClaimedEvent(
                "delivery",
                "event",
                tenant.id,
                "evidence_claim",
                claim_id,
                "governance.fact.withdrawn",
                {"evidence_claim_id": claim_id},
                1,
            )
        )
    assert gateway.deleted_claims == []
    assert {document.source["evidence_claim_id"] for document in gateway.documents} == old_claims


def test_legacy_ungoverned_evidence_remains_projectable_without_fabricated_provenance(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    _, _, _, facts = published_official_revision(session, tenant, tmp_path)
    current = session.get(EvidenceClaim, facts[0].published_resource_id)
    assert current is not None
    legacy = EvidenceClaim(
        tenant_id=tenant.id,
        subject_id=current.subject_id,
        predicate="legacy_assertion",
        source_document_id=current.source_document_id,
        quote="Preserve the source text",
        review_status=ReviewStatus.VERIFIED,
    )
    session.add(legacy)
    session.flush()
    projection = evidence_claim_projection(session, tenant.id, legacy.id)
    assert projection is not None
    assert projection.source["content"] == "Preserve the source text"
    assert projection.source["dataset_key"] == "unclassified"
    assert projection.source["source_asset_id"] is None
