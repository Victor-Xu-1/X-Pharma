from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.accounts.identity import create_account
from pharma_intel.identity import EntityIdentityService, IdentityError, normalize_identifier
from pharma_intel.models import (
    EntityCanonicalLink,
    EntityIdentifier,
    EntityResolutionDecision,
    EntityType,
    OutboxEvent,
    ResolutionStatus,
    ReviewStatus,
    Tenant,
    User,
    UserRole,
)
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import EntityCreate


def _user(session: Session, tenant: Tenant) -> User:
    user = create_account(
        tenant_id=tenant.id,
        email="reviewer@example.test",
        normalized_email="reviewer@example.test",
        display_name="Reviewer",
        password_hash="not-used",  # noqa: S106
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.commit()
    return user


def test_identifier_normalization_is_namespace_aware() -> None:
    assert normalize_identifier("HGNC_ID", "HGNC:3236").normalized_value == "3236"
    assert normalize_identifier("doi", "https://doi.org/10.1000/ABC").normalized_value == "10.1000/abc"
    assert normalize_identifier("publication-number", "WO 2024-123456").normalized_value == "WO2024123456"
    assert normalize_identifier("customer_registry", " Acme-01 ").trusted is False


def test_trusted_identifier_resolves_existing_entity(session: Session, tenant: Tenant) -> None:
    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.TARGET, name="EGFR", external_ids={"uniprot": "P00533"})
    )
    identity = EntityIdentityService(session, tenant.id)
    identity.sync_identifiers(
        entity,
        {"uniprot": "P00533"},
        review_status=ReviewStatus.VERIFIED,
    )

    resolved = identity.resolve_or_create(
        {"entity_type": "target", "name": "ERBB1", "external_ids": {"uniprotkb": "P00533"}}
    )

    assert resolved.id == entity.id
    assert resolved.external_ids["uniprot"] == "P00533"


def test_deterministic_source_can_promote_a_draft_trusted_identifier(session: Session, tenant: Tenant) -> None:
    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.TARGET, name="Epidermal growth factor receptor")
    )
    identity = EntityIdentityService(session, tenant.id)
    identity.sync_identifiers(
        entity,
        {"chembl": "CHEMBL203"},
        review_status=ReviewStatus.DRAFT,
    )

    resolved = identity.resolve_or_create(
        {
            "entity_type": "target",
            "name": "Epidermal growth factor receptor",
            "external_ids": {"chembl": "CHEMBL203"},
        },
        allow_unverified_trusted_identifiers=True,
    )

    assert resolved.id == entity.id
    assert resolved.review_status == ReviewStatus.VERIFIED
    assert resolved.identity_identifiers[0].review_status == ReviewStatus.VERIFIED


def test_conflicting_trusted_identifier_creates_review_case_and_reversible_link(
    session: Session, tenant: Tenant
) -> None:
    repository = EntityRepository(session, tenant.id)
    existing = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="ALK", external_ids={"hgnc": "427"}))
    identity = EntityIdentityService(session, tenant.id)
    identity.sync_identifiers(existing, {"hgnc": "427"}, review_status=ReviewStatus.VERIFIED)

    source = identity.resolve_or_create({"entity_type": "target", "name": "ALK", "external_ids": {"hgnc": "99999"}})
    cases = identity.list_cases(status=ResolutionStatus.PENDING, limit=10)

    assert source.id != existing.id
    assert len(cases) == 1
    assert cases[0].risk_tier == "high"
    assert any(reason["code"] == "trusted_identifier_conflict" for reason in cases[0].reasons)

    reviewer = _user(session, tenant)
    approved = identity.decide(
        cases[0].id,
        action="approve",
        expected_status="pending",
        canonical_entity_id=existing.id,
        user_id=reviewer.id,
        notes="verified manually",
    )
    assert approved.status == ResolutionStatus.APPROVED
    assert identity.canonical_entity_id(source.id) == existing.id

    reverted = identity.decide(
        cases[0].id,
        action="revert",
        expected_status="approved",
        canonical_entity_id=None,
        user_id=reviewer.id,
        notes="new evidence",
    )
    assert reverted.status == ResolutionStatus.REVERTED
    assert identity.canonical_entity_id(source.id) == source.id
    link = session.scalar(select(EntityCanonicalLink).where(EntityCanonicalLink.alias_entity_id == source.id))
    assert link is not None
    assert len(list(session.scalars(select(EntityResolutionDecision)))) == 2


def test_name_only_match_creates_draft_and_review_case(session: Session, tenant: Tenant) -> None:
    existing = EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.TARGET, name="Same Name")
    )

    source = EntityIdentityService(session, tenant.id).resolve_or_create(
        {"entity_type": "target", "name": "Same Name", "external_ids": {}}
    )
    cases = EntityIdentityService(session, tenant.id).list_cases(status=ResolutionStatus.PENDING, limit=10)

    assert source.id != existing.id
    assert source.review_status == ReviewStatus.DRAFT
    assert len(cases) == 1
    assert cases[0].risk_tier == "high"


def test_same_governed_source_reuses_exact_name_without_merging_across_documents(
    session: Session, tenant: Tenant
) -> None:
    identity = EntityIdentityService(session, tenant.id)
    reference = {"entity_type": "drug", "name": "Compound A", "external_ids": {}}

    first = identity.resolve_or_create(reference, source_document_id="document-a")
    repeated = identity.resolve_or_create(reference, source_document_id="document-a")
    other_document = identity.resolve_or_create(reference, source_document_id="document-b")

    assert repeated.id == first.id
    assert first.attributes["source_document_ids"] == ["document-a"]
    assert other_document.id != first.id
    assert other_document.review_status == ReviewStatus.DRAFT


def test_governed_entity_creation_emits_search_projection_event(session: Session, tenant: Tenant) -> None:
    entity = EntityIdentityService(session, tenant.id).resolve_or_create(
        {
            "entity_type": "target",
            "name": "IL27",
            "external_ids": {"pharmcube_target": "a" * 64},
        },
        source_document_id="document-a",
    )
    session.flush()

    events = list(
        session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.tenant_id == tenant.id,
                OutboxEvent.aggregate_id == entity.id,
                OutboxEvent.event_type == "canonical.entity.upserted",
            )
        )
    )

    assert len(events) == 1
    assert events[0].payload == {"entity_id": entity.id, "schema_version": 1}


def test_unchanged_governed_entity_does_not_duplicate_projection_event(session: Session, tenant: Tenant) -> None:
    identity = EntityIdentityService(session, tenant.id)
    reference = {
        "entity_type": "target",
        "name": "IL27",
        "external_ids": {"pharmcube_target": "b" * 64},
    }
    entity = identity.resolve_or_create(reference, source_document_id="document-a")
    repeated = identity.resolve_or_create(reference, source_document_id="document-a")
    session.flush()

    assert repeated.id == entity.id
    assert (
        session.scalar(
            select(func.count(OutboxEvent.id)).where(
                OutboxEvent.tenant_id == tenant.id,
                OutboxEvent.aggregate_id == entity.id,
                OutboxEvent.event_type == "canonical.entity.upserted",
            )
        )
        == 1
    )


def test_identifiers_resolving_multiple_entities_never_mutate_a_candidate(session: Session, tenant: Tenant) -> None:
    repository = EntityRepository(session, tenant.id)
    first = repository.create(
        EntityCreate(entity_type=EntityType.TARGET, name="Target A", external_ids={"hgnc": "427"})
    )
    second = repository.create(
        EntityCreate(entity_type=EntityType.TARGET, name="Target B", external_ids={"uniprot": "P00533"})
    )
    identity = EntityIdentityService(session, tenant.id)
    identity.sync_identifiers(first, {"hgnc": "427"}, review_status=ReviewStatus.VERIFIED)
    identity.sync_identifiers(second, {"uniprot": "P00533"}, review_status=ReviewStatus.VERIFIED)

    source = identity.resolve_or_create(
        {
            "entity_type": "target",
            "name": "Conflicting bridge",
            "external_ids": {"hgnc": "427", "uniprot": "P00533"},
        }
    )
    cases = identity.list_cases(status=ResolutionStatus.PENDING, limit=10)
    source_identifiers = list(session.scalars(select(EntityIdentifier).where(EntityIdentifier.entity_id == source.id)))

    assert source.id not in {first.id, second.id}
    assert source.review_status == ReviewStatus.DRAFT
    assert all(item.review_status == ReviewStatus.DRAFT for item in source_identifiers)
    assert {case.candidate_entity_id for case in cases} == {first.id, second.id}
    assert all(case.risk_tier == "high" for case in cases)
    assert first.external_ids == {"hgnc": "427"}
    assert second.external_ids == {"uniprot": "P00533"}
    reviewer = _user(session, tenant)
    with pytest.raises(IdentityError, match="decision reason"):
        identity.decide(
            cases[0].id,
            action="approve",
            expected_status="pending",
            canonical_entity_id=cases[0].candidate_entity_id,
            user_id=reviewer.id,
            notes=None,
        )
    identity.decide(
        cases[0].id,
        action="approve",
        expected_status="pending",
        canonical_entity_id=cases[0].candidate_entity_id,
        user_id=reviewer.id,
        notes="first canonical choice",
    )
    with pytest.raises(IdentityError, match="active canonical link"):
        identity.decide(
            cases[1].id,
            action="approve",
            expected_status="pending",
            canonical_entity_id=cases[1].candidate_entity_id,
            user_id=reviewer.id,
            notes="conflicting choice",
        )


def test_versioned_ontology_is_immutable_and_type_safe(session: Session, tenant: Tenant) -> None:
    repository = EntityRepository(session, tenant.id)
    target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
    drug = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="Gefitinib"))
    identity = EntityIdentityService(session, tenant.id)
    payload = {
        "ontology_name": "efo",
        "ontology_version": "2026-07",
        "term_id": "EFO:0001645",
        "entity_type": "target",
        "preferred_label": "EGFR",
        "synonyms": ["ERBB1"],
        "parent_term_ids": [],
    }
    term = identity.register_ontology_term(payload)
    assert identity.register_ontology_term(payload).id == term.id

    changed = {**payload, "preferred_label": "Changed in place"}
    try:
        identity.register_ontology_term(changed)
    except IdentityError as exc:
        assert "new ontology version" in str(exc)
    else:
        raise AssertionError("Ontology version mutation must fail")

    mapping = identity.map_ontology_term(
        entity_id=target.id,
        ontology_term_id=term.id,
        mapping_type="exact",
        confidence=1.0,
        evidence={"curator": "test"},
        source_document_id=None,
        review_status=ReviewStatus.VERIFIED,
    )
    assert mapping.entity_id == target.id
    try:
        identity.map_ontology_term(
            entity_id=drug.id,
            ontology_term_id=term.id,
            mapping_type="exact",
            confidence=1.0,
            evidence={},
            source_document_id=None,
            review_status=ReviewStatus.VERIFIED,
        )
    except IdentityError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("Cross-type ontology mapping must fail")
