from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from pharma_intel.api import app
from pharma_intel.config import Settings
from pharma_intel.db import get_session
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    DealAssetAssociation,
    DealDirection,
    DealPartyAssociation,
    DealPartyRole,
    DealProfile,
    DealRight,
    DealRightType,
    DealStatus,
    DevelopmentPhase,
    DevelopmentProgram,
    EntityType,
    EpidemiologyObservation,
    MonitoringAlert,
    MonitoringAlertReceipt,
    MonitoringTopic,
    NewsEvent,
    OutboxEvent,
    PatentFamily,
    PatientPopulation,
    PatientPopulationEntityLink,
    ProjectionDelivery,
    ProjectionDeliveryState,
    RegulatoryDesignationType,
    RegulatoryEvent,
    RegulatoryLabelChangeType,
    RegulatorySafetySeverity,
    RegulatorySafetySignalType,
    RegulatorySafetyStatus,
    Relationship,
    SavedSearchVersion,
    SavedSearchVisibility,
    Tenant,
    TrialEntityRole,
    User,
    UserRole,
)
from pharma_intel.monitoring.consumer import (
    CONSUMER_NAME,
    MonitoringConsumer,
    entity_matches_saved_search_version,
    saved_search_matches_entity,
)
from pharma_intel.monitoring.service import MonitoringConflict, MonitoringNotFound, MonitoringService
from pharma_intel.repository import EntityRepository
from pharma_intel.schemas import (
    ChemistrySavedSearchQuery,
    ClinicalTrialSavedSearchQuery,
    DealSavedSearchQuery,
    EntityCreate,
    EntitySearchQuery,
    EpidemiologySavedSearchQuery,
    NewsSavedSearchQuery,
    PatentSavedSearchQuery,
    PipelineSavedSearchQuery,
    RegulatorySavedSearchQuery,
    SavedSearchCreate,
    SavedSearchUpdate,
)
from pharma_intel.security import Principal, require_principal


def _user(session: Session, tenant: Tenant, suffix: str) -> User:
    user = User(
        tenant_id=tenant.id,
        email=f"{suffix}@example.test",
        normalized_email=f"{suffix}@example.test",
        display_name=suffix,
        password_hash="not-used",  # noqa: S106
        role=UserRole.ANALYST,
    )
    session.add(user)
    session.commit()
    return user


def test_regulatory_saved_search_rejects_empty_and_inverted_ranges() -> None:
    with pytest.raises(ValueError, match="At least one regulatory search filter is required"):
        RegulatorySavedSearchQuery()
    with pytest.raises(ValueError, match="decision_from must not be after decision_to"):
        RegulatorySavedSearchQuery(decision_from=datetime(2026, 3, 1).date(), decision_to=datetime(2026, 2, 1).date())
    assert RegulatorySavedSearchQuery(has_boxed_warning=False).has_boxed_warning is False


def test_epidemiology_and_news_saved_searches_reject_invalid_contracts() -> None:
    with pytest.raises(ValueError, match="At least one epidemiology search filter is required"):
        EpidemiologySavedSearchQuery()
    with pytest.raises(ValueError, match="period_start_from must not be after period_end_to"):
        EpidemiologySavedSearchQuery(
            period_start_from=datetime(2026, 3, 1).date(),
            period_end_to=datetime(2026, 2, 1).date(),
        )
    with pytest.raises(ValueError, match="At least one news search filter is required"):
        NewsSavedSearchQuery()
    with pytest.raises(ValueError, match="published_from must not be after published_to"):
        NewsSavedSearchQuery(
            published_from=datetime(2026, 3, 1).date(),
            published_to=datetime(2026, 2, 1).date(),
        )
    with pytest.raises(ValueError, match="timeline display requires research content_scope"):
        NewsSavedSearchQuery(q="EGFR", display_mode="timeline")
    with pytest.raises(ValueError, match="research content_scope requires a research event_type"):
        NewsSavedSearchQuery(event_type="news", content_scope="research")


def test_chemistry_saved_search_preserves_server_side_structure_query() -> None:
    saved = ChemistrySavedSearchQuery(
        mode="similarity",
        query="CC(=O)Oc1ccccc1C(=O)O",
        threshold=0.75,
        limit=50,
    )
    assert saved.model_dump(mode="json") == {
        "mode": "similarity",
        "query": "CC(=O)Oc1ccccc1C(=O)O",
        "threshold": 0.75,
        "limit": 50,
    }
    with pytest.raises(ValueError):
        ChemistrySavedSearchQuery(mode="exact", query="", limit=20)


def test_saved_search_sharing_topics_and_durable_alert_delivery(session: Session, tenant: Tenant) -> None:
    owner = _user(session, tenant, "owner")
    colleague = _user(session, tenant, "colleague")
    owner_service = MonitoringService(session, tenant.id, owner.id)
    private = owner_service.create_saved_search(
        SavedSearchCreate(name="Private KRAS", query=EntitySearchQuery(q="KRAS"))
    )
    shared = owner_service.create_saved_search(
        SavedSearchCreate(
            name="Shared EGFR",
            query=EntitySearchQuery(q="ERBB1", entity_type=EntityType.TARGET),
            visibility=SavedSearchVisibility.TENANT,
        )
    )
    chemistry = owner_service.create_saved_search(
        SavedSearchCreate(
            name="Aspirin structure",
            query_type="chemistry_search",
            query=ChemistrySavedSearchQuery(mode="exact", query="CC(=O)Oc1ccccc1C(=O)O"),
        )
    )
    with pytest.raises(MonitoringConflict, match="do not support change monitoring"):
        owner_service.create_topic("Aspirin structure changes", chemistry.id)
    legacy_topic = MonitoringTopic(
        tenant_id=tenant.id,
        owner_user_id=owner.id,
        saved_search_id=chemistry.id,
        query_version=chemistry.query_version,
        name="Legacy aspirin structure changes",
        active=False,
    )
    session.add(legacy_topic)
    session.commit()
    with pytest.raises(MonitoringConflict, match="do not support change monitoring"):
        owner_service.update_topic(legacy_topic.id, name=None, active=True, query_version=None)

    colleague_service = MonitoringService(session, tenant.id, colleague.id)
    assert {item.id for item in colleague_service.list_saved_searches()} == {shared.id}
    topic = colleague_service.create_topic("EGFR changes", shared.id)
    assert topic.active is True
    assert topic.query_version == 1
    entity = EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.TARGET, name="EGFR", aliases=["ERBB1"])
    )
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    consumer = MonitoringConsumer(factory, Settings(), worker_id="monitoring-test")

    first = consumer.drain()

    assert first.succeeded == 1
    assert consumer.drain_once().processed == 0
    alert = session.scalar(select(MonitoringAlert))
    assert alert is not None
    assert alert.topic_id == topic.id
    assert alert.entity_id == entity.id
    assert alert.recipient_user_id == colleague.id
    assert session.scalar(select(func.count()).select_from(MonitoringAlert)) == 1
    assert colleague_service.list_alerts(unread_only=True, limit=10)[0]["entity_name"] == "EGFR"

    read_at = colleague_service.mark_alert_read(alert.id)

    assert read_at.tzinfo is not None
    assert colleague_service.list_alerts(unread_only=True, limit=10) == []
    assert session.scalar(select(func.count()).select_from(MonitoringAlertReceipt)) == 1
    owner_service.update_saved_search(shared.id, SavedSearchUpdate(visibility=SavedSearchVisibility.PRIVATE))
    assert colleague_service.list_saved_searches() == []
    session.refresh(topic)
    assert topic.active is False
    with pytest.raises(MonitoringNotFound, match="Saved search not found"):
        colleague_service.update_topic(topic.id, name=None, active=True, query_version=None)

    # Defense in depth: a stale or manually reactivated topic cannot bypass the current sharing boundary.
    topic.active = True
    session.commit()
    EntityRepository(session, tenant.id).create(
        EntityCreate(entity_type=EntityType.TARGET, name="EGFR follow-up", aliases=["ERBB1"])
    )
    assert consumer.drain().succeeded == 1
    assert session.scalar(select(func.count()).select_from(MonitoringAlert)) == 1

    owner_service.update_saved_search(shared.id, SavedSearchUpdate(query=EntitySearchQuery(q="EGFR")))
    assert session.scalar(select(func.count()).select_from(SavedSearchVersion)) == 4
    versions = list(
        session.scalars(
            select(SavedSearchVersion)
            .where(SavedSearchVersion.saved_search_id == shared.id)
            .order_by(SavedSearchVersion.version)
        )
    )
    assert [version.query_json for version in versions] == [
        {"q": "ERBB1", "entity_type": "target", "sort_by": "relevance", "sort_direction": "desc"},
        {"q": "EGFR", "sort_by": "relevance", "sort_direction": "desc"},
    ]
    assert private.visibility == SavedSearchVisibility.PRIVATE
    session.refresh(topic)
    assert topic.query_version == 1


def test_saved_search_multi_type_filter_is_versioned_and_enforced(session: Session, tenant: Tenant) -> None:
    owner = _user(session, tenant, "multi-type-owner")
    saved = MonitoringService(session, tenant.id, owner.id).create_saved_search(
        SavedSearchCreate(
            name="Target and drug portfolio",
            query=EntitySearchQuery(q="Portfolio", entity_types=[EntityType.TARGET, EntityType.DRUG]),
        )
    )
    version = session.scalar(
        select(SavedSearchVersion).where(
            SavedSearchVersion.saved_search_id == saved.id,
            SavedSearchVersion.version == 1,
        )
    )
    assert version is not None
    assert version.query_json == {
        "q": "Portfolio",
        "entity_types": ["target", "drug"],
        "sort_by": "relevance",
        "sort_direction": "desc",
    }
    repository = EntityRepository(session, tenant.id)
    target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="Portfolio target"))
    drug = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="Portfolio drug"))
    organization = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="Portfolio organization"))

    assert entity_matches_saved_search_version(target, version) is True
    assert entity_matches_saved_search_version(drug, version) is True
    assert entity_matches_saved_search_version(organization, version) is False


def test_entity_saved_search_preserves_statistics_presentation_state(session: Session, tenant: Tenant) -> None:
    owner = _user(session, tenant, "landscape-owner")
    saved = MonitoringService(session, tenant.id, owner.id).create_saved_search(
        SavedSearchCreate(
            name="EGFR statistics",
            query=EntitySearchQuery(
                q="EGFR",
                entity_type=EntityType.TARGET,
                display_mode="landscape",
                analysis_view="table",
            ),
        )
    )
    version = session.scalar(
        select(SavedSearchVersion).where(
            SavedSearchVersion.saved_search_id == saved.id,
            SavedSearchVersion.version == 1,
        )
    )

    assert version is not None
    assert version.query_json == {
        "q": "EGFR",
        "entity_type": "target",
        "display_mode": "landscape",
        "analysis_view": "table",
        "sort_by": "relevance",
        "sort_direction": "desc",
    }


def test_pipeline_saved_search_is_versioned_replayed_and_emits_related_alert(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "pipeline-owner")
    repository = EntityRepository(session, tenant.id)
    drug = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="VX-101"))
    target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
    disease = repository.create(EntityCreate(entity_type=EntityType.DISEASE, name="NSCLC"))
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=drug.id,
            target_entity_id=target.id,
            disease_entity_id=disease.id,
            modality="small molecule",
            phase=DevelopmentPhase.PHASE_2,
            global_phase=DevelopmentPhase.PHASE_2.value,
        )
    )
    session.commit()
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="EGFR global pipeline",
            query_type="pipeline_search",
            query=PipelineSavedSearchQuery(
                drug_entity_id=drug.id,
                target_entity_id=target.id,
                global_phase=DevelopmentPhase.PHASE_2,
                display_mode="landscape",
                analysis_dimension="targets",
                analysis_limit=50,
                analysis_stage_scope="global",
                target_aggregation="primary",
            ),
        )
    )
    topic = service.create_topic("EGFR pipeline changes", saved.id)
    version = session.scalar(select(SavedSearchVersion).where(SavedSearchVersion.saved_search_id == saved.id))
    assert version is not None
    assert version.query_type == "pipeline_search"
    assert version.query_json["drug_entity_id"] == drug.id
    assert version.query_json["analysis_limit"] == 50
    assert saved_search_matches_entity(session, tenant.id, drug, version) is True
    assert saved_search_matches_entity(session, tenant.id, target, version) is True
    assert saved_search_matches_entity(session, tenant.id, disease, version) is True
    unrelated = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="BRAF"))
    assert saved_search_matches_entity(session, tenant.id, unrelated, version) is False

    session.add(
        OutboxEvent(
            tenant_id=tenant.id,
            aggregate_type="entity",
            aggregate_id=target.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": target.id},
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    result = MonitoringConsumer(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False),
        Settings(),
        worker_id="pipeline-monitoring-test",
    ).drain()
    alert = session.scalar(select(MonitoringAlert).where(MonitoringAlert.topic_id == topic.id))
    assert result.succeeded >= 1
    assert alert is not None
    assert alert.entity_id == target.id
    assert alert.payload_json["query_version"] == 1


def test_clinical_trial_saved_search_reuses_domain_filters_and_emits_related_alert(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "trial-owner")
    repository = EntityRepository(session, tenant.id)
    target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
    target_variant = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR exon 20"))
    trial_entity = repository.create(EntityCreate(entity_type=EntityType.CLINICAL_TRIAL, name="NCT00000001"))
    trial = ClinicalTrialProfile(
        tenant_id=tenant.id,
        entity_id=trial_entity.id,
        registry_name="ClinicalTrials.gov",
        registry_id="NCT00000001",
        official_title="Phase 2 EGFR inhibitor trial",
        acronym="KEYNOTE-EGFR",
        initiation_type="ist",
        therapy_lines=["first_line"],
        overall_status="RECRUITING",
        phases=["PHASE2"],
        study_type="INTERVENTIONAL",
        has_results=True,
        result_evaluation="positive",
        results_first_posted=datetime(2026, 7, 10, tzinfo=UTC),
        last_update_posted=datetime(2026, 7, 12, tzinfo=UTC),
    )
    session.add(trial)
    session.flush()
    session.add(
        ClinicalTrialEntityRole(
            tenant_id=tenant.id,
            trial_id=trial.id,
            entity_id=target.id,
            role=TrialEntityRole.INVESTIGATIONAL_TARGET.value,
        )
    )
    session.add(
        ClinicalTrialEntityRole(
            tenant_id=tenant.id,
            trial_id=trial.id,
            entity_id=target_variant.id,
            role=TrialEntityRole.INVESTIGATIONAL_TARGET.value,
        )
    )
    session.add(
        Relationship(
            tenant_id=tenant.id,
            subject_id=trial_entity.id,
            predicate="trial_links_entity",
            object_id=target.id,
        )
    )
    session.add(
        Relationship(
            tenant_id=tenant.id,
            subject_id=trial_entity.id,
            predicate="trial_links_entity",
            object_id=target_variant.id,
        )
    )
    session.commit()
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="EGFR recruiting results",
            query_type="clinical_trial_search",
            query=ClinicalTrialSavedSearchQuery(
                registry="ClinicalTrials.gov",
                status="RECRUITING",
                phase="PHASE2",
                acronym="KEYNOTE",
                initiation_type="ist",
                therapy_line="first_line",
                has_results=True,
                result_evaluation="positive",
                results_posted_from=datetime(2026, 7, 1, tzinfo=UTC).date(),
                results_posted_to=datetime(2026, 7, 31, tzinfo=UTC).date(),
                investigational_target_entity_ids=[target_variant.id, target.id],
                sort_by="result_evaluation",
            ),
        )
    )
    topic = service.create_topic("EGFR trial changes", saved.id)
    version = session.scalar(select(SavedSearchVersion).where(SavedSearchVersion.saved_search_id == saved.id))
    assert version is not None
    assert version.query_type == "clinical_trial_search"
    assert version.query_json["sort_by"] == "result_evaluation"
    assert version.query_json["investigational_target_entity_ids"] == sorted([target.id, target_variant.id])
    assert version.query_json["acronym"] == "KEYNOTE"
    assert version.query_json["initiation_type"] == "ist"
    assert version.query_json["therapy_line"] == "first_line"
    assert saved_search_matches_entity(session, tenant.id, target, version) is True
    assert saved_search_matches_entity(session, tenant.id, target_variant, version) is True
    assert saved_search_matches_entity(session, tenant.id, trial_entity, version) is True
    unrelated = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="BRAF"))
    assert saved_search_matches_entity(session, tenant.id, unrelated, version) is False

    session.add(
        OutboxEvent(
            tenant_id=tenant.id,
            aggregate_type="entity",
            aggregate_id=target.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": target.id},
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    result = MonitoringConsumer(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False),
        Settings(),
        worker_id="trial-monitoring-test",
    ).drain()
    alert = session.scalar(select(MonitoringAlert).where(MonitoringAlert.topic_id == topic.id))
    assert result.succeeded >= 1
    assert alert is not None
    assert alert.entity_id == target.id


def test_patent_saved_search_reuses_domain_filters_and_emits_related_alert(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "patent-owner")
    repository = EntityRepository(session, tenant.id)
    target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
    patent_entity = repository.create(EntityCreate(entity_type=EntityType.PATENT, name="WO2026000001"))
    session.add(
        PatentFamily(
            tenant_id=tenant.id,
            entity_id=patent_entity.id,
            family_identifier="WO2026000001",
            title="Covalent EGFR inhibitor family",
            priority_date=datetime(2024, 1, 10, tzinfo=UTC),
            applicants=["Victor Therapeutics"],
            inventors=["A. Researcher"],
            publications=[{"publication_number": "WO2026000001"}],
            legal_status="ACTIVE",
            linked_entity_ids=[target.id],
        )
    )
    session.add(
        Relationship(
            tenant_id=tenant.id,
            subject_id=patent_entity.id,
            predicate="patent_links_entity",
            object_id=target.id,
        )
    )
    session.commit()
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="Active Victor EGFR patents",
            query_type="patent_search",
            query=PatentSavedSearchQuery(
                q="EGFR",
                applicant="Victor Therapeutics",
                legal_status="ACTIVE",
                sort_by="family_identifier",
                sort_direction="asc",
            ),
        )
    )
    topic = service.create_topic("EGFR patent changes", saved.id)
    version = session.scalar(select(SavedSearchVersion).where(SavedSearchVersion.saved_search_id == saved.id))
    assert version is not None
    assert version.query_type == "patent_search"
    assert version.query_json["sort_by"] == "family_identifier"
    assert saved_search_matches_entity(session, tenant.id, target, version) is True
    assert saved_search_matches_entity(session, tenant.id, patent_entity, version) is True
    unrelated = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="BRAF"))
    assert saved_search_matches_entity(session, tenant.id, unrelated, version) is False

    session.add(
        OutboxEvent(
            tenant_id=tenant.id,
            aggregate_type="entity",
            aggregate_id=target.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": target.id},
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    result = MonitoringConsumer(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False),
        Settings(),
        worker_id="patent-monitoring-test",
    ).drain()
    alert = session.scalar(select(MonitoringAlert).where(MonitoringAlert.topic_id == topic.id))
    assert result.succeeded >= 1
    assert alert is not None
    assert alert.entity_id == target.id


def test_deal_saved_search_reuses_domain_filters_and_emits_related_alert(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "deal-owner")
    repository = EntityRepository(session, tenant.id)
    licensor = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="Acme Pharma"))
    asset = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="VX-101"))
    target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
    disease = repository.create(EntityCreate(entity_type=EntityType.DISEASE, name="Non-small cell lung cancer"))
    deal_entity = repository.create(EntityCreate(entity_type=EntityType.TRANSACTION, name="Acme VX-101 license"))
    deal = DealProfile(
        tenant_id=tenant.id,
        entity_id=deal_entity.id,
        deal_type="license",
        status=DealStatus.ACTIVE.value,
        direction=DealDirection.OUTBOUND.value,
        direction_reference_jurisdiction="US",
        announced_at=datetime(2026, 1, 10, tzinfo=UTC),
        source_updated_at=datetime(2026, 3, 15, tzinfo=UTC),
        parties=[{"entity_id": licensor.id, "name": licensor.name}],
        asset_entity_ids=[asset.id],
        territory="Greater China",
        upfront_amount=25_000_000,
        total_potential_amount=500_000_000,
        currency="USD",
    )
    session.add(deal)
    session.flush()
    session.add(
        DealPartyAssociation(
            tenant_id=tenant.id,
            deal_id=deal.id,
            party_entity_id=licensor.id,
            role=DealPartyRole.LICENSOR.value,
            country_region="US",
            organization_type="biopharma",
        )
    )
    session.add(
        DealAssetAssociation(
            tenant_id=tenant.id,
            deal_id=deal.id,
            asset_entity_id=asset.id,
            development_phase_at_transaction="phase_2",
        )
    )
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=asset.id,
            target_entity_id=target.id,
            disease_entity_id=disease.id,
            modality="antibody",
            phase=DevelopmentPhase.PHASE_3,
            program_tags=["first_in_class"],
            status_date=datetime(2026, 3, 10, tzinfo=UTC),
        )
    )
    session.add(
        DealRight(
            tenant_id=tenant.id,
            deal_id=deal.id,
            holder_entity_id=licensor.id,
            right_type=DealRightType.COMMERCIALIZATION.value,
            territory="Greater China",
            exclusive=True,
        )
    )
    session.commit()
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="Active outbound China licenses",
            query_type="deal_search",
            query=DealSavedSearchQuery(
                deal_type="license",
                status=DealStatus.ACTIVE,
                direction=DealDirection.OUTBOUND,
                direction_reference_jurisdiction="US",
                territory="Greater China",
                asset_entity_id=asset.id,
                target_entity_id=target.id,
                disease_entity_id=disease.id,
                asset_modality=["antibody", "small molecule"],
                asset_program_tag=["first_in_class", "best_in_class"],
                party_entity_id=licensor.id,
                party_role=DealPartyRole.LICENSOR,
                party_country_region="US",
                party_organization_type="biopharma",
                right_type=DealRightType.COMMERCIALIZATION,
                rights_territory="Greater China",
                currency="USD",
                announced_from=datetime(2026, 1, 1, tzinfo=UTC).date(),
                announced_to=datetime(2026, 1, 31, tzinfo=UTC).date(),
                upfront_amount_min=20_000_000,
                upfront_amount_max=30_000_000,
                sort_by="upfront_amount",
                sort_direction="asc",
                display_mode="landscape",
                analysis_dimension="party_country",
                analysis_view="table",
                analysis_limit=20,
            ),
        )
    )
    topic = service.create_topic("China deal changes", saved.id)
    version = session.scalar(select(SavedSearchVersion).where(SavedSearchVersion.saved_search_id == saved.id))
    assert version is not None
    assert version.query_type == "deal_search"
    assert version.query_json["sort_by"] == "upfront_amount"
    assert version.query_json["asset_entity_id"] == asset.id
    assert version.query_json["target_entity_id"] == target.id
    assert version.query_json["disease_entity_id"] == disease.id
    assert version.query_json["asset_modality"] == ["antibody", "small molecule"]
    assert version.query_json["asset_program_tag"] == ["first_in_class", "best_in_class"]
    assert version.query_json["display_mode"] == "landscape"
    assert version.query_json["analysis_dimension"] == "party_country"
    assert version.query_json["analysis_view"] == "table"
    assert version.query_json["analysis_limit"] == 20
    assert saved_search_matches_entity(session, tenant.id, licensor, version) is True
    assert saved_search_matches_entity(session, tenant.id, deal_entity, version) is True
    assert saved_search_matches_entity(session, tenant.id, asset, version) is True
    assert saved_search_matches_entity(session, tenant.id, target, version) is True
    assert saved_search_matches_entity(session, tenant.id, disease, version) is True
    unrelated = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="Beta Bio"))
    assert saved_search_matches_entity(session, tenant.id, unrelated, version) is False

    session.add(
        OutboxEvent(
            tenant_id=tenant.id,
            aggregate_type="entity",
            aggregate_id=licensor.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": licensor.id},
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    result = MonitoringConsumer(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False),
        Settings(),
        worker_id="deal-monitoring-test",
    ).drain()
    alert = session.scalar(select(MonitoringAlert).where(MonitoringAlert.topic_id == topic.id))
    assert result.succeeded >= 1
    assert alert is not None
    assert alert.entity_id == licensor.id


def test_regulatory_saved_search_reuses_domain_filters_and_emits_related_alert(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "regulatory-owner")
    repository = EntityRepository(session, tenant.id)
    drug = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="VX-101"))
    disease = repository.create(EntityCreate(entity_type=EntityType.DISEASE, name="EGFR-positive NSCLC"))
    sponsor = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="Acme Pharma"))
    session.add(
        RegulatoryEvent(
            tenant_id=tenant.id,
            subject_entity_id=drug.id,
            indication_entity_id=disease.id,
            organization_entity_id=sponsor.id,
            agency="FDA",
            jurisdiction="US",
            event_identifier="FDA-2026-001",
            application_number="NDA 219999",
            event_type="safety_signal",
            status="active",
            title="VX-101 pulmonary safety update",
            decision_date=datetime(2026, 2, 20, tzinfo=UTC),
            designation_type=RegulatoryDesignationType.BREAKTHROUGH_THERAPY.value,
            label_change_type=RegulatoryLabelChangeType.SAFETY_UPDATE.value,
            has_boxed_warning=False,
            safety_signal_type=RegulatorySafetySignalType.ADVERSE_EVENT.value,
            safety_term="Interstitial lung disease",
            safety_severity=RegulatorySafetySeverity.SERIOUS.value,
            safety_status=RegulatorySafetyStatus.CONFIRMED.value,
            source_updated_at=datetime(2026, 2, 21, tzinfo=UTC),
        )
    )
    session.commit()
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="FDA confirmed pulmonary signals",
            query_type="regulatory_search",
            query=RegulatorySavedSearchQuery(
                q="pulmonary",
                agency="FDA",
                jurisdiction="US",
                event_type="safety_signal",
                status="active",
                designation_type=RegulatoryDesignationType.BREAKTHROUGH_THERAPY,
                label_change_type=RegulatoryLabelChangeType.SAFETY_UPDATE,
                has_boxed_warning=False,
                safety_signal_type=RegulatorySafetySignalType.ADVERSE_EVENT,
                safety_severity=RegulatorySafetySeverity.SERIOUS,
                safety_status=RegulatorySafetyStatus.CONFIRMED,
                decision_from=datetime(2026, 2, 1, tzinfo=UTC).date(),
                decision_to=datetime(2026, 2, 28, tzinfo=UTC).date(),
                source_updated_from=datetime(2026, 2, 1, tzinfo=UTC).date(),
                source_updated_to=datetime(2026, 2, 28, tzinfo=UTC).date(),
                sort_by="source_updated_at",
                sort_direction="asc",
            ),
        )
    )
    topic = service.create_topic("FDA safety changes", saved.id)
    version = session.scalar(select(SavedSearchVersion).where(SavedSearchVersion.saved_search_id == saved.id))
    assert version is not None
    assert version.query_type == "regulatory_search"
    assert version.query_json["has_boxed_warning"] is False
    assert version.query_json["sort_by"] == "source_updated_at"
    assert saved_search_matches_entity(session, tenant.id, drug, version) is True
    assert saved_search_matches_entity(session, tenant.id, disease, version) is True
    assert saved_search_matches_entity(session, tenant.id, sponsor, version) is True
    unrelated = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="Beta Bio"))
    assert saved_search_matches_entity(session, tenant.id, unrelated, version) is False

    session.add(
        OutboxEvent(
            tenant_id=tenant.id,
            aggregate_type="entity",
            aggregate_id=sponsor.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": sponsor.id},
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    result = MonitoringConsumer(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False),
        Settings(),
        worker_id="regulatory-monitoring-test",
    ).drain()
    alert = session.scalar(select(MonitoringAlert).where(MonitoringAlert.topic_id == topic.id))
    assert result.succeeded >= 1
    assert alert is not None
    assert alert.entity_id == sponsor.id


def test_epidemiology_saved_search_matches_governed_relationships_and_emits_alert(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "epidemiology-owner")
    repository = EntityRepository(session, tenant.id)
    disease = repository.create(EntityCreate(entity_type=EntityType.DISEASE, name="EGFR-positive NSCLC"))
    publisher = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="Global Cancer Registry"))
    target = repository.create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
    population = PatientPopulation(
        tenant_id=tenant.id,
        population_key="nsclc-egfr-adults",
        name="Adults with EGFR-positive NSCLC",
        description="Governed epidemiology cohort",
    )
    session.add(population)
    session.flush()
    session.add_all(
        [
            PatientPopulationEntityLink(
                tenant_id=tenant.id,
                patient_population_id=population.id,
                entity_id=disease.id,
                relationship="disease",
            ),
            PatientPopulationEntityLink(
                tenant_id=tenant.id,
                patient_population_id=population.id,
                entity_id=target.id,
                relationship="target",
            ),
            EpidemiologyObservation(
                tenant_id=tenant.id,
                observation_identifier="EPI-2026-001",
                disease_entity_id=disease.id,
                patient_population_id=population.id,
                measure="prevalence",
                value=Decimal("125000"),
                unit="patients",
                geography="China",
                population_scope="adults",
                age_group="18+",
                sex="all",
                period_start=datetime(2025, 1, 1, tzinfo=UTC),
                period_end=datetime(2025, 12, 31, tzinfo=UTC),
                methodology="registry estimate",
                publisher_entity_id=publisher.id,
            ),
        ]
    )
    session.commit()
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="China EGFR-positive NSCLC burden",
            query_type="epidemiology_search",
            query=EpidemiologySavedSearchQuery(
                q="registry",
                disease_entity_id=disease.id,
                measure="prevalence",
                geography="China",
                unit="patients",
                patient_population_id=population.id,
                population_scope="adults",
                age_group="18+",
                sex="all",
                period_start_from=datetime(2025, 1, 1).date(),
                period_end_to=datetime(2025, 12, 31).date(),
                sort_by="value",
                sort_direction="asc",
            ),
        )
    )
    topic = service.create_topic("NSCLC burden changes", saved.id)
    version = session.scalar(select(SavedSearchVersion).where(SavedSearchVersion.saved_search_id == saved.id))
    assert version is not None
    assert version.query_type == "epidemiology_search"
    assert version.query_json["patient_population_id"] == population.id
    assert version.query_json["sort_by"] == "value"
    assert saved_search_matches_entity(session, tenant.id, disease, version) is True
    assert saved_search_matches_entity(session, tenant.id, publisher, version) is True
    assert saved_search_matches_entity(session, tenant.id, target, version) is True
    unrelated = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="Unrelated Registry"))
    assert saved_search_matches_entity(session, tenant.id, unrelated, version) is False

    session.add(
        OutboxEvent(
            tenant_id=tenant.id,
            aggregate_type="entity",
            aggregate_id=target.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": target.id},
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    result = MonitoringConsumer(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False),
        Settings(),
        worker_id="epidemiology-monitoring-test",
    ).drain()
    alert = session.scalar(select(MonitoringAlert).where(MonitoringAlert.topic_id == topic.id))
    assert result.succeeded >= 1
    assert alert is not None
    assert alert.entity_id == target.id


def test_news_saved_search_matches_related_entities_and_emits_alert(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "news-owner")
    repository = EntityRepository(session, tenant.id)
    publisher = repository.create(EntityCreate(entity_type=EntityType.ORGANIZATION, name="ASCO"))
    drug = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="VX-101"))
    event = NewsEvent(
        tenant_id=tenant.id,
        event_identifier="ASCO-2026-VX101",
        event_type="conference_abstract",
        title="VX-101 pivotal NSCLC results",
        summary="Positive EGFR cohort data",
        published_at=datetime(2026, 6, 1, tzinfo=UTC),
        language="en",
        publisher_entity_id=publisher.id,
        related_entity_ids=[drug.id],
        venue="ASCO 2026",
    )
    session.add(event)
    session.commit()
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="ASCO VX-101 research releases",
            query_type="news_search",
            query=NewsSavedSearchQuery(
                q="pivotal",
                event_type="conference_abstract",
                publisher="ASCO",
                language="en",
                venue="ASCO 2026",
                published_from=datetime(2026, 1, 1).date(),
                published_to=datetime(2026, 12, 31).date(),
                content_scope="research",
                display_mode="timeline",
                sort_by="venue",
                sort_direction="asc",
            ),
        )
    )
    topic = service.create_topic("ASCO research changes", saved.id)
    version = session.scalar(select(SavedSearchVersion).where(SavedSearchVersion.saved_search_id == saved.id))
    assert version is not None
    assert version.query_type == "news_search"
    assert version.query_json["content_scope"] == "research"
    assert version.query_json["display_mode"] == "timeline"
    assert saved_search_matches_entity(session, tenant.id, publisher, version) is True
    assert saved_search_matches_entity(session, tenant.id, drug, version) is True
    unrelated = repository.create(EntityCreate(entity_type=EntityType.DRUG, name="VX-999"))
    assert saved_search_matches_entity(session, tenant.id, unrelated, version) is False

    session.add(
        OutboxEvent(
            tenant_id=tenant.id,
            aggregate_type="entity",
            aggregate_id=drug.id,
            event_type="canonical.entity.upserted",
            payload={"entity_id": drug.id},
            created_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    result = MonitoringConsumer(
        sessionmaker(bind=session.get_bind(), expire_on_commit=False),
        Settings(),
        worker_id="news-monitoring-test",
    ).drain()
    alert = session.scalar(select(MonitoringAlert).where(MonitoringAlert.topic_id == topic.id))
    assert result.succeeded >= 1
    assert alert is not None
    assert alert.entity_id == drug.id


def test_monitoring_topic_uses_pinned_query_until_explicit_version_refresh(
    session: Session,
    tenant: Tenant,
) -> None:
    owner = _user(session, tenant, "version-owner")
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(
        SavedSearchCreate(
            name="Pinned target query",
            query=EntitySearchQuery(q="EGFR", entity_type=EntityType.TARGET),
        )
    )
    topic = service.create_topic("Pinned target changes", saved.id)
    service.update_saved_search(
        saved.id,
        SavedSearchUpdate(query=EntitySearchQuery(q="BRAF", entity_type=EntityType.TARGET)),
    )
    EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.TARGET, name="EGFR"))
    EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.TARGET, name="BRAF"))
    consumer = MonitoringConsumer(sessionmaker(bind=session.get_bind(), expire_on_commit=False), Settings())

    first = consumer.drain()

    assert first.succeeded == 2
    alerts = list(session.scalars(select(MonitoringAlert).order_by(MonitoringAlert.occurred_at, MonitoringAlert.id)))
    assert len(alerts) == 1
    assert service.list_alerts(unread_only=False, limit=10)[0]["entity_name"] == "EGFR"
    refreshed = service.update_topic(topic.id, name=None, active=None, query_version=2)
    assert refreshed.query_version == 2
    EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.TARGET, name="BRAF V600E"))

    second = consumer.drain()

    assert second.succeeded == 1
    assert {item["entity_name"] for item in service.list_alerts(unread_only=False, limit=10)} == {
        "EGFR",
        "BRAF V600E",
    }


def test_monitoring_consumer_recovers_expired_lease_without_duplicate_alert(session: Session, tenant: Tenant) -> None:
    owner = _user(session, tenant, "lease-owner")
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(SavedSearchCreate(name="TP53", query=EntitySearchQuery(q="TP53")))
    service.create_topic("TP53 changes", saved.id)
    EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.TARGET, name="TP53"))
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)
    first = MonitoringConsumer(factory, Settings(), worker_id="worker-1")
    assert first.drain_once().succeeded == 1
    delivery = session.scalar(select(ProjectionDelivery).where(ProjectionDelivery.consumer_name == CONSUMER_NAME))
    assert delivery is not None
    delivery.state = ProjectionDeliveryState.PROCESSING
    delivery.worker_id = "crashed-worker"
    delivery.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()

    recovered = MonitoringConsumer(factory, Settings(), worker_id="worker-2").drain_once()

    assert recovered.succeeded == 1
    assert session.scalar(select(func.count()).select_from(MonitoringAlert)) == 1
    session.refresh(delivery)
    assert delivery.state == ProjectionDeliveryState.SUCCEEDED


def test_new_topic_does_not_emit_alerts_for_preexisting_outbox_history(session: Session, tenant: Tenant) -> None:
    owner = _user(session, tenant, "history-owner")
    EntityRepository(session, tenant.id).create(EntityCreate(entity_type=EntityType.TARGET, name="ALK"))
    service = MonitoringService(session, tenant.id, owner.id)
    saved = service.create_saved_search(SavedSearchCreate(name="ALK", query=EntitySearchQuery(q="ALK")))
    service.create_topic("ALK changes", saved.id)
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

    result = MonitoringConsumer(factory, Settings(), worker_id="history-worker").drain()

    assert result.processed == 0
    assert session.scalar(select(func.count()).select_from(MonitoringAlert)) == 0
    assert session.scalar(select(func.count()).select_from(ProjectionDelivery)) == 0


def test_monitoring_api_requires_human_session_and_exposes_full_workflow(session: Session, tenant: Tenant) -> None:
    user = _user(session, tenant, "api-owner")

    def session_override() -> Generator[Session]:
        yield session

    def principal_override() -> Principal:
        return Principal(tenant.id, user.id, "user", frozenset({"monitoring:read", "monitoring:write"}))

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[require_principal] = principal_override
    try:
        with TestClient(app) as client:
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "   ", "query": {"q": "EGFR"}},
                ).status_code
                == 422
            )
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid query", "query": {"q": "   "}},
                ).status_code
                == 422
            )
            saved_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={"name": "API EGFR", "query": {"q": "EGFR"}, "visibility": "tenant"},
            )
            assert saved_response.status_code == 201
            saved_id = saved_response.json()["id"]
            assert client.get("/api/v1/monitoring/saved-searches").json()[0]["query_json"] == {"q": "EGFR"}
            chemistry_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API aspirin structure",
                    "query_type": "chemistry_search",
                    "query": {
                        "mode": "similarity",
                        "query": "CC(=O)Oc1ccccc1C(=O)O",
                        "threshold": 0.75,
                        "limit": 20,
                    },
                    "visibility": "private",
                },
            )
            assert chemistry_response.status_code == 201
            chemistry_id = chemistry_response.json()["id"]
            assert chemistry_response.json()["query_type"] == "chemistry_search"
            assert (
                client.get(f"/api/v1/monitoring/saved-searches/{chemistry_id}").json()["query_json"]["mode"]
                == "similarity"
            )
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid all pipelines", "query_type": "pipeline_search", "query": {}},
                ).status_code
                == 422
            )
            pipeline_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API EGFR pipelines",
                    "query_type": "pipeline_search",
                    "query": {
                        "q": "EGFR",
                        "global_phase": "phase_2",
                        "display_mode": "landscape",
                        "analysis_dimension": "targets",
                        "analysis_limit": 50,
                    },
                },
            )
            assert pipeline_response.status_code == 201
            assert pipeline_response.json()["query_type"] == "pipeline_search"
            assert pipeline_response.json()["query_json"]["analysis_limit"] == 50
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid all trials", "query_type": "clinical_trial_search", "query": {}},
                ).status_code
                == 422
            )
            trial_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API EGFR trials",
                    "query_type": "clinical_trial_search",
                    "query": {
                        "q": "EGFR",
                        "status": "RECRUITING",
                        "has_results": True,
                        "results_posted_from": "2026-07-01",
                        "results_posted_to": "2026-07-31",
                        "sort_by": "result_evaluation",
                    },
                },
            )
            assert trial_response.status_code == 201
            assert trial_response.json()["query_type"] == "clinical_trial_search"
            assert trial_response.json()["query_json"]["sort_by"] == "result_evaluation"
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid all patents", "query_type": "patent_search", "query": {}},
                ).status_code
                == 422
            )
            patent_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API active patents",
                    "query_type": "patent_search",
                    "query": {
                        "applicant": "Victor Therapeutics",
                        "legal_status": "ACTIVE",
                        "sort_by": "family_identifier",
                    },
                },
            )
            assert patent_response.status_code == 201
            assert patent_response.json()["query_type"] == "patent_search"
            assert patent_response.json()["query_json"]["sort_by"] == "family_identifier"
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid all deals", "query_type": "deal_search", "query": {}},
                ).status_code
                == 422
            )
            deal_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API outbound deals",
                    "query_type": "deal_search",
                    "query": {
                        "status": "active",
                        "direction": "outbound",
                        "currency": "USD",
                        "announced_from": "2026-01-01",
                        "announced_to": "2026-01-31",
                        "upfront_amount_min": 1000000,
                        "sort_by": "upfront_amount",
                    },
                },
            )
            assert deal_response.status_code == 201
            assert deal_response.json()["query_type"] == "deal_search"
            assert deal_response.json()["query_json"]["sort_by"] == "upfront_amount"
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid all regulatory", "query_type": "regulatory_search", "query": {}},
                ).status_code
                == 422
            )
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={
                        "name": "Invalid regulatory dates",
                        "query_type": "regulatory_search",
                        "query": {"agency": "FDA", "decision_from": "2026-03-01", "decision_to": "2026-02-01"},
                    },
                ).status_code
                == 422
            )
            regulatory_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API FDA safety",
                    "query_type": "regulatory_search",
                    "query": {
                        "agency": "FDA",
                        "jurisdiction": "US",
                        "event_type": "safety_signal",
                        "has_boxed_warning": False,
                        "safety_signal_type": "adverse_event",
                        "safety_severity": "serious",
                        "safety_status": "confirmed",
                        "decision_from": "2026-02-01",
                        "decision_to": "2026-02-28",
                        "sort_by": "source_updated_at",
                        "sort_direction": "asc",
                    },
                },
            )
            assert regulatory_response.status_code == 201
            assert regulatory_response.json()["query_type"] == "regulatory_search"
            assert regulatory_response.json()["query_json"]["has_boxed_warning"] is False
            assert regulatory_response.json()["query_json"]["sort_by"] == "source_updated_at"
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid all epidemiology", "query_type": "epidemiology_search", "query": {}},
                ).status_code
                == 422
            )
            epidemiology_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API disease burden",
                    "query_type": "epidemiology_search",
                    "query": {
                        "measure": "prevalence",
                        "geography": "China",
                        "unit": "patients",
                        "period_start_from": "2025-01-01",
                        "period_end_to": "2025-12-31",
                        "sort_by": "value",
                    },
                },
            )
            assert epidemiology_response.status_code == 201
            assert epidemiology_response.json()["query_type"] == "epidemiology_search"
            assert epidemiology_response.json()["query_json"]["sort_by"] == "value"
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={"name": "Invalid all news", "query_type": "news_search", "query": {}},
                ).status_code
                == 422
            )
            assert (
                client.post(
                    "/api/v1/monitoring/saved-searches",
                    json={
                        "name": "Invalid news timeline",
                        "query_type": "news_search",
                        "query": {"q": "EGFR", "display_mode": "timeline"},
                    },
                ).status_code
                == 422
            )
            news_response = client.post(
                "/api/v1/monitoring/saved-searches",
                json={
                    "name": "API research news",
                    "query_type": "news_search",
                    "query": {
                        "event_type": "conference_abstract",
                        "publisher": "ASCO",
                        "venue": "ASCO 2026",
                        "published_from": "2026-01-01",
                        "published_to": "2026-12-31",
                        "content_scope": "research",
                        "display_mode": "timeline",
                        "sort_by": "venue",
                    },
                },
            )
            assert news_response.status_code == 201
            assert news_response.json()["query_type"] == "news_search"
            assert news_response.json()["query_json"]["display_mode"] == "timeline"
            assert client.patch(f"/api/v1/monitoring/saved-searches/{saved_id}", json={}).status_code == 422
            private_response = client.patch(
                f"/api/v1/monitoring/saved-searches/{saved_id}", json={"visibility": "private"}
            )
            assert private_response.status_code == 200
            assert private_response.json()["visibility"] == "private"

            topic_response = client.post(
                "/api/v1/monitoring/topics",
                json={"name": "API topic", "saved_search_id": saved_id},
            )
            assert topic_response.status_code == 201
            topic_id = topic_response.json()["id"]
            assert topic_response.json()["query_version"] == 1
            assert client.patch(f"/api/v1/monitoring/topics/{topic_id}", json={}).status_code == 422
            paused = client.patch(f"/api/v1/monitoring/topics/{topic_id}", json={"active": False})
            assert paused.status_code == 200
            assert paused.json()["active"] is False
            refreshed = client.patch(f"/api/v1/monitoring/topics/{topic_id}", json={"query_version": 1})
            assert refreshed.status_code == 200
            assert refreshed.json()["query_version"] == 1
            assert client.patch(f"/api/v1/monitoring/topics/{topic_id}", json={"query_version": 999}).status_code == 404
            assert client.get("/api/v1/monitoring/alerts").json() == []

        app.dependency_overrides[require_principal] = lambda: Principal(
            tenant.id, "agent-1", "agent", frozenset({"monitoring:read"})
        )
        with TestClient(app) as client:
            assert client.get("/api/v1/monitoring/saved-searches").status_code == 403
    finally:
        app.dependency_overrides.clear()
