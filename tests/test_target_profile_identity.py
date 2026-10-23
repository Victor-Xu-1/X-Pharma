from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from pharma_intel.api import app
from pharma_intel.db import get_session
from pharma_intel.identity import EntityIdentityService
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    Entity,
    EntityCanonicalLink,
    EntityResolutionCase,
    EntityType,
    ResolutionStatus,
    ReviewStatus,
    TargetProfile,
    Tenant,
)
from pharma_intel.security import Principal, require_principal


def _target(session: Session, tenant_id: str, name: str, status: ReviewStatus) -> Entity:
    entity = Entity(
        tenant_id=tenant_id,
        entity_type=EntityType.TARGET,
        name=name,
        normalized_name=name.casefold(),
        external_ids={"chembl": "CHEMBL203"},
        review_status=status,
    )
    session.add(entity)
    session.flush()
    return entity


@pytest.mark.parametrize("include_unpublished", [False, True])
@pytest.mark.parametrize("candidate_status", [ReviewStatus.DRAFT, ReviewStatus.VERIFIED])
def test_target_profile_never_borrows_an_unreconciled_entity_profile(
    session: Session, tenant: Tenant, include_unpublished: bool, candidate_status: ReviewStatus
) -> None:
    target = _target(session, tenant.id, "Verified target", ReviewStatus.VERIFIED)
    other = _target(session, tenant.id, "Unreconciled target", candidate_status)
    session.add(
        TargetProfile(
            tenant_id=tenant.id,
            entity_id=other.id,
            gene_symbol="OTHER_TARGET",
            function_summary="Unreviewed profile owned by a different entity",
        )
    )
    session.commit()
    result = IntelligenceService(session, tenant.id, include_unpublished=include_unpublished).target_profile(target.id)
    assert result is not None and result.entity.id == target.id
    assert result.entity.canonical_entity_id == target.id
    assert result.profile_id is None
    assert result.gene_symbol is None
    assert result.function_summary is None


def test_missing_profile_does_not_materialize_every_other_target_profile(session: Session, tenant: Tenant) -> None:
    target = _target(session, tenant.id, "Requested target", ReviewStatus.VERIFIED)
    for index in range(40):
        other = _target(session, tenant.id, f"Unrelated target {index}", ReviewStatus.VERIFIED)
        other.external_ids = {"chembl": f"CHEMBL{9000 + index}"}
        session.add(TargetProfile(tenant_id=tenant.id, entity_id=other.id, gene_symbol=f"OTHER_{index}"))
    session.commit()
    tenant_id, target_id = tenant.id, target.id
    session.expunge_all()
    loaded_profiles: list[str] = []

    def record_loaded(_session: Session, instance: object) -> None:
        if isinstance(instance, TargetProfile):
            loaded_profiles.append(instance.entity_id)

    event.listen(session, "loaded_as_persistent", record_loaded)
    try:
        result = IntelligenceService(session, tenant_id, include_unpublished=False).target_profile(target_id)
    finally:
        event.remove(session, "loaded_as_persistent", record_loaded)
    assert result is not None and result.profile_id is None
    assert loaded_profiles == []


@pytest.mark.parametrize("include_unpublished", [False, True])
def test_target_profile_keeps_its_own_authoritative_fields(
    session: Session, tenant: Tenant, include_unpublished: bool
) -> None:
    target = _target(session, tenant.id, "Verified target", ReviewStatus.VERIFIED)
    own = TargetProfile(tenant_id=tenant.id, entity_id=target.id, gene_symbol="EGFR", organism="Homo sapiens")
    session.add(own)
    session.commit()
    result = IntelligenceService(session, tenant.id, include_unpublished=include_unpublished).target_profile(target.id)
    assert result is not None and result.entity.id == target.id
    assert result.profile_id == own.id
    assert result.gene_symbol == "EGFR" and result.organism == "Homo sapiens"


def _approved_link(session: Session, tenant_id: str, alias: Entity, canonical: Entity) -> EntityCanonicalLink:
    case = EntityResolutionCase(
        tenant_id=tenant_id,
        source_entity_id=alias.id,
        candidate_entity_id=canonical.id,
        score=1,
        risk_tier="low",
        reasons=[],
        proposed_by="controlled identity fixture",
        status=ResolutionStatus.APPROVED,
    )
    session.add(case)
    session.flush()
    link = EntityCanonicalLink(
        tenant_id=tenant_id, alias_entity_id=alias.id, canonical_entity_id=canonical.id, resolution_case_id=case.id
    )
    session.add(link)
    session.flush()
    return link


def test_reviewed_identity_chain_keeps_profile_access_and_revocation(session: Session, tenant: Tenant) -> None:
    canonical = _target(session, tenant.id, "Canonical target", ReviewStatus.VERIFIED)
    intermediate = _target(session, tenant.id, "Reviewed intermediate", ReviewStatus.VERIFIED)
    alias = _target(session, tenant.id, "Reviewed profile owner", ReviewStatus.VERIFIED)
    for item in (canonical, intermediate, alias):
        item.external_ids = {}
    _approved_link(session, tenant.id, intermediate, canonical)
    link = _approved_link(session, tenant.id, alias, intermediate)
    profile = TargetProfile(tenant_id=tenant.id, entity_id=alias.id, gene_symbol="EGFR")
    session.add(profile)
    session.commit()
    assert EntityIdentityService(session, tenant.id).canonical_entity_id(alias.id) == canonical.id
    service = IntelligenceService(session, tenant.id, include_unpublished=False)
    result = service.target_profile(canonical.id)
    assert result is not None and result.profile_id == profile.id and result.gene_symbol == "EGFR"
    link.active = False
    session.commit()
    result = service.target_profile(canonical.id)
    assert result is not None and result.profile_id is None


def test_reviewed_link_does_not_publish_draft_profile_or_choose_between_two_owners(
    session: Session, tenant: Tenant
) -> None:
    canonical = _target(session, tenant.id, "Canonical target", ReviewStatus.VERIFIED)
    first = _target(session, tenant.id, "First profile owner", ReviewStatus.DRAFT)
    second = _target(session, tenant.id, "Second profile owner", ReviewStatus.VERIFIED)
    for item in (canonical, first, second):
        item.external_ids = {}
    _approved_link(session, tenant.id, first, canonical)
    session.add(TargetProfile(tenant_id=tenant.id, entity_id=first.id, gene_symbol="FIRST"))
    session.commit()
    service = IntelligenceService(session, tenant.id, include_unpublished=False)
    result = service.target_profile(canonical.id)
    assert result is not None and result.profile_id is None
    first.review_status = ReviewStatus.VERIFIED
    _approved_link(session, tenant.id, second, canonical)
    session.add(TargetProfile(tenant_id=tenant.id, entity_id=second.id, gene_symbol="SECOND"))
    session.commit()
    result = service.target_profile(canonical.id)
    assert result is not None and result.profile_id is None


def test_public_http_profile_and_dossier_keep_the_same_reviewed_identity_boundary(
    session: Session, tenant: Tenant
) -> None:
    target = _target(session, tenant.id, "Public target", ReviewStatus.VERIFIED)
    other = _target(session, tenant.id, "Draft target", ReviewStatus.DRAFT)
    session.add(
        TargetProfile(
            tenant_id=tenant.id, entity_id=other.id, gene_symbol="PRIVATE_DRAFT", function_summary="NOT_PUBLISHED"
        )
    )
    session.commit()

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, "viewer", "user", frozenset({"targets:read", "dossiers:read"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            for endpoint in ("profile", "dossier"):
                response = client.get(f"/api/v1/targets/{target.id}/{endpoint}")
                assert response.status_code == 200
                assert "PRIVATE_DRAFT" not in response.text and "NOT_PUBLISHED" not in response.text
                data = response.json()
                profile = data if endpoint == "profile" else data["profile"]
                assert profile["entity"]["id"] == target.id
                assert profile.get("profile_id") is None
    finally:
        app.dependency_overrides.clear()
