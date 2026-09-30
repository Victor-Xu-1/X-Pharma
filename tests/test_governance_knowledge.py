from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pharma_intel.config import Settings
from pharma_intel.governance.model_gateway import (
    ExtractionResponse,
    ModelGatewayError,
    OpenAICompatibleExtractionGateway,
)
from pharma_intel.governance.schemas import (
    ActivityFact,
    Citation,
    ClaimFact,
    DealAssetStageFact,
    DealFact,
    DealPartyRoleFact,
    DealRightFact,
    EntityReference,
    EpidemiologyFact,
    ExtractionEnvelope,
    NewsFact,
    PatentFact,
    PatientPopulationReference,
    ProgramFact,
    ProgramOrganizationFact,
    RegulatoryFact,
    StructureFact,
    TargetEvidenceFact,
    TargetProfileFact,
    TrialEntityRoleFact,
    TrialFact,
    TrialResultDisclosureFact,
)
from pharma_intel.governance.service import (
    DocumentSegment,
    GovernanceError,
    GovernanceService,
    _quote_source_match,
    _should_update_temporal_state,
    governance_policy_manifest,
    governance_policy_sha256,
)
from pharma_intel.intelligence import IntelligenceService
from pharma_intel.knowledge.compiler import KnowledgeCompiler
from pharma_intel.models import (
    ActivityMeasurement,
    Assay,
    ClinicalTrialEntityRole,
    ClinicalTrialProfile,
    ClinicalTrialResultDisclosure,
    CompoundStructure,
    DataSource,
    DataSourceType,
    DealAssetAssociation,
    DealDirection,
    DealPartyAssociation,
    DealPartyRole,
    DealProfile,
    DealRight,
    DealRightType,
    DealStatus,
    DevelopmentProgram,
    DevelopmentProgramOrganization,
    DevelopmentProgramTarget,
    Entity,
    EntityType,
    EpidemiologyObservation,
    EvidenceClaim,
    ExtractionRun,
    FactProvenanceLink,
    GovernanceStatus,
    NewsEvent,
    PatentFamily,
    PatientPopulation,
    PatientPopulationEntityLink,
    RegulatoryEvent,
    Relationship,
    ReviewTask,
    RunState,
    SourceAsset,
    SourceDocument,
    SourceVersion,
    SourceVersionState,
    StagedFact,
    StageStatus,
    TargetEvidenceObservation,
    TargetProfile,
    Tenant,
    TrialEntityRole,
    TrialResultDisclosureType,
    User,
    UserRole,
)
from pharma_intel.object_store import FileSystemObjectStore
from pharma_intel.search.documents import evidence_claim_projection, source_chunk_projections
from pharma_intel.security import hash_password


class StaticGateway(OpenAICompatibleExtractionGateway):
    def __init__(self, envelope: ExtractionEnvelope) -> None:
        self.envelope = envelope

    def extract(
        self,
        document_segment: str,
        *,
        fact_kind_allowlist: frozenset[str] | None = None,
        max_facts: int | None = None,
        source_profile: str | None = None,
    ) -> ExtractionResponse:
        del fact_kind_allowlist, max_facts, source_profile
        assert "EGFR" in document_segment
        return ExtractionResponse(self.envelope, 100, 50)


class SequenceGateway(OpenAICompatibleExtractionGateway):
    def __init__(self, envelopes: list[ExtractionEnvelope]) -> None:
        self.envelopes = iter(envelopes)
        self.calls = 0

    def extract(
        self,
        document_segment: str,
        *,
        fact_kind_allowlist: frozenset[str] | None = None,
        max_facts: int | None = None,
        source_profile: str | None = None,
    ) -> ExtractionResponse:
        del fact_kind_allowlist, max_facts, source_profile
        assert document_segment
        self.calls += 1
        return ExtractionResponse(next(self.envelopes), 100, 50)


class FailingGateway(OpenAICompatibleExtractionGateway):
    def extract(
        self,
        document_segment: str,
        *,
        fact_kind_allowlist: frozenset[str] | None = None,
        max_facts: int | None = None,
        source_profile: str | None = None,
    ) -> ExtractionResponse:
        del fact_kind_allowlist, max_facts, source_profile
        assert document_segment
        raise ModelGatewayError("controlled model failure")


def test_temporal_governance_rejects_undated_and_older_state_regressions() -> None:
    current = datetime(2026, 6, 1, tzinfo=UTC)
    assert _should_update_temporal_state(None, None) is True
    assert _should_update_temporal_state(current, None) is False
    assert _should_update_temporal_state(current, datetime(2026, 5, 31, tzinfo=UTC)) is False
    assert _should_update_temporal_state(current, datetime(2026, 6, 1, tzinfo=UTC)) is True
    assert _should_update_temporal_state(current, datetime(2026, 6, 2, tzinfo=UTC)) is True


def test_ai_facts_are_quote_gated_reviewed_published_and_compiled(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    text = " ".join(
        [
            "EGFR is a receptor tyrosine kinase.",
            "EGFR is a human kinase with UniProt accession P00533.",
            "A 12000-participant lung cancer GWAS found EGFR variant rs121434568 associated with disease risk.",
            "Compound A has the reported SMILES CCO.",
            "Compound A inhibited EGFR with an IC50 of 12 nM.",
            (
                "Compound A entered Phase 2 for lung cancer with Acme Pharma on 2026-06-01 after "
                "starting Phase 1 in China on 2025-03-01 and received IND clearance on 2024-12-15."
            ),
            (
                "NCT00000001 is a randomized Phase 2 trial of Compound A in EGFR-positive lung cancer "
                "with a 61.9% ORR at 24 weeks, recruiting as of 2026-07-20."
            ),
            (
                "WO2026000001, filed by Acme Pharma with A. Inventor and priority from 2024-01-10, was published "
                "on 2026-01-15, granted and active on 2026-06-01, expires on 2044-01-10, and independent claim 1 "
                "covers the composition of Compound A as an EGFR inhibitor."
            ),
            "Acme Pharma licensed Compound A to Beta Bio for USD 100 million.",
            "FDA approved Compound A for lung cancer under NDA 219999 on 2026-07-01.",
            "WHO estimated 815000 prevalent lung cancer patients in China in 2025.",
            "Acme Pharma announced positive Phase 2 data for Compound A at ASCO 2026.",
        ]
    )
    text_bytes = text.encode()
    text_sha = hashlib.sha256(text_bytes).hexdigest()
    store = FileSystemObjectStore(tmp_path / "objects")
    text_object = store.put_bytes(tenant.id, "extracted-text", text_bytes, text_sha, ".txt")
    source = DataSource(
        tenant_id=tenant.id,
        name="Governance Source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path="paper.txt",
        source_uri=str(tmp_path / "paper.txt"),
        file_name="paper.txt",
        extension=".txt",
        processing_mode="parse",
    )
    session.add(asset)
    session.flush()
    document = SourceDocument(
        tenant_id=tenant.id,
        title="EGFR paper",
        source_type="folder",
        source_uri=asset.source_uri,
        content_sha256="a" * 64,
    )
    session.add(document)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256="a" * 64,
        size_bytes=len(text_bytes),
        snapshot_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        extracted_text_object_uri=text_object.uri,
        extracted_text_sha256=text_sha,
        source_document_id=document.id,
        state=SourceVersionState.PARSED,
    )
    session.add(version)
    session.commit()

    target = EntityReference(entity_type=EntityType.TARGET, name="EGFR", external_ids={"HGNC": "3236"})
    compound = EntityReference(entity_type=EntityType.DRUG, name="Compound A")
    disease = EntityReference(entity_type=EntityType.DISEASE, name="Lung cancer")
    acme = EntityReference(entity_type=EntityType.ORGANIZATION, name="Acme Pharma")
    beta = EntityReference(entity_type=EntityType.ORGANIZATION, name="Beta Bio")
    who = EntityReference(entity_type=EntityType.ORGANIZATION, name="World Health Organization")
    envelope = ExtractionEnvelope(
        document_type="journal_article",
        document_summary="EGFR pharmacology",
        facts=[
            ClaimFact(
                fact_kind="claim",
                subject=target,
                predicate="has_target_class",
                value={"value": "receptor tyrosine kinase"},
                citation=Citation(
                    quote="EGFR is a receptor tyrosine kinase.",
                    locator="model-supplied-page=999",
                    confidence=0.99,
                ),
            ),
            TargetProfileFact(
                fact_kind="target_profile",
                subject=target,
                gene_symbol="EGFR",
                uniprot_accession="P00533",
                organism="Homo sapiens",
                target_class="kinase",
                function_summary="Receptor tyrosine kinase.",
                citation=Citation(
                    quote="EGFR is a human kinase with UniProt accession P00533.",
                    confidence=0.99,
                ),
            ),
            TargetEvidenceFact(
                fact_kind="target_evidence",
                record_identifier="EGFR-GWAS-1",
                target=target,
                disease=disease,
                evidence_type="genetic_association",
                direction="supports",
                study_name="EGFR lung cancer GWAS",
                population="East Asian",
                variant="rs121434568",
                effect_size=1.8,
                effect_unit="odds_ratio",
                p_value=1.2e-8,
                sample_size=12000,
                summary="Genetic association supports the EGFR disease hypothesis.",
                observed_at=datetime(2026, 7, 21, tzinfo=UTC),
                citation=Citation(
                    quote=(
                        "A 12000-participant lung cancer GWAS found EGFR variant rs121434568 "
                        "associated with disease risk."
                    ),
                    confidence=0.99,
                ),
            ),
            StructureFact(
                fact_kind="structure",
                subject=compound,
                canonical_smiles="CCO",
                citation=Citation(
                    quote="Compound A has the reported SMILES CCO.",
                    confidence=0.99,
                ),
            ),
            ActivityFact(
                fact_kind="activity",
                compound=compound,
                target=target,
                assay_name="biochemical inhibition",
                reported_type="IC50",
                reported_relation="=",
                reported_value="12",
                reported_units="nM",
                citation=Citation(quote="Compound A inhibited EGFR with an IC50 of 12 nM.", confidence=0.99),
            ),
            ProgramFact(
                fact_kind="program",
                drug=compound,
                target=target,
                indication=disease,
                organizations=[ProgramOrganizationFact(role="originator", entity=acme)],
                phase="Phase 2",
                status="recruiting",
                status_date=datetime(2026, 6, 1, tzinfo=UTC),
                modality="small molecule",
                geography="Global",
                global_phase="phase_2",
                china_phase="phase_1",
                global_phase_started_at=datetime(2026, 6, 1, tzinfo=UTC),
                china_phase_started_at=datetime(2025, 3, 1, tzinfo=UTC),
                development_rights_regions=["Global", "Global"],
                commercialization_rights_regions=["Greater China"],
                program_tags=["first_in_class"],
                status_history=[
                    {
                        "phase": "phase_1",
                        "status": "active",
                        "effective_at": datetime(2025, 3, 1, tzinfo=UTC),
                        "geography": "China",
                    }
                ],
                milestones=[
                    {
                        "milestone_type": "ind_clearance",
                        "title": "IND clearance",
                        "occurred_at": datetime(2024, 12, 15, tzinfo=UTC),
                        "geography": "China",
                    }
                ],
                citation=Citation(
                    quote=(
                        "Compound A entered Phase 2 for lung cancer with Acme Pharma on 2026-06-01 after "
                        "starting Phase 1 in China on 2025-03-01 and received IND clearance on 2024-12-15."
                    ),
                    confidence=0.99,
                ),
            ),
            TrialFact(
                fact_kind="trial",
                trial=EntityReference(entity_type=EntityType.CLINICAL_TRIAL, name="NCT00000001"),
                registry_name="ClinicalTrials.gov",
                registry_id="NCT00000001",
                official_title="Study of Compound A in EGFR-positive lung cancer",
                acronym="COMPOUND-A-201",
                initiation_type="ist",
                therapy_lines=["first_line", "maintenance"],
                overall_status="RECRUITING",
                phases=["PHASE2"],
                study_type="INTERVENTIONAL",
                enrollment=126,
                start_date=datetime(2026, 1, 1, tzinfo=UTC),
                conditions=["Lung cancer"],
                interventions=[{"name": "Compound A", "type": "DRUG", "arm_labels": ["Compound A"]}],
                entity_roles=[
                    TrialEntityRoleFact(role=TrialEntityRole.INVESTIGATIONAL_DRUG, entity=compound),
                    TrialEntityRoleFact(role=TrialEntityRole.INVESTIGATIONAL_TARGET, entity=target),
                ],
                sponsors=[{"name": "Acme Pharma", "sponsor_class": "INDUSTRY"}],
                locations=[{"country": "China", "city": "Shanghai", "status": "RECRUITING"}],
                study_design={
                    "allocation": "RANDOMIZED",
                    "intervention_model": "PARALLEL",
                    "primary_purpose": "TREATMENT",
                    "masking": "DOUBLE",
                    "who_masked": ["PARTICIPANT", "INVESTIGATOR"],
                },
                eligibility={
                    "minimum_age": "18 Years",
                    "maximum_age": "75 Years",
                    "sex": "ALL",
                    "healthy_volunteers": False,
                    "criteria": "Confirmed EGFR-positive lung cancer",
                },
                arms=[
                    {
                        "label": "Compound A",
                        "type": "EXPERIMENTAL",
                        "description": "Compound A once daily",
                        "intervention_names": ["Compound A"],
                    }
                ],
                outcomes=[
                    {
                        "outcome_type": "PRIMARY",
                        "measure": "Objective response rate",
                        "time_frame": "24 weeks",
                        "results": [
                            {
                                "group_label": "Compound A",
                                "value": "61.9",
                                "unit": "%",
                                "participants": 126,
                            }
                        ],
                    }
                ],
                status_history=[
                    {
                        "status": "RECRUITING",
                        "effective_at": datetime(2026, 7, 20, tzinfo=UTC),
                    }
                ],
                result_evaluation="positive",
                result_disclosures=[
                    TrialResultDisclosureFact(
                        disclosure_key="trial-result-1",
                        version=1,
                        disclosure_type=TrialResultDisclosureType.CONFERENCE_PRESENTATION,
                        external_id="ASCO:2026-COMPOUND-A",
                        title="Compound A Phase 2 data presentation",
                        disclosed_at=datetime(2026, 6, 5, tzinfo=UTC),
                        conference_name="ASCO 2026",
                        is_key_result=True,
                        result_evaluation="positive",
                        citation=Citation(
                            quote="Acme Pharma announced positive Phase 2 data for Compound A at ASCO 2026.",
                            confidence=0.99,
                        ),
                    )
                ],
                results_first_posted=datetime(2026, 7, 20, tzinfo=UTC),
                last_update_posted=datetime(2026, 7, 20, tzinfo=UTC),
                linked_entities=[target, compound, disease],
                citation=Citation(
                    quote=(
                        "NCT00000001 is a randomized Phase 2 trial of Compound A in EGFR-positive lung cancer "
                        "with a 61.9% ORR at 24 weeks, recruiting as of 2026-07-20."
                    ),
                    confidence=0.99,
                ),
            ),
            PatentFact(
                fact_kind="patent",
                patent=EntityReference(entity_type=EntityType.PATENT, name="WO2026000001"),
                family_identifier="FAM-WO2026000001",
                title="EGFR inhibitors",
                priority_date=datetime(2024, 1, 10, tzinfo=UTC),
                applicants=["Acme Pharma"],
                inventors=["A. Inventor"],
                publications=[
                    {
                        "publication_number": "WO2026000001",
                        "jurisdiction": "WO",
                        "publication_date": datetime(2026, 1, 15, tzinfo=UTC),
                        "grant_date": datetime(2026, 6, 1, tzinfo=UTC),
                    }
                ],
                legal_status="active",
                legal_status_at=datetime(2026, 6, 1, tzinfo=UTC),
                legal_events=[
                    {
                        "event_type": "grant",
                        "status": "active",
                        "occurred_at": datetime(2026, 6, 1, tzinfo=UTC),
                        "jurisdiction": "WO",
                        "publication_number": "WO2026000001",
                    }
                ],
                independent_claims=[
                    {
                        "claim_number": "1",
                        "claim_type": "composition",
                        "summary": "Composition of Compound A as an EGFR inhibitor.",
                    }
                ],
                expiration_date=datetime(2044, 1, 10, tzinfo=UTC),
                linked_entities=[target, compound],
                citation=Citation(
                    quote=(
                        "WO2026000001, filed by Acme Pharma with A. Inventor and priority from 2024-01-10, was "
                        "published on 2026-01-15, granted and active on 2026-06-01, expires on 2044-01-10, and "
                        "independent claim 1 covers the composition of Compound A as an EGFR inhibitor."
                    ),
                    confidence=0.99,
                ),
            ),
            DealFact(
                fact_kind="deal",
                deal=EntityReference(entity_type=EntityType.TRANSACTION, name="Acme-Beta Compound A license"),
                deal_type="license",
                parties=[acme, beta],
                party_roles=[
                    DealPartyRoleFact(
                        party=acme,
                        role=DealPartyRole.LICENSOR,
                        country_region="US",
                        organization_type="biopharma",
                    ),
                    DealPartyRoleFact(
                        party=beta,
                        role=DealPartyRole.LICENSEE,
                        country_region="China",
                        organization_type="biotech",
                    ),
                ],
                assets=[compound],
                asset_stages=[
                    DealAssetStageFact(
                        asset=compound,
                        development_phase_at_transaction="phase_2",
                    )
                ],
                rights=[
                    DealRightFact(
                        holder=beta,
                        right_type=DealRightType.COMMERCIALIZATION,
                        territory="Greater China",
                        exclusive=True,
                        scope_description="Exclusive commercialization rights",
                    )
                ],
                status=DealStatus.ACTIVE,
                direction=DealDirection.CROSS_BORDER,
                announced_at="2026-06-15T00:00:00Z",
                source_updated_at="2026-06-20T00:00:00Z",
                territory="global",
                total_potential_amount=100_000_000,
                currency="USD",
                terms={"royalties": "tiered", "option": "regional co-development"},
                citation=Citation(
                    quote="Acme Pharma licensed Compound A to Beta Bio for USD 100 million.",
                    confidence=0.99,
                ),
            ),
            RegulatoryFact(
                fact_kind="regulatory",
                subject=compound,
                agency="FDA",
                jurisdiction="US",
                event_identifier="FDA-NDA-219999-APPROVAL-20260701",
                application_number="NDA 219999",
                event_type="approval",
                status="approved",
                title="FDA approval of Compound A for lung cancer",
                decision_date="2026-07-01T00:00:00Z",
                designation_type="breakthrough_therapy",
                label_change_type="initial_label",
                label_version="USPI-2026-07",
                label_effective_at="2026-07-02T00:00:00Z",
                approved_population="Adults with EGFR-positive lung cancer",
                line_of_therapy="first_line",
                biomarker="EGFR mutation",
                route_of_administration="oral",
                dosage_form="tablet",
                has_boxed_warning=True,
                safety_signal_type="adverse_event",
                safety_term="QT prolongation",
                safety_severity="serious",
                safety_status="confirmed",
                safety_identified_at="2026-06-20T00:00:00Z",
                safety_confirmed_at="2026-07-01T00:00:00Z",
                affected_population="Patients with cardiac risk factors",
                risk_actions=["ECG monitoring"],
                source_updated_at="2026-07-03T00:00:00Z",
                indication=disease,
                organization=acme,
                details={"review_pathway": "standard"},
                citation=Citation(
                    quote="FDA approved Compound A for lung cancer under NDA 219999 on 2026-07-01.",
                    confidence=0.99,
                ),
            ),
            EpidemiologyFact(
                fact_kind="epidemiology",
                observation_identifier="WHO-LUNG-CN-PREVALENCE-2025",
                disease=disease,
                measure="prevalence",
                value=815_000,
                lower_bound=790_000,
                upper_bound=840_000,
                unit="patients",
                geography="China",
                population_scope="All residents",
                patient_population=PatientPopulationReference(
                    population_key="lung-cancer-egfr-positive-cn",
                    name="EGFR-positive lung cancer population in China",
                    description="Governed biomarker-defined patient population",
                    targets=[target, target],
                    attributes={"biomarker": "EGFR-positive"},
                ),
                age_group="all ages",
                sex="all",
                period_start="2025-01-01T00:00:00Z",
                period_end="2025-12-31T00:00:00Z",
                sample_size=1_000_000,
                methodology="Modeled national estimate",
                publisher=who,
                citation=Citation(
                    quote="WHO estimated 815000 prevalent lung cancer patients in China in 2025.",
                    confidence=0.99,
                ),
            ),
            NewsFact(
                fact_kind="news",
                event_identifier="ACME-ASCO-2026-COMPOUND-A",
                event_type="corporate_announcement",
                title="Acme Pharma reports positive Phase 2 data for Compound A",
                summary="Positive Phase 2 data were announced at ASCO 2026.",
                published_at="2026-06-05T08:00:00Z",
                language="en",
                publisher=acme,
                related_entities=[compound, target, disease],
                canonical_url="https://example.test/acme/compound-a-phase-2",
                venue="ASCO 2026",
                details={"data_type": "clinical_update"},
                citation=Citation(
                    quote="Acme Pharma announced positive Phase 2 data for Compound A at ASCO 2026.",
                    confidence=0.99,
                ),
            ),
            ClaimFact(
                fact_kind="claim",
                subject=target,
                predicate="has_unverified_stage",
                value={"value": "Phase 3"},
                citation=Citation(quote="This quote does not exist.", confidence=0.99),
            ),
        ],
    )
    settings = Settings(
        ai_governance_enabled=True,
        ai_base_url="https://model.test",
        ai_api_key="test-key",
        ai_model="test-model",
        ai_input_cost_per_million_tokens=2,
        ai_output_cost_per_million_tokens=6,
        ai_max_document_cost=1,
        ai_auto_publish_threshold=0.95,
        object_store_root=tmp_path / "objects",
        markdown_export_root=tmp_path / "wiki",
    )
    service = GovernanceService(
        session,
        settings,
        store,
        tenant.id,
        gateway=StaticGateway(envelope),
    )
    result = service.govern_version(version.id)

    assert result["published"] == 2
    assert result["review_pending"] == 10
    assert result["rejected"] == 1
    extraction_run = session.get(ExtractionRun, result["run_id"])
    assert extraction_run is not None
    assert extraction_run.schema_version == "2.13.0"
    assert float(extraction_run.estimated_cost or 0) == 0.0005
    assert extraction_run.structured_output is not None
    assert extraction_run.structured_output["segments"][0]["quote_verified_count"] == 12
    assert extraction_run.structured_output["segments"][0]["source_start_char"] == 0
    assert extraction_run.structured_output["segments"][0]["source_end_char"] == len(text)
    assert extraction_run.structured_output["budget"]["estimated_cost"] == "0.0005"
    assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 2
    assert session.scalar(select(func.count()).select_from(FactProvenanceLink)) == 3
    assert session.scalar(select(func.count()).select_from(ReviewTask)) == 10

    reviewer = User(
        tenant_id=tenant.id,
        email="reviewer@example.test",
        normalized_email="reviewer@example.test",
        display_name="Reviewer",
        password_hash=hash_password("reviewer-password-for-test"),
        role=UserRole.ANALYST,
    )
    session.add(reviewer)
    session.commit()
    for task in list(session.scalars(select(ReviewTask))):
        service.approve_fact(task.staged_fact_id, reviewer.id, "Source quote verified")

    assert session.scalar(select(func.count()).select_from(EvidenceClaim)) == 12
    assert session.scalar(select(func.count()).select_from(FactProvenanceLink)) == 25

    duplicate_source = DataSource(
        tenant_id=tenant.id,
        name="Duplicate content source",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path / "duplicate"),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
    )
    session.add(duplicate_source)
    session.flush()
    duplicate_asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=duplicate_source.id,
        logical_path="duplicate-paper.txt",
        source_uri=str(tmp_path / "duplicate" / "duplicate-paper.txt"),
        file_name="duplicate-paper.txt",
        extension=".txt",
        processing_mode="parse",
    )
    session.add(duplicate_asset)
    session.flush()
    duplicate_version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=duplicate_asset.id,
        version_number=1,
        content_sha256=version.content_sha256,
        size_bytes=len(text_bytes),
        snapshot_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        extracted_text_object_uri=text_object.uri,
        extracted_text_sha256=text_sha,
        source_document_id=document.id,
        state=SourceVersionState.PARSED,
    )
    session.add(duplicate_version)
    session.flush()
    duplicate_asset.current_version_id = duplicate_version.id
    session.commit()

    published_claim = session.scalar(select(EvidenceClaim).where(EvidenceClaim.predicate == "has_target_class"))
    assert published_claim is not None
    claim_projection = evidence_claim_projection(session, tenant.id, published_claim.id)
    assert claim_projection is not None
    assert claim_projection.source["source_version_id"] == version.id
    assert claim_projection.source["source_asset_id"] == asset.id
    assert claim_projection.source["source_uri"] == asset.source_uri
    _, duplicate_chunks = source_chunk_projections(
        session,
        store,
        settings,
        tenant.id,
        duplicate_version.id,
    )
    assert duplicate_chunks
    assert {chunk.source["source_uri"] for chunk in duplicate_chunks} == {duplicate_asset.source_uri}

    activity_links = set(
        session.scalars(
            select(FactProvenanceLink.resource_type)
            .join(
                StagedFact,
                StagedFact.id == FactProvenanceLink.staged_fact_id,
            )
            .where(StagedFact.fact_kind == "activity")
        )
    )
    assert activity_links == {"activity_measurement", "assay", "evidence_claim"}
    assert session.scalar(select(func.count()).select_from(TargetProfile)) == 1
    governed_target_profile = session.scalar(select(TargetProfile))
    assert governed_target_profile is not None
    assert governed_target_profile.source_document_id == version.source_document_id
    target_evidence = session.scalar(select(TargetEvidenceObservation))
    assert target_evidence is not None
    assert target_evidence.source_record_id == "EGFR-GWAS-1"
    assert target_evidence.evidence_type == "genetic_association"
    assert target_evidence.direction == "supports"
    assert target_evidence.sample_size == 12000
    assert target_evidence.source_document_id == version.source_document_id
    assert session.scalar(select(func.count()).select_from(CompoundStructure)) == 1
    structure = session.scalar(select(CompoundStructure))
    assert structure is not None
    assert structure.canonical_smiles == "CCO"
    assert structure.standard_inchi_key == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert structure.molecular_formula == "C2H6O"
    assert structure.standardization_version.startswith("rdkit-2026.03.3/")
    staged_structure = session.scalar(select(StagedFact).where(StagedFact.fact_kind == "structure"))
    assert staged_structure is not None
    assert staged_structure.raw_payload["standard_inchi_key"] is None
    assert staged_structure.payload["standard_inchi_key"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert staged_structure.normalization_version == structure.standardization_version
    assert session.scalar(select(func.count()).select_from(Assay)) == 1
    assert session.scalar(select(func.count()).select_from(ActivityMeasurement)) == 1
    assert session.scalar(select(func.count()).select_from(DevelopmentProgram)) == 1
    governed_program = session.scalar(select(DevelopmentProgram))
    assert governed_program is not None
    assert governed_program.status_date is not None
    assert governed_program.status_date.replace(tzinfo=UTC) == datetime(2026, 6, 1, tzinfo=UTC)
    assert [event["phase"] for event in governed_program.status_history] == ["phase_1", "phase_2"]
    assert governed_program.status_history[0]["source_document_id"] == version.source_document_id
    assert governed_program.milestones[0]["milestone_type"] == "ind_clearance"
    assert governed_program.milestones[0]["source_document_id"] == version.source_document_id
    assert governed_program.global_phase == "phase_2"
    assert governed_program.china_phase == "phase_1"
    assert governed_program.global_phase_started_at is not None
    assert governed_program.global_phase_started_at.replace(tzinfo=UTC) == datetime(2026, 6, 1, tzinfo=UTC)
    assert governed_program.china_phase_started_at is not None
    assert governed_program.china_phase_started_at.replace(tzinfo=UTC) == datetime(2025, 3, 1, tzinfo=UTC)
    assert governed_program.development_rights_regions == ["Global"]
    assert governed_program.commercialization_rights_regions == ["Greater China"]
    assert governed_program.program_tags == ["first_in_class"]
    assert governed_program.target_set_version == 1
    assert governed_program.target_combination_key == governed_program.target_entity_id
    governed_program_target = session.scalar(select(DevelopmentProgramTarget))
    assert governed_program_target is not None
    assert governed_program_target.program_id == governed_program.id
    assert governed_program_target.target_entity_id == governed_program.target_entity_id
    assert governed_program_target.role.value == "primary"
    assert governed_program_target.position == 0
    governed_program_organization = session.scalar(select(DevelopmentProgramOrganization))
    assert governed_program_organization is not None
    assert governed_program_organization.program_id == governed_program.id
    assert governed_program_organization.organization_entity_id == governed_program.organization_entity_id
    assert governed_program_organization.role == "originator"
    assert governed_program_organization.position == 0
    staged_program = session.scalar(select(StagedFact).where(StagedFact.fact_kind == "program"))
    assert staged_program is not None
    service._materialize_program(staged_program, staged_program.payload)
    session.flush()
    assert session.scalar(select(func.count()).select_from(DevelopmentProgram)) == 1
    assert session.scalar(select(func.count()).select_from(DevelopmentProgramOrganization)) == 1
    assert session.scalar(select(func.count()).select_from(ClinicalTrialProfile)) == 1
    governed_trial = session.scalar(select(ClinicalTrialProfile))
    assert governed_trial is not None
    assert governed_trial.has_results is True
    assert governed_trial.result_evaluation == "positive"
    assert governed_trial.acronym == "COMPOUND-A-201"
    assert governed_trial.initiation_type == "ist"
    assert governed_trial.therapy_lines == ["first_line", "maintenance"]
    assert governed_trial.study_design["allocation"] == "RANDOMIZED"
    assert governed_trial.eligibility["minimum_age"] == "18 Years"
    assert governed_trial.arms[0]["label"] == "Compound A"
    assert governed_trial.outcomes[0]["results"][0]["value"] == "61.9"
    assert governed_trial.status_history[0]["source_document_id"] == version.source_document_id
    assert governed_trial.source_document_id == version.source_document_id
    assert session.scalar(select(func.count()).select_from(ClinicalTrialEntityRole)) == 2
    disclosure = session.scalar(select(ClinicalTrialResultDisclosure))
    assert disclosure is not None
    assert disclosure.disclosure_key == "trial-result-1"
    assert disclosure.is_key_result is True
    assert disclosure.source_quote == "Acme Pharma announced positive Phase 2 data for Compound A at ASCO 2026."
    assert session.scalar(select(func.count()).select_from(PatentFamily)) == 1
    governed_patent = session.scalar(select(PatentFamily))
    assert governed_patent is not None
    assert governed_patent.priority_date is not None
    assert governed_patent.priority_date.replace(tzinfo=UTC) == datetime(2024, 1, 10, tzinfo=UTC)
    assert governed_patent.inventors == ["A. Inventor"]
    assert governed_patent.publications[0]["publication_number"] == "WO2026000001"
    assert governed_patent.publications[0]["publication_date"] == "2026-01-15T00:00:00+00:00"
    assert governed_patent.legal_status_at is not None
    assert governed_patent.legal_status_at.replace(tzinfo=UTC) == datetime(2026, 6, 1, tzinfo=UTC)
    assert governed_patent.legal_events[0]["source_document_id"] == version.source_document_id
    assert governed_patent.independent_claims[0]["claim_type"] == "composition"
    assert governed_patent.independent_claims[0]["source_document_id"] == version.source_document_id
    assert governed_patent.expiration_date is not None
    assert session.scalar(select(func.count()).select_from(DealProfile)) == 1
    governed_deal_profile = session.scalar(select(DealProfile))
    assert governed_deal_profile is not None
    assert governed_deal_profile.announced_at is not None
    assert governed_deal_profile.announced_at.replace(tzinfo=UTC) == datetime(2026, 6, 15, tzinfo=UTC)
    assert governed_deal_profile.status == DealStatus.ACTIVE.value
    assert governed_deal_profile.direction == DealDirection.CROSS_BORDER.value
    assert governed_deal_profile.source_updated_at is not None
    assert governed_deal_profile.source_updated_at.replace(tzinfo=UTC) == datetime(2026, 6, 20, tzinfo=UTC)
    assert governed_deal_profile.terms == {"royalties": "tiered", "option": "regional co-development"}
    deal_parties = session.scalars(select(DealPartyAssociation).order_by(DealPartyAssociation.role)).all()
    assert [(association.role, association.country_region) for association in deal_parties] == [
        (DealPartyRole.LICENSEE.value, "China"),
        (DealPartyRole.LICENSOR.value, "US"),
    ]
    deal_asset = session.scalar(select(DealAssetAssociation))
    assert deal_asset is not None
    assert deal_asset.development_phase_at_transaction == "phase_2"
    deal_right = session.scalar(select(DealRight))
    assert deal_right is not None
    assert deal_right.right_type == DealRightType.COMMERCIALIZATION.value
    assert deal_right.territory == "Greater China"
    assert deal_right.exclusive is True
    regulatory = session.scalar(select(RegulatoryEvent))
    assert regulatory is not None
    assert regulatory.agency == "FDA"
    assert regulatory.application_number == "NDA 219999"
    assert regulatory.designation_type == "breakthrough_therapy"
    assert regulatory.label_change_type == "initial_label"
    assert regulatory.label_version == "USPI-2026-07"
    assert regulatory.has_boxed_warning is True
    assert regulatory.safety_term == "QT prolongation"
    assert regulatory.safety_status == "confirmed"
    assert regulatory.risk_actions == ["ECG monitoring"]
    assert regulatory.source_document_id == version.source_document_id
    epidemiology = session.scalar(select(EpidemiologyObservation))
    assert epidemiology is not None
    assert epidemiology.observation_identifier == "WHO-LUNG-CN-PREVALENCE-2025"
    assert epidemiology.measure == "prevalence"
    assert epidemiology.value == 815_000
    assert epidemiology.lower_bound == 790_000
    assert epidemiology.upper_bound == 840_000
    assert epidemiology.geography == "China"
    assert epidemiology.period_end is not None
    assert epidemiology.period_end.replace(tzinfo=UTC) == datetime(2025, 12, 31, tzinfo=UTC)
    assert epidemiology.source_document_id == version.source_document_id
    population = session.scalar(select(PatientPopulation))
    assert population is not None
    assert epidemiology.patient_population_id == population.id
    assert population.population_key == "lung-cancer-egfr-positive-cn"
    assert population.attributes == {"biomarker": "EGFR-positive"}
    population_links = list(session.scalars(select(PatientPopulationEntityLink)))
    assert {link.relationship for link in population_links} == {"disease", "target"}
    epidemiology_links = set(
        session.scalars(
            select(FactProvenanceLink.resource_type)
            .where(FactProvenanceLink.resource_id == epidemiology.id)
            .order_by(FactProvenanceLink.resource_type)
        )
    )
    assert epidemiology_links == {"epidemiology_observation"}
    population_provenance = set(
        session.scalars(
            select(FactProvenanceLink.resource_type)
            .where(FactProvenanceLink.resource_id == population.id)
            .order_by(FactProvenanceLink.resource_type)
        )
    )
    assert population_provenance == {"patient_population"}
    news_event = session.scalar(select(NewsEvent))
    assert news_event is not None
    assert news_event.event_identifier == "ACME-ASCO-2026-COMPOUND-A"
    assert news_event.publisher_entity_id is not None
    assert news_event.source_document_id == version.source_document_id
    assert news_event.canonical_url == "https://example.test/acme/compound-a-phase-2"
    news_links = set(
        session.scalars(
            select(FactProvenanceLink.resource_type)
            .where(FactProvenanceLink.resource_id == news_event.id)
            .order_by(FactProvenanceLink.resource_type)
        )
    )
    assert news_links == {"news_event"}
    intelligence = IntelligenceService(session, tenant.id)
    assert intelligence.regulatory_events(regulatory.subject_entity_id, "approved", None, 10)[0].id == regulatory.id
    assert intelligence.regulatory_events(None, "US", "FDA", 10)[0].id == regulatory.id
    epidemiology_search = intelligence.search_epidemiology_observations(
        "WHO",
        "prevalence",
        "China",
        "patients",
        "All residents",
        "all ages",
        "all",
        None,
        None,
        10,
        0,
    )
    assert epidemiology_search.total == 1
    assert epidemiology_search.items[0].id == epidemiology.id
    assert epidemiology_search.items[0].patient_population is not None
    assert epidemiology_search.items[0].patient_population.id == population.id
    assert epidemiology_search.patient_populations[0].id == population.id
    epidemiology_trend = intelligence.epidemiology_trend(
        epidemiology.disease_entity_id,
        "prevalence",
        "China",
        "patients",
        "All residents",
        "all ages",
        "all",
        10,
    )
    assert epidemiology_trend is not None
    assert [item.id for item in epidemiology_trend.items] == [epidemiology.id]
    news_search = intelligence.search_news_events("Compound A", None, "Acme", "en", "ASCO 2026", None, None, 10, 0)
    assert news_search.total == 1
    assert news_search.items[0].id == news_event.id
    assert {entity.name for entity in news_search.items[0].related_entities} == {
        "Compound A",
        "EGFR",
        "Lung cancer",
    }
    assert (session.scalar(select(func.count()).select_from(Relationship)) or 0) >= 10
    governed_target = session.scalar(
        select(Entity).where(Entity.tenant_id == tenant.id, Entity.entity_type == EntityType.TARGET)
    )
    assert governed_target is not None
    governed_compound = session.scalar(
        select(Entity).where(Entity.tenant_id == tenant.id, Entity.entity_type == EntityType.DRUG)
    )
    governed_deal = session.scalar(
        select(Entity).where(Entity.tenant_id == tenant.id, Entity.entity_type == EntityType.TRANSACTION)
    )
    assert governed_compound is not None
    assert governed_deal is not None
    relationship_edges = set(
        session.execute(
            select(Relationship.predicate, Relationship.subject_id, Relationship.object_id).where(
                Relationship.tenant_id == tenant.id
            )
        )
    )
    assert ("has_target", governed_compound.id, governed_target.id) in relationship_edges
    assert ("deal_asset", governed_deal.id, governed_compound.id) in relationship_edges
    assert [item.registry_id for item in intelligence.clinical_trials(governed_target.id, None, 10)] == ["NCT00000001"]
    assert [item.family_identifier for item in intelligence.patents(governed_target.id, None, 10)] == [
        "FAM-WO2026000001"
    ]
    assert [item.deal_type for item in intelligence.deals(governed_target.id, 10)] == ["license"]
    assert [item.event_identifier for item in intelligence.regulatory_events(governed_target.id, None, None, 10)] == [
        "FDA-NDA-219999-APPROVAL-20260701"
    ]
    assert [
        item.event_identifier
        for item in intelligence.news_event_search_items(
            governed_target.id,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            10,
        )
    ] == ["ACME-ASCO-2026-COMPOUND-A"]
    dossier = intelligence.entity_dossier(governed_target.id, 10)
    assert dossier is not None
    assert dossier.entity.id == governed_target.id
    dossier_counts = {item.domain: item.total for item in dossier.coverage}
    assert dossier_counts["activities"] == 1
    assert dossier_counts["programs"] == 1
    assert dossier_counts["clinical_trials"] == 1
    assert dossier_counts["patents"] == 1
    assert dossier_counts["deals"] == 1
    assert dossier_counts["regulatory_events"] == 1
    assert dossier_counts["news_events"] == 1
    assert any(item.predicate == "has_target" for item in dossier.relationships)

    claim = session.scalar(select(EvidenceClaim).where(EvidenceClaim.predicate == "has_target_class"))
    assert claim is not None
    staged_claim = next(
        (
            item
            for item in session.scalars(select(StagedFact).where(StagedFact.fact_kind == "claim"))
            if item.payload.get("predicate") == "has_target_class"
        ),
        None,
    )
    assert staged_claim is not None
    assert staged_claim.raw_payload["citation"]["locator"] == "model-supplied-page=999"
    assert staged_claim.source_locator is not None and staged_claim.source_locator.startswith("chars=")
    start, end = (int(value) for value in staged_claim.source_locator.removeprefix("chars=").split("-", 1))
    assert text[start:end] == staged_claim.source_quote
    assert claim.source_locator == staged_claim.source_locator
    compiler = KnowledgeCompiler(session, tenant.id)
    first = compiler.compile_entity(claim.subject_id, run_id="test-governance")
    second = compiler.compile_entity(claim.subject_id, run_id="test-governance-repeat")
    export = compiler.export_page(first.page_id, tmp_path / "wiki")

    assert first.changed is True
    assert second.changed is False
    assert first.content_sha256 == second.content_sha256
    rendered = export.read_text(encoding="utf-8")
    assert "# EGFR" in rendered
    assert "has_target_class" in rendered
    assert "EGFR paper" in rendered


def test_quote_locator_is_server_derived_across_case_and_whitespace() -> None:
    text = "Prefix: EGFR\n  is a receptor tyrosine kinase. Suffix"
    segment = DocumentSegment(text=text, start_char=200, end_char=200 + len(text))

    match = _quote_source_match("  egfr is a receptor tyrosine kinase.  ", segment)

    assert match is not None
    start, end = (int(value) for value in match.locator.removeprefix("chars=").split("-", 1))
    located = text[start - segment.start_char : end - segment.start_char]
    assert match.quote == located
    assert " ".join(located.casefold().split()) == "egfr is a receptor tyrosine kinase."
    assert _quote_source_match("quote absent from source", segment) is None


def test_duplicate_fact_prefers_segment_local_quote_over_higher_unverified_confidence(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    quote = "SECOND evidence quote."
    text = "A" * 2050 + " " + quote
    store, version = _parsed_version(session, tenant, tmp_path, "segment-boundary.txt", text)
    target = EntityReference(entity_type=EntityType.TARGET, name="EGFR")

    def envelope(confidence: float) -> ExtractionEnvelope:
        return ExtractionEnvelope(
            document_type="report",
            document_summary="Segment-local citation test",
            facts=[
                ClaimFact(
                    fact_kind="claim",
                    subject=target,
                    predicate="has_segment_evidence",
                    value={"value": "supported"},
                    citation=Citation(quote=quote, confidence=confidence),
                )
            ],
        )

    gateway = SequenceGateway([envelope(0.99), envelope(0.80)])
    service = GovernanceService(
        session,
        Settings(
            ai_governance_enabled=True,
            ai_base_url="https://model.test",
            ai_api_key="test-key",
            ai_model="test-model",
            ai_max_input_chars=2000,
            ai_max_document_chars=5000,
            ai_max_segments_per_document=2,
            object_store_root=tmp_path / "objects",
        ),
        store,
        tenant.id,
        gateway=gateway,
    )

    result = service.govern_version(version.id)

    staged = session.scalar(select(StagedFact).where(StagedFact.extraction_run_id == result["run_id"]))
    assert gateway.calls == 2
    assert result["review_pending"] == 1
    assert result["rejected"] == 0
    assert staged is not None
    assert staged.status == GovernanceStatus.REVIEW_PENDING
    assert staged.confidence == 0.80
    assert all(item["code"] != "quote_not_found_in_segment" for item in staged.quality_findings)


def test_ai_document_segment_budget_fails_before_any_model_call_and_is_audited(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version = _parsed_version(session, tenant, tmp_path, "oversized.txt", "B" * 3001)
    gateway = SequenceGateway([])
    service = GovernanceService(
        session,
        Settings(
            ai_governance_enabled=True,
            ai_base_url="https://model.test",
            ai_api_key="test-key",
            ai_model="test-model",
            ai_max_input_chars=2000,
            ai_max_document_chars=5000,
            ai_max_segments_per_document=1,
            object_store_root=tmp_path / "objects",
        ),
        store,
        tenant.id,
        gateway=gateway,
    )

    with pytest.raises(GovernanceError, match="segment budget"):
        service.govern_version(version.id)

    run = session.scalar(select(ExtractionRun).where(ExtractionRun.source_version_id == version.id))
    session.refresh(version)
    assert gateway.calls == 0
    assert run is not None
    assert run.status == RunState.FAILED
    assert run.validation_errors[0]["code"] == "governance_budget_error"
    assert run.structured_output is not None
    assert run.structured_output["budget"]["max_segments_per_document"] == 1
    assert version.governance_status == StageStatus.FAILED
    assert version.error_code == "governance_budget_error"


def test_failed_governance_retry_clears_terminal_audit_state_before_model_call(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version = _parsed_version(session, tenant, tmp_path, "retry.txt", "EGFR evidence")
    settings = Settings(
        ai_governance_enabled=True,
        ai_base_url="https://model.test",
        ai_api_key="test-key",
        ai_model="test-model",
        object_store_root=tmp_path / "objects",
    )
    failing = GovernanceService(session, settings, store, tenant.id, gateway=FailingGateway(settings))

    with pytest.raises(ModelGatewayError, match="controlled model failure"):
        failing.govern_version(version.id)

    run = session.scalar(select(ExtractionRun).where(ExtractionRun.source_version_id == version.id))
    assert run is not None
    run_id = run.id
    session.refresh(version)
    assert run.status == RunState.FAILED
    assert run.completed_at is not None
    assert run.structured_output is not None
    assert version.error_code == "governance_model_failed"

    envelope = ExtractionEnvelope(
        document_type="report",
        document_summary="Retry succeeded",
        facts=[],
        warnings=[],
    )

    class InspectingGateway(OpenAICompatibleExtractionGateway):
        def extract(
            self,
            document_segment: str,
            *,
            fact_kind_allowlist: frozenset[str] | None = None,
            max_facts: int | None = None,
            source_profile: str | None = None,
        ) -> ExtractionResponse:
            del fact_kind_allowlist, max_facts, source_profile
            assert document_segment == "EGFR evidence"
            current_run = session.get(ExtractionRun, run_id)
            assert current_run is not None
            session.refresh(current_run)
            session.refresh(version)
            assert current_run.status == RunState.RUNNING
            assert current_run.completed_at is None
            assert current_run.structured_output is None
            assert current_run.validation_errors == []
            assert current_run.input_tokens is None
            assert current_run.output_tokens is None
            assert current_run.estimated_cost is None
            assert version.error_code is None
            assert version.error_message is None
            return ExtractionResponse(envelope, 20, 10)

    result = GovernanceService(
        session,
        settings,
        store,
        tenant.id,
        gateway=InspectingGateway(settings),
    ).govern_version(version.id)

    completed_run = session.get(ExtractionRun, run_id)
    assert completed_run is not None
    session.refresh(completed_run)
    session.refresh(version)
    assert result["run_id"] == completed_run.id
    assert completed_run.status == RunState.SUCCEEDED
    assert completed_run.started_at is not None and completed_run.completed_at is not None
    assert completed_run.completed_at >= completed_run.started_at
    assert version.governance_status == StageStatus.SUCCEEDED


def test_governance_policy_change_creates_a_new_immutable_run_and_same_policy_reuses_it(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    store, version = _parsed_version(session, tenant, tmp_path, "policy-version.txt", "EGFR evidence")
    envelope = ExtractionEnvelope(
        document_type="report",
        document_summary="Policy fingerprint test",
        facts=[],
        warnings=[],
    )
    first_settings = Settings(
        ai_governance_enabled=True,
        ai_base_url="https://model-v1.test",
        ai_api_key="test-key",
        ai_model="extractor-v1",
        object_store_root=tmp_path / "objects",
    )
    first_gateway = SequenceGateway([envelope])
    first = GovernanceService(
        session,
        first_settings,
        store,
        tenant.id,
        gateway=first_gateway,
    ).govern_version(version.id)

    second_settings = Settings(
        ai_governance_enabled=True,
        ai_base_url="https://model-v2.test",
        ai_api_key="rotated-test-key",
        ai_model="extractor-v2",
        ai_auto_publish_threshold=0.99,
        object_store_root=tmp_path / "objects",
    )
    second_gateway = SequenceGateway([envelope])
    second_service = GovernanceService(
        session,
        second_settings,
        store,
        tenant.id,
        gateway=second_gateway,
    )
    second = second_service.govern_version(version.id)
    version.governance_status = StageStatus.FAILED
    version.state = SourceVersionState.GOVERNANCE_PENDING
    version.error_code = "governance_model_failed"
    version.error_message = "provider unavailable after the durable result was stored"
    session.commit()
    repeated = second_service.govern_version(version.id)

    runs = list(
        session.scalars(
            select(ExtractionRun)
            .where(ExtractionRun.source_version_id == version.id)
            .order_by(ExtractionRun.created_at)
        )
    )
    assert first["run_id"] != second["run_id"]
    assert repeated["run_id"] == second["run_id"]
    assert first_gateway.calls == 1
    assert second_gateway.calls == 1
    assert version.governance_status == StageStatus.SUCCEEDED
    assert version.state == SourceVersionState.PARSED
    assert version.error_code is None
    assert len(runs) == 2
    assert runs[0].model_name == "extractor-v1"
    assert runs[1].model_name == "extractor-v2"
    assert runs[0].policy_sha256 != runs[1].policy_sha256
    assert runs[0].status == runs[1].status == RunState.SUCCEEDED


def test_governance_policy_fingerprint_excludes_credentials_but_binds_semantic_controls() -> None:
    baseline = Settings(
        ai_base_url="https://model-gateway.example.test/v1",
        ai_api_key="first-secret",
        ai_model="extractor-v1",
        ai_allowed_response_models_json='["extractor-v1"]',
    )
    rotated = baseline.model_copy(update={"ai_api_key": "rotated-secret"})
    upgraded = baseline.model_copy(update={"ai_auto_publish_threshold": 0.99})

    manifest = governance_policy_manifest(baseline)
    assert governance_policy_sha256(baseline) == governance_policy_sha256(rotated)
    assert governance_policy_sha256(baseline) != governance_policy_sha256(upgraded)
    assert "first-secret" not in str(manifest)
    assert manifest["schema"] == "pharma.governance-policy.v1"
    assert manifest["model_name"] == "extractor-v1"
    assert set(manifest["response_schemas"]) == {"default_sha256", "structure_sha256"}


def test_identity_policy_failure_rolls_back_facts_and_persists_failed_run(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
) -> None:
    text = "Compound A has evidence"
    store, version = _parsed_version(session, tenant, tmp_path, "invalid-identity.txt", text)
    envelope = ExtractionEnvelope(
        document_type="report",
        document_summary="Invalid authority identifier",
        facts=[
            ClaimFact(
                fact_kind="claim",
                subject=EntityReference(
                    entity_type=EntityType.DRUG,
                    name="Compound A",
                    external_ids={"DrugBank": "DB123456"},
                ),
                predicate="has_evidence",
                value={"value": "supported"},
                citation=Citation(quote=text, confidence=1),
            )
        ],
    )
    settings = Settings(
        ai_governance_enabled=True,
        ai_base_url="https://model.test",
        ai_api_key="test-key",
        ai_model="test-model",
        object_store_root=tmp_path / "objects",
    )

    with pytest.raises(GovernanceError, match="Invalid drugbank identifier"):
        GovernanceService(
            session,
            settings,
            store,
            tenant.id,
            gateway=SequenceGateway([envelope]),
        ).govern_version(version.id)

    run = session.scalar(select(ExtractionRun).where(ExtractionRun.source_version_id == version.id))
    assert run is not None
    session.refresh(version)
    staged_count = session.scalar(
        select(func.count()).select_from(StagedFact).where(StagedFact.extraction_run_id == run.id)
    )
    assert run.status == RunState.FAILED
    assert run.validation_errors == [{"code": "governance_policy_error", "message": "Invalid drugbank identifier"}]
    assert run.structured_output is not None
    assert len(run.structured_output["segments"]) == 1
    assert staged_count == 0
    assert version.governance_status == StageStatus.FAILED
    assert version.error_code == "governance_policy_error"


def _parsed_version(
    session: Session,
    tenant: Tenant,
    tmp_path: Path,
    file_name: str,
    text: str,
) -> tuple[FileSystemObjectStore, SourceVersion]:
    text_bytes = text.encode("utf-8")
    text_sha256 = hashlib.sha256(text_bytes).hexdigest()
    store = FileSystemObjectStore(tmp_path / "objects")
    text_object = store.put_bytes(tenant.id, "extracted-text", text_bytes, text_sha256, ".txt")
    source = DataSource(
        tenant_id=tenant.id,
        name=f"Governance {file_name}",
        source_type=DataSourceType.FOLDER,
        root_uri=str(tmp_path),
        owner="Research Operations",
        authorization_scopes=["contract:test-source"],
        dataset_key="literature",
    )
    session.add(source)
    session.flush()
    asset = SourceAsset(
        tenant_id=tenant.id,
        data_source_id=source.id,
        logical_path=file_name,
        source_uri=str(tmp_path / file_name),
        file_name=file_name,
        extension=".txt",
        processing_mode="parse",
    )
    session.add(asset)
    session.flush()
    document = SourceDocument(
        tenant_id=tenant.id,
        title=file_name,
        source_type="folder",
        source_uri=asset.source_uri,
        content_sha256=text_sha256,
    )
    session.add(document)
    session.flush()
    version = SourceVersion(
        tenant_id=tenant.id,
        source_asset_id=asset.id,
        version_number=1,
        content_sha256=text_sha256,
        size_bytes=len(text_bytes),
        snapshot_status=StageStatus.SUCCEEDED,
        parse_status=StageStatus.SUCCEEDED,
        extracted_text_object_uri=text_object.uri,
        extracted_text_sha256=text_sha256,
        source_document_id=document.id,
    )
    session.add(version)
    session.commit()
    return store, version
