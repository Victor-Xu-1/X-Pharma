from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.clinicaltrials_gov import ADAPTER_VERSION, parse_clinicaltrials_gov_snapshot
from pharma_intel.governance.service import GovernanceService
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.models import (
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    DataSource,
    DataSourceType,
    DevelopmentPhase,
    DevelopmentProgram,
    Entity,
    EntityType,
    ExtractionRun,
    GovernanceStatus,
    ReviewStatus,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StagedFact,
    StageStatus,
    Tenant,
    TrialEntityRole,
)
from pharma_intel.object_store import FileSystemObjectStore


def _snapshot() -> bytes:
    payload = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT07672483",
                "briefTitle": "IL-12 GEMys in EGFR-positive solid tumors",
                "officialTitle": "A Study of IL-12 GEMys in EGFR-positive Solid Tumors",
                "acronym": "GEMYS-1",
            },
            "statusModule": {
                "overallStatus": "RECRUITING",
                "startDateStruct": {"date": "2026-04", "type": "ACTUAL"},
                "completionDateStruct": {"date": "2028-12-31", "type": "ESTIMATED"},
                "resultsFirstPostDateStruct": {"date": "2026-07-18", "type": "ACTUAL"},
                "lastUpdatePostDateStruct": {"date": "2026-08-10", "type": "ACTUAL"},
                "statusVerifiedDate": "2026-08",
            },
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": "Example Therapeutics", "class": "INDUSTRY"},
                "collaborators": [{"name": "Example Cancer Center", "class": "OTHER"}],
            },
            "conditionsModule": {"conditions": ["EGFR-positive solid tumor"]},
            "designModule": {
                "studyType": "INTERVENTIONAL",
                "phases": ["PHASE1"],
                "enrollmentInfo": {"count": 42, "type": "ESTIMATED"},
                "designInfo": {
                    "allocation": "NON_RANDOMIZED",
                    "interventionModel": "SINGLE_GROUP",
                    "primaryPurpose": "TREATMENT",
                    "maskingInfo": {"masking": "NONE"},
                },
            },
            "armsInterventionsModule": {
                "armGroups": [
                    {
                        "label": "Experimental arm",
                        "type": "EXPERIMENTAL",
                        "description": "IL-12 GEMys with cetuximab",
                        "interventionNames": ["Biological: IL-12 GEMys", "Drug: Cetuximab"],
                    }
                ],
                "interventions": [
                    {
                        "name": "IL-12 GEMys",
                        "type": "BIOLOGICAL",
                        "armGroupLabels": ["Experimental arm"],
                    },
                    {
                        "name": "Cetuximab",
                        "type": "DRUG",
                        "description": "Administered intravenously",
                        "armGroupLabels": ["Experimental arm"],
                    },
                ],
            },
            "outcomesModule": {
                "primaryOutcomes": [
                    {
                        "measure": "Objective response rate",
                        "description": "Investigator-assessed response",
                        "timeFrame": "24 weeks",
                    }
                ]
            },
            "eligibilityModule": {
                "minimumAge": "18 Years",
                "maximumAge": "80 Years",
                "sex": "ALL",
                "healthyVolunteers": False,
                "eligibilityCriteria": "Confirmed EGFR-positive solid tumor.",
            },
            "contactsLocationsModule": {
                "locations": [
                    {
                        "facility": "Example Cancer Center",
                        "city": "Shanghai",
                        "country": "China",
                        "status": "RECRUITING",
                    }
                ]
            },
        },
        "resultsSection": {
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "type": "PRIMARY",
                        "title": "Objective response rate",
                        "description": "Confirmed responses",
                        "timeFrame": "24 weeks",
                        "unitOfMeasure": "%",
                        "groups": [{"id": "OG000", "title": "Experimental arm"}],
                        "denoms": [{"counts": [{"groupId": "OG000", "value": "40"}]}],
                        "classes": [
                            {
                                "categories": [
                                    {
                                        "measurements": [
                                            {
                                                "groupId": "OG000",
                                                "value": "62.5",
                                                "lowerLimit": "47.0",
                                                "upperLimit": "76.0",
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                        "analyses": [
                            {
                                "statisticalMethod": "Exact binomial",
                                "pValue": "0.01",
                                "paramType": "PROPORTION",
                                "paramValue": "0.625",
                                "ciPctValue": "95",
                                "ciLowerLimit": "0.47",
                                "ciUpperLimit": "0.76",
                            }
                        ],
                    }
                ]
            }
        },
        "hasResults": True,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def test_official_trial_publishes_source_scoped_searchable_condition_and_sponsor_labels(
    session: Session, tenant: Tenant, tmp_path: Path
) -> None:
    store, version = _version(session, tenant, tmp_path)
    service = GovernanceService(session, Settings(ai_governance_enabled=False), store, tenant.id)
    first = service.govern_version(version.id)
    repeated = service.govern_version(version.id)
    assert first["run_id"] == repeated["run_id"]
    entities = list(session.scalars(select(Entity).where(Entity.tenant_id == tenant.id)))
    conditions = [item for item in entities if item.entity_type == EntityType.DISEASE]
    sponsors = [item for item in entities if item.entity_type == EntityType.ORGANIZATION]
    assert [item.name for item in conditions] == ["EGFR-positive solid tumor"]
    assert {item.name for item in sponsors} == {"Example Therapeutics", "Example Cancer Center"}
    assert all(item.attributes["identity_scope"] == "provider_label" for item in conditions + sponsors)
    assert all(item.review_status == ReviewStatus.VERIFIED for item in conditions + sponsors)
    assert not any(item.attributes.get("approved_indication") for item in conditions)
    for label in conditions + sponsors:
        dossier = IntelligenceService(session, tenant.id, include_unpublished=False).entity_dossier(label.id)
        assert dossier is not None
        assert len(dossier.clinical_trials) == 1
        assert next(item.total for item in dossier.coverage if item.domain == "evidence") == 1


def _version(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> tuple[FileSystemObjectStore, SourceVersion]:
    store = FileSystemObjectStore(tmp_path / "objects")
    content = _snapshot()
    digest = hashlib.sha256(content).hexdigest()
    raw = store.put_bytes(tenant.id, "raw", content, digest, ".json")
    extracted = store.put_bytes(tenant.id, "extracted-text", content, digest, ".txt")
    source = DataSource(
        tenant_id=tenant.id,
        name="ClinicalTrials.gov official API",
        source_type=DataSourceType.CLINICALTRIALS_GOV,
        root_uri="https://clinicaltrials.gov/api/v2/studies",
        owner="Clinical Data Operations",
        data_classification="public",
        authorization_scopes=["public:clinicaltrials-gov"],
        dataset_key="clinical_trials",
        include_globs=["studies/*.json"],
        exclude_globs=[],
        routing_rules=[{"query_term": "EGFR", "max_records": 100, "page_size": 100}],
        stable_seconds=0,
        max_file_bytes=1_000_000,
        scan_interval_seconds=86_400,
        expected_freshness_seconds=172_800,
        rate_limit_per_minute=60,
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="studies/NCT07672483.json",
        source_uri="https://clinicaltrials.gov/study/NCT07672483",
        file_name="NCT07672483.json",
        extension=".json",
        processing_mode="parse",
    )
    session.add(asset)
    session.flush()
    document = SourceDocument(
        tenant_id=tenant.id,
        title=asset.file_name,
        source_type="clinicaltrials_gov",
        source_uri=asset.source_uri,
        content_sha256=digest,
    )
    session.add(document)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=digest,
        size_bytes=len(content),
        snapshot_status=StageStatus.SUCCEEDED,
        malware_scan_status=StageStatus.SKIPPED,
        parse_status=StageStatus.SUCCEEDED,
        raw_object_uri=raw.uri,
        extracted_text_object_uri=extracted.uri,
        extracted_text_sha256=digest,
        source_document_id=document.id,
        state=SourceVersionState.PARSED,
    )
    session.add(version)
    session.commit()
    return store, version


def test_official_snapshot_parser_preserves_structured_trial_and_results() -> None:
    record = parse_clinicaltrials_gov_snapshot(_snapshot())

    fact = record.fact
    assert fact.registry_id == "NCT07672483"
    assert fact.official_title == "A Study of IL-12 GEMys in EGFR-positive Solid Tumors"
    assert fact.phases == ["PHASE1"]
    assert fact.start_date_precision == "month"
    assert fact.conditions == ["EGFR-positive solid tumor"]
    assert [item.name for item in fact.interventions] == ["IL-12 GEMys", "Cetuximab"]
    assert fact.arms[0].intervention_names == ["IL-12 GEMys", "Cetuximab"]
    assert fact.outcomes[0].results[0].value == "62.5"
    assert fact.outcomes[0].results[0].participants == 40
    assert fact.outcomes[0].statistical_analyses[0].p_value == "0.01"
    assert fact.result_disclosures[0].disclosure_type.value == "registry_result"
    assert fact.citation.confidence == 1


def test_official_governance_bypasses_llm_publishes_and_links_target_pipeline(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version = _version(session, tenant, tmp_path)
    target = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.TARGET,
        name="EGFR",
        normalized_name="egfr",
        review_status=ReviewStatus.VERIFIED,
    )
    verified_drug = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.DRUG,
        name="Cetuximab",
        normalized_name="cetuximab",
        review_status=ReviewStatus.VERIFIED,
    )
    program_drug = Entity(
        tenant_id=tenant.id,
        entity_type=EntityType.DRUG,
        name="CETUXIMAB",
        normalized_name="cetuximab",
        review_status=ReviewStatus.DRAFT,
    )
    session.add_all([target, verified_drug, program_drug])
    session.flush()
    session.add(
        DevelopmentProgram(
            tenant_id=tenant.id,
            drug_entity_id=program_drug.id,
            target_entity_id=target.id,
            phase=DevelopmentPhase.APPROVED,
        )
    )
    session.commit()
    session.autoflush = False

    service = GovernanceService(
        session,
        Settings(
            ai_governance_enabled=True,
            ai_base_url="https://model.test",
            ai_api_key="must-not-be-called",
            ai_model="must-not-be-called",
            object_store_root=tmp_path / "objects",
        ),
        store,
        tenant.id,
    )

    first = service.govern_version(version.id)
    repeated = service.govern_version(version.id)

    assert first["run_id"] == repeated["run_id"]
    assert first["published"] == 1
    assert first["review_pending"] == first["rejected"] == first["conflict"] == 0
    run = session.get(ExtractionRun, first["run_id"])
    assert run is not None
    assert run.model_provider == "deterministic-adapter"
    assert run.model_name == f"clinicaltrials_gov_v2:{ADAPTER_VERSION}"
    trial = session.scalar(select(ClinicalTrialProfile).where(ClinicalTrialProfile.registry_id == "NCT07672483"))
    assert trial is not None
    assert trial.has_results is True
    assert trial.conditions == ["EGFR-positive solid tumor"]
    role = session.scalar(select(ClinicalTrialEntityRole).where(ClinicalTrialEntityRole.trial_id == trial.id))
    assert role is None  # Registered intervention order does not establish investigational/combination roles.
    legacy_role = ClinicalTrialEntityRole(
        tenant_id=tenant.id,
        trial_id=trial.id,
        entity_id=verified_drug.id,
        role=TrialEntityRole.INVESTIGATIONAL_DRUG.value,
        source_document_id=version.source_document_id,
    )
    session.add(legacy_role)
    session.commit()
    public_trial = IntelligenceService(session, tenant.id, include_unpublished=False).clinical_trial_detail(trial.id)
    assert public_trial is not None and public_trial.entity_roles == []
    assert session.get(ClinicalTrialEntityRole, legacy_role.id) is not None  # Retained, not deleted.
    assert session.scalar(select(func.count()).select_from(ReviewTask)) == 0
    assert version.state == SourceVersionState.PUBLISHED

    intelligence = IntelligenceService(session, tenant.id, include_unpublished=False)
    assert [item.registry_id for item in intelligence.clinical_trials(target.id, None, 10)] == ["NCT07672483"]
    assert intelligence.competitive_programs(target.id, 10)[0].clinical_trial_count == 1
    search = intelligence.search_programs(
        "Cetuximab",
        None,
        None,
        None,
        10,
        0,
        target_entity_id=target.id,
    )
    assert search.total == 1
    assert search.items[0].drug_entity_id == verified_drug.id
    assert search.items[0].clinical_trial_count == 1


def test_authoritative_adapter_withdraws_stale_unpublished_llm_fact(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version = _version(session, tenant, tmp_path)
    record = parse_clinicaltrials_gov_snapshot(_snapshot())
    old_run = ExtractionRun(
        tenant_id=tenant.id,
        source_version_id=version.id,
        schema_name="pharma_document_facts",
        schema_version="legacy",
        model_provider="openai-compatible",
        model_name="legacy-model",
        prompt_sha256="1" * 64,
        policy_sha256="2" * 64,
        input_sha256=version.content_sha256,
        status=RunState.SUCCEEDED,
    )
    session.add(old_run)
    session.flush()
    old_fact = StagedFact(
        tenant_id=tenant.id,
        extraction_run_id=old_run.id,
        fact_kind="trial",
        fact_key=hashlib.sha256(
            json.dumps(
                {"kind": "trial", "registry": "clinicaltrials.gov", "id": "nct07672483"},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        raw_payload=record.fact.model_dump(mode="json"),
        payload=record.fact.model_dump(mode="json"),
        source_document_id=version.source_document_id,
        source_quote="NCT07672483",
        confidence=0.99,
        status=GovernanceStatus.REVIEW_PENDING,
    )
    session.add(old_fact)
    session.flush()
    old_task = ReviewTask(
        tenant_id=tenant.id,
        staged_fact_id=old_fact.id,
        status=GovernanceStatus.REVIEW_PENDING,
        reasons=[{"code": "policy_review", "message": "Legacy model fact requires review"}],
    )
    session.add(old_task)
    session.commit()

    GovernanceService(
        session,
        Settings(
            ai_governance_enabled=True,
            ai_base_url="https://model.test",
            ai_api_key="must-not-be-called",
            ai_model="must-not-be-called",
            object_store_root=tmp_path / "objects",
        ),
        store,
        tenant.id,
    ).govern_version(version.id)

    session.refresh(old_fact)
    session.refresh(old_task)
    assert old_fact.status == GovernanceStatus.WITHDRAWN
    assert old_task.status == GovernanceStatus.WITHDRAWN
    assert "authoritative" in (old_task.decision_notes or "").casefold()


def test_official_trial_does_not_guess_an_ambiguous_verified_drug_identity(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version = _version(session, tenant, tmp_path)
    session.add_all(
        [
            Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.DRUG,
                name="Cetuximab",
                normalized_name="cetuximab",
                review_status=ReviewStatus.VERIFIED,
            ),
            Entity(
                tenant_id=tenant.id,
                entity_type=EntityType.DRUG,
                name="Cetuximab",
                normalized_name="cetuximab",
                review_status=ReviewStatus.VERIFIED,
            ),
        ]
    )
    session.commit()

    result = GovernanceService(
        session,
        Settings(
            ai_governance_enabled=True,
            ai_base_url="https://model.test",
            ai_api_key="must-not-be-called",
            ai_model="must-not-be-called",
            object_store_root=tmp_path / "objects",
        ),
        store,
        tenant.id,
    ).govern_version(version.id)

    assert result["published"] == 1
    assert session.scalar(select(func.count()).select_from(ClinicalTrialEntityRole)) == 0
