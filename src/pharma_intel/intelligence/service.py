from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from pharma_intel.intelligence.bioactivity import bioactivities as query_bioactivities
from pharma_intel.intelligence.bioactivity import bioactivities_for_entity as query_bioactivities_for_entity
from pharma_intel.intelligence.bioactivity import sar_comparison as query_sar_comparison
from pharma_intel.intelligence.bioactivity import target_evidence_for_entity as query_target_evidence_for_entity
from pharma_intel.intelligence.clinical_read import clinical_trial_detail as query_clinical_trial_detail
from pharma_intel.intelligence.clinical_read import clinical_trial_search_items as query_clinical_trial_search_items
from pharma_intel.intelligence.clinical_read import clinical_trials as query_clinical_trials
from pharma_intel.intelligence.clinical_search import (
    clinical_trial_saved_search_matches_entity as query_clinical_trial_saved_search_matches_entity,
)
from pharma_intel.intelligence.clinical_search import search_clinical_trials as query_search_clinical_trials
from pharma_intel.intelligence.company_dossier import company_dossier as query_company_dossier
from pharma_intel.intelligence.company_timeline import company_timeline as query_company_timeline
from pharma_intel.intelligence.context import QueryContext
from pharma_intel.intelligence.deal_read import deal_detail as query_deal_detail
from pharma_intel.intelligence.deal_read import deal_search_items as query_deal_search_items
from pharma_intel.intelligence.deal_read import deals as query_deals
from pharma_intel.intelligence.deal_search import (
    deal_saved_search_matches_entity as query_deal_saved_search_matches_entity,
)
from pharma_intel.intelligence.deal_search import search_deals as query_search_deals
from pharma_intel.intelligence.disease_dossier import disease_dossier as query_disease_dossier
from pharma_intel.intelligence.drug_dossier import drug_comparison_profiles as query_drug_comparison_profiles
from pharma_intel.intelligence.drug_dossier import drug_dossier as query_drug_dossier
from pharma_intel.intelligence.entity_dossier import entity_dossier as query_entity_dossier
from pharma_intel.intelligence.entity_dossier import relationships as query_relationships
from pharma_intel.intelligence.epidemiology import (
    epidemiology_saved_search_matches_entity as query_epidemiology_saved_search_matches_entity,
)
from pharma_intel.intelligence.epidemiology import epidemiology_search_items as query_epidemiology_search_items
from pharma_intel.intelligence.epidemiology import epidemiology_trend as query_epidemiology_trend
from pharma_intel.intelligence.epidemiology import (
    search_epidemiology_observations as query_search_epidemiology_observations,
)
from pharma_intel.intelligence.news import news_event_detail as query_news_event_detail
from pharma_intel.intelligence.news import news_event_search_items as query_news_event_search_items
from pharma_intel.intelligence.news import news_saved_search_matches_entity as query_news_saved_search_matches_entity
from pharma_intel.intelligence.news import search_news_events as query_search_news_events
from pharma_intel.intelligence.patents import patent_family_detail as query_patent_family_detail
from pharma_intel.intelligence.patents import (
    patent_saved_search_matches_entity as query_patent_saved_search_matches_entity,
)
from pharma_intel.intelligence.patents import patent_search_items as query_patent_search_items
from pharma_intel.intelligence.patents import patents as query_patents
from pharma_intel.intelligence.patents import search_patent_families as query_search_patent_families
from pharma_intel.intelligence.pipeline_filters import (
    program_saved_search_matches_entity as query_program_saved_search_matches_entity,
)
from pharma_intel.intelligence.pipeline_read import competitive_programs as query_competitive_programs
from pharma_intel.intelligence.pipeline_read import drug_programs as query_drug_programs
from pharma_intel.intelligence.pipeline_read import programs_for_entity as query_programs_for_entity
from pharma_intel.intelligence.pipeline_search import search_programs as query_search_programs
from pharma_intel.intelligence.regulatory import regulatory_event_detail as query_regulatory_event_detail
from pharma_intel.intelligence.regulatory import regulatory_events as query_regulatory_events
from pharma_intel.intelligence.regulatory import (
    regulatory_saved_search_matches_entity as query_regulatory_saved_search_matches_entity,
)
from pharma_intel.intelligence.regulatory import regulatory_search_items as query_regulatory_search_items
from pharma_intel.intelligence.regulatory import search_regulatory_events as query_search_regulatory_events
from pharma_intel.intelligence.structures import structures as query_structures
from pharma_intel.intelligence.structures import structures_for_target as query_structures_for_target
from pharma_intel.intelligence.target_dossier import target_dossier as query_target_dossier
from pharma_intel.intelligence.target_dossier import target_profile as query_target_profile
from pharma_intel.schemas import (
    BioactivityRead,
    ClinicalTrialDetailRead,
    ClinicalTrialRead,
    ClinicalTrialSavedSearchQuery,
    ClinicalTrialSearchItemRead,
    ClinicalTrialSearchResult,
    ClinicalTrialSortField,
    CompanyDossierResponse,
    CompanyTimelineResult,
    CompetitiveProgramRead,
    CompoundStructureRead,
    DealAnalysisLimit,
    DealRead,
    DealSavedSearchQuery,
    DealSearchItemRead,
    DealSearchResult,
    DealSortField,
    DiseaseDossierResponse,
    DrugComparisonResult,
    DrugDossierResponse,
    DrugProgramSearchResult,
    EntityDossierResponse,
    EntityRelationshipRead,
    EpidemiologyObservationSearchItemRead,
    EpidemiologyObservationSearchResult,
    EpidemiologySavedSearchQuery,
    EpidemiologySortField,
    EpidemiologyTrendResult,
    NewsEventSearchItemRead,
    NewsEventSearchResult,
    NewsSavedSearchQuery,
    NewsSortField,
    PatentFamilyRead,
    PatentFamilySearchItemRead,
    PatentFamilySearchResult,
    PatentSavedSearchQuery,
    PatentSortField,
    PipelineLandscapeStageScope,
    PipelineResultGrain,
    PipelineSavedSearchQuery,
    PipelineSearchResult,
    PipelineSortField,
    PipelineTargetAggregation,
    RegulatoryEventRead,
    RegulatoryEventSearchItemRead,
    RegulatoryEventSearchResult,
    RegulatorySavedSearchQuery,
    RegulatorySortField,
    SarComparisonResult,
    SortDirection,
    TargetDossierResponse,
    TargetEvidenceRead,
    TargetProfileResponse,
)
from pharma_intel.sorting import SortClause


class IntelligenceService:
    """Typed public facade over one request context and domain-owned SQL queries."""

    def __init__(self, session: Session, tenant_id: str, *, include_unpublished: bool = True) -> None:
        self.context = QueryContext(session, tenant_id, include_unpublished)

    def target_profile(self, entity_id: str) -> TargetProfileResponse | None:
        return query_target_profile(self.context, entity_id)

    def target_dossier(self, entity_id: str, limit: int = 50) -> TargetDossierResponse | None:
        return query_target_dossier(self.context, entity_id, limit)

    def drug_dossier(self, entity_id: str, limit: int = 100) -> DrugDossierResponse | None:
        return query_drug_dossier(self.context, entity_id, limit)

    def drug_programs(self, entity_id: str, limit: int, offset: int = 0) -> DrugProgramSearchResult | None:
        """Return the complete drug portfolio through a bounded page."""
        return query_drug_programs(self.context, entity_id, limit, offset)

    def drug_comparison_profiles(self, entity_ids: Sequence[str]) -> DrugComparisonResult:
        """Aggregate complete development profiles for a bounded drug batch.

        The comparison workspace must not infer portfolio-level dimensions from the
        truncated record lists in a generic dossier. This method keeps the request
        count independent of the number of compared drugs and computes every metric
        over the complete authorized program set.
        """
        return query_drug_comparison_profiles(self.context, entity_ids)

    def company_dossier(self, entity_id: str, limit: int = 100) -> CompanyDossierResponse | None:
        return query_company_dossier(self.context, entity_id, limit)

    def disease_dossier(self, entity_id: str, limit: int = 100) -> DiseaseDossierResponse | None:
        return query_disease_dossier(self.context, entity_id, limit)

    def entity_dossier(self, entity_id: str, limit: int = 50) -> EntityDossierResponse | None:
        return query_entity_dossier(self.context, entity_id, limit)

    def relationships(self, entity_id: str, limit: int, offset: int = 0) -> list[EntityRelationshipRead]:
        return query_relationships(self.context, entity_id, limit, offset)

    def target_evidence_for_entity(
        self,
        entity_id: str,
        limit: int,
        offset: int = 0,
        *,
        evidence_type: str | None = None,
        direction: str | None = None,
        disease_entity_id: str | None = None,
    ) -> list[TargetEvidenceRead]:
        return query_target_evidence_for_entity(
            self.context,
            entity_id,
            limit,
            offset,
            evidence_type=evidence_type,
            direction=direction,
            disease_entity_id=disease_entity_id,
        )

    def bioactivities(
        self, target_entity_id: str, standard_type: str | None, limit: int, offset: int = 0
    ) -> list[BioactivityRead]:
        return query_bioactivities(self.context, target_entity_id, standard_type, limit, offset)

    def bioactivities_for_entity(
        self, entity_id: str, standard_type: str | None, limit: int, offset: int = 0
    ) -> list[BioactivityRead]:
        return query_bioactivities_for_entity(self.context, entity_id, standard_type, limit, offset)

    def sar_comparison(
        self,
        target_entity_id: str,
        *,
        standard_type: str | None,
        assay_type: str | None,
        assay_format: str | None,
        organism: str | None,
        cell_line: str | None,
        limit: int,
        offset: int,
    ) -> SarComparisonResult:
        return query_sar_comparison(
            self.context,
            target_entity_id,
            standard_type=standard_type,
            assay_type=assay_type,
            assay_format=assay_format,
            organism=organism,
            cell_line=cell_line,
            limit=limit,
            offset=offset,
        )

    def competitive_programs(self, target_entity_id: str, limit: int, offset: int = 0) -> list[CompetitiveProgramRead]:
        return query_competitive_programs(self.context, target_entity_id, limit, offset)

    def program_saved_search_matches_entity(self, entity_id: str, query: PipelineSavedSearchQuery) -> bool:
        return query_program_saved_search_matches_entity(self.context, entity_id, query)

    def search_programs(
        self,
        query: str | None,
        modality: list[str] | None,
        phase: str | None,
        geography: str | None,
        limit: int,
        offset: int,
        *,
        innovation_type: list[str] | None = None,
        therapeutic_area: list[str] | None = None,
        drug_category: list[str] | None = None,
        program_status: str | None = None,
        organization_role: str | None = None,
        organization_type: str | None = None,
        organization_country_region: str | None = None,
        status_date_from: datetime | None = None,
        status_date_to: datetime | None = None,
        drug_entity_id: str | None = None,
        target_entity_id: str | None = None,
        target_combination_key: str | None = None,
        disease_entity_id: str | None = None,
        organization_entity_id: str | None = None,
        global_phase: str | None = None,
        china_phase: str | None = None,
        global_phase_started_from: datetime | None = None,
        global_phase_started_to: datetime | None = None,
        china_phase_started_from: datetime | None = None,
        china_phase_started_to: datetime | None = None,
        development_rights_region: str | None = None,
        commercialization_rights_region: str | None = None,
        program_tag: list[str] | None = None,
        milestone_type: str | None = None,
        milestone_from: datetime | None = None,
        milestone_to: datetime | None = None,
        has_clinical_results: bool | None = None,
        clinical_result_evaluation: str | None = None,
        has_deal: bool | None = None,
        deal_currency: str | None = None,
        deal_total_potential_amount_min: float | None = None,
        deal_total_potential_amount_max: float | None = None,
        sort_by: PipelineSortField = "status_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[PipelineSortField]] | None = None,
        landscape_limit: int = 20,
        landscape_stage_scope: PipelineLandscapeStageScope = "overall",
        landscape_target_aggregation: PipelineTargetAggregation = "all",
        result_grain: PipelineResultGrain = "program",
    ) -> PipelineSearchResult:
        return query_search_programs(
            self.context,
            query,
            modality,
            phase,
            geography,
            limit,
            offset,
            innovation_type=innovation_type,
            therapeutic_area=therapeutic_area,
            drug_category=drug_category,
            program_status=program_status,
            organization_role=organization_role,
            organization_type=organization_type,
            organization_country_region=organization_country_region,
            status_date_from=status_date_from,
            status_date_to=status_date_to,
            drug_entity_id=drug_entity_id,
            target_entity_id=target_entity_id,
            target_combination_key=target_combination_key,
            disease_entity_id=disease_entity_id,
            organization_entity_id=organization_entity_id,
            global_phase=global_phase,
            china_phase=china_phase,
            global_phase_started_from=global_phase_started_from,
            global_phase_started_to=global_phase_started_to,
            china_phase_started_from=china_phase_started_from,
            china_phase_started_to=china_phase_started_to,
            development_rights_region=development_rights_region,
            commercialization_rights_region=commercialization_rights_region,
            program_tag=program_tag,
            milestone_type=milestone_type,
            milestone_from=milestone_from,
            milestone_to=milestone_to,
            has_clinical_results=has_clinical_results,
            clinical_result_evaluation=clinical_result_evaluation,
            has_deal=has_deal,
            deal_currency=deal_currency,
            deal_total_potential_amount_min=deal_total_potential_amount_min,
            deal_total_potential_amount_max=deal_total_potential_amount_max,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
            landscape_limit=landscape_limit,
            landscape_stage_scope=landscape_stage_scope,
            landscape_target_aggregation=landscape_target_aggregation,
            result_grain=result_grain,
        )

    def programs_for_entity(self, entity_id: str, limit: int, offset: int = 0) -> list[CompetitiveProgramRead]:
        return query_programs_for_entity(self.context, entity_id, limit, offset)

    def structures(
        self,
        entity_id: str | None,
        inchi_key: str | None,
        limit: int,
        offset: int = 0,
    ) -> list[CompoundStructureRead]:
        return query_structures(self.context, entity_id, inchi_key, limit, offset)

    def structures_for_target(
        self,
        target_entity_id: str,
        limit: int,
        offset: int = 0,
    ) -> list[CompoundStructureRead]:
        """Return structures for compounds connected to a target through governed data.

        Target dossiers must expose compound structures through activity and pipeline
        relationships; a structure row is owned by its compound entity, not by the
        target. Direct target-owned rows remain readable for legacy imports.
        """
        return query_structures_for_target(self.context, target_entity_id, limit, offset)

    def clinical_trials(
        self,
        entity_id: str | None,
        query: str | None,
        limit: int,
        offset: int = 0,
        registry: str | None = None,
        overall_status: str | None = None,
        phase: str | None = None,
        study_type: str | None = None,
        has_results: bool | None = None,
    ) -> list[ClinicalTrialRead]:
        return query_clinical_trials(
            self.context, entity_id, query, limit, offset, registry, overall_status, phase, study_type, has_results
        )

    def clinical_trial_saved_search_matches_entity(
        self,
        entity_id: str,
        query: ClinicalTrialSavedSearchQuery,
    ) -> bool:
        return query_clinical_trial_saved_search_matches_entity(self.context, entity_id, query)

    def search_clinical_trials(
        self,
        query: str | None,
        registry: str | None,
        overall_status: str | None,
        phase: str | None,
        study_type: str | None,
        has_results: bool | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        results_posted_from: datetime | None = None,
        results_posted_to: datetime | None = None,
        result_evaluation: str | None = None,
        acronym: str | None = None,
        initiation_type: str | None = None,
        therapy_line: str | None = None,
        investigational_drug: str | None = None,
        combination_drug: str | None = None,
        investigational_target: str | None = None,
        combination_target: str | None = None,
        investigational_drug_entity_ids: list[str] | None = None,
        combination_drug_entity_ids: list[str] | None = None,
        investigational_target_entity_ids: list[str] | None = None,
        combination_target_entity_ids: list[str] | None = None,
        linked_drug_modality: list[str] | None = None,
        linked_drug_innovation_type: list[str] | None = None,
        linked_drug_category: list[str] | None = None,
        linked_drug_program_tag: list[str] | None = None,
        linked_drug_global_phase: str | None = None,
        linked_drug_organization_country_region: str | None = None,
        role_entity_id: str | None = None,
        role_entity_ids: list[str] | None = None,
        role_entity_role: str | None = None,
        has_key_result: bool | None = None,
        publication_id: str | None = None,
        conference: str | None = None,
        disclosed_from: datetime | None = None,
        disclosed_to: datetime | None = None,
        sort_by: ClinicalTrialSortField = "last_update_posted",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[ClinicalTrialSortField]] | None = None,
    ) -> ClinicalTrialSearchResult:
        return query_search_clinical_trials(
            self.context,
            query,
            registry,
            overall_status,
            phase,
            study_type,
            has_results,
            limit,
            offset,
            entity_id=entity_id,
            results_posted_from=results_posted_from,
            results_posted_to=results_posted_to,
            result_evaluation=result_evaluation,
            acronym=acronym,
            initiation_type=initiation_type,
            therapy_line=therapy_line,
            investigational_drug=investigational_drug,
            combination_drug=combination_drug,
            investigational_target=investigational_target,
            combination_target=combination_target,
            investigational_drug_entity_ids=investigational_drug_entity_ids,
            combination_drug_entity_ids=combination_drug_entity_ids,
            investigational_target_entity_ids=investigational_target_entity_ids,
            combination_target_entity_ids=combination_target_entity_ids,
            linked_drug_modality=linked_drug_modality,
            linked_drug_innovation_type=linked_drug_innovation_type,
            linked_drug_category=linked_drug_category,
            linked_drug_program_tag=linked_drug_program_tag,
            linked_drug_global_phase=linked_drug_global_phase,
            linked_drug_organization_country_region=linked_drug_organization_country_region,
            role_entity_id=role_entity_id,
            role_entity_ids=role_entity_ids,
            role_entity_role=role_entity_role,
            has_key_result=has_key_result,
            publication_id=publication_id,
            conference=conference,
            disclosed_from=disclosed_from,
            disclosed_to=disclosed_to,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def clinical_trial_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        registry: str | None,
        overall_status: str | None,
        phase: str | None,
        study_type: str | None,
        has_results: bool | None,
        limit: int,
        offset: int = 0,
        *,
        results_posted_from: datetime | None = None,
        results_posted_to: datetime | None = None,
        result_evaluation: str | None = None,
        acronym: str | None = None,
        initiation_type: str | None = None,
        therapy_line: str | None = None,
        investigational_drug: str | None = None,
        combination_drug: str | None = None,
        investigational_target: str | None = None,
        combination_target: str | None = None,
        investigational_drug_entity_ids: list[str] | None = None,
        combination_drug_entity_ids: list[str] | None = None,
        investigational_target_entity_ids: list[str] | None = None,
        combination_target_entity_ids: list[str] | None = None,
        linked_drug_modality: list[str] | None = None,
        linked_drug_innovation_type: list[str] | None = None,
        linked_drug_category: list[str] | None = None,
        linked_drug_program_tag: list[str] | None = None,
        linked_drug_global_phase: str | None = None,
        linked_drug_organization_country_region: str | None = None,
        role_entity_id: str | None = None,
        role_entity_ids: list[str] | None = None,
        role_entity_role: str | None = None,
        has_key_result: bool | None = None,
        publication_id: str | None = None,
        conference: str | None = None,
        disclosed_from: datetime | None = None,
        disclosed_to: datetime | None = None,
        sort_by: ClinicalTrialSortField = "last_update_posted",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[ClinicalTrialSortField]] | None = None,
    ) -> list[ClinicalTrialSearchItemRead]:
        return query_clinical_trial_search_items(
            self.context,
            entity_id,
            query,
            registry,
            overall_status,
            phase,
            study_type,
            has_results,
            limit,
            offset,
            results_posted_from=results_posted_from,
            results_posted_to=results_posted_to,
            result_evaluation=result_evaluation,
            acronym=acronym,
            initiation_type=initiation_type,
            therapy_line=therapy_line,
            investigational_drug=investigational_drug,
            combination_drug=combination_drug,
            investigational_target=investigational_target,
            combination_target=combination_target,
            investigational_drug_entity_ids=investigational_drug_entity_ids,
            combination_drug_entity_ids=combination_drug_entity_ids,
            investigational_target_entity_ids=investigational_target_entity_ids,
            combination_target_entity_ids=combination_target_entity_ids,
            linked_drug_modality=linked_drug_modality,
            linked_drug_innovation_type=linked_drug_innovation_type,
            linked_drug_category=linked_drug_category,
            linked_drug_program_tag=linked_drug_program_tag,
            linked_drug_global_phase=linked_drug_global_phase,
            linked_drug_organization_country_region=linked_drug_organization_country_region,
            role_entity_id=role_entity_id,
            role_entity_ids=role_entity_ids,
            role_entity_role=role_entity_role,
            has_key_result=has_key_result,
            publication_id=publication_id,
            conference=conference,
            disclosed_from=disclosed_from,
            disclosed_to=disclosed_to,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def clinical_trial_detail(self, trial_id: str) -> ClinicalTrialDetailRead | None:
        return query_clinical_trial_detail(self.context, trial_id)

    def patents(
        self,
        entity_id: str | None,
        query: str | None,
        limit: int,
        offset: int = 0,
        applicant: str | None = None,
        legal_status: str | None = None,
    ) -> list[PatentFamilyRead]:
        return query_patents(self.context, entity_id, query, limit, offset, applicant, legal_status)

    def search_patent_families(
        self,
        query: str | None,
        applicant: str | None,
        legal_status: str | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        priority_from: datetime | None = None,
        priority_to: datetime | None = None,
        expiration_from: datetime | None = None,
        expiration_to: datetime | None = None,
        sort_by: PatentSortField = "priority_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[PatentSortField]] | None = None,
    ) -> PatentFamilySearchResult:
        return query_search_patent_families(
            self.context,
            query,
            applicant,
            legal_status,
            limit,
            offset,
            entity_id=entity_id,
            priority_from=priority_from,
            priority_to=priority_to,
            expiration_from=expiration_from,
            expiration_to=expiration_to,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def patent_saved_search_matches_entity(
        self,
        entity_id: str,
        query: PatentSavedSearchQuery,
    ) -> bool:
        return query_patent_saved_search_matches_entity(self.context, entity_id, query)

    def patent_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        applicant: str | None,
        legal_status: str | None,
        limit: int,
        offset: int = 0,
        *,
        sort_by: PatentSortField = "priority_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[PatentSortField]] | None = None,
    ) -> list[PatentFamilySearchItemRead]:
        return query_patent_search_items(
            self.context,
            entity_id,
            query,
            applicant,
            legal_status,
            limit,
            offset,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def patent_family_detail(self, family_id: str) -> PatentFamilySearchItemRead | None:
        return query_patent_family_detail(self.context, family_id)

    def deals(
        self,
        entity_id: str | None,
        limit: int,
        offset: int = 0,
        query: str | None = None,
        deal_type: str | None = None,
        territory: str | None = None,
        party: str | None = None,
    ) -> list[DealRead]:
        return query_deals(self.context, entity_id, limit, offset, query, deal_type, territory, party)

    def search_deals(
        self,
        query: str | None,
        deal_type: str | None,
        territory: str | None,
        party: str | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        status: str | None = None,
        direction: str | None = None,
        direction_reference_jurisdiction: str | None = None,
        asset_entity_id: str | None = None,
        target_entity_id: str | None = None,
        disease_entity_id: str | None = None,
        asset_modality: list[str] | None = None,
        asset_program_tag: list[str] | None = None,
        party_entity_id: str | None = None,
        party_role: str | None = None,
        party_country_region: str | None = None,
        party_organization_type: str | None = None,
        development_phase_at_transaction: str | None = None,
        current_development_phase: str | None = None,
        right_type: str | None = None,
        rights_territory: str | None = None,
        currency: str | None = None,
        announced_from: datetime | None = None,
        announced_to: datetime | None = None,
        terminated_from: datetime | None = None,
        terminated_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        upfront_amount_min: float | None = None,
        upfront_amount_max: float | None = None,
        total_potential_amount_min: float | None = None,
        total_potential_amount_max: float | None = None,
        sort_by: DealSortField = "announced_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[DealSortField]] | None = None,
        landscape_limit: DealAnalysisLimit = 8,
    ) -> DealSearchResult:
        return query_search_deals(
            self.context,
            query,
            deal_type,
            territory,
            party,
            limit,
            offset,
            entity_id=entity_id,
            status=status,
            direction=direction,
            direction_reference_jurisdiction=direction_reference_jurisdiction,
            asset_entity_id=asset_entity_id,
            target_entity_id=target_entity_id,
            disease_entity_id=disease_entity_id,
            asset_modality=asset_modality,
            asset_program_tag=asset_program_tag,
            party_entity_id=party_entity_id,
            party_role=party_role,
            party_country_region=party_country_region,
            party_organization_type=party_organization_type,
            development_phase_at_transaction=development_phase_at_transaction,
            current_development_phase=current_development_phase,
            right_type=right_type,
            rights_territory=rights_territory,
            currency=currency,
            announced_from=announced_from,
            announced_to=announced_to,
            terminated_from=terminated_from,
            terminated_to=terminated_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            upfront_amount_min=upfront_amount_min,
            upfront_amount_max=upfront_amount_max,
            total_potential_amount_min=total_potential_amount_min,
            total_potential_amount_max=total_potential_amount_max,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
            landscape_limit=landscape_limit,
        )

    def deal_saved_search_matches_entity(
        self,
        entity_id: str,
        query: DealSavedSearchQuery,
    ) -> bool:
        return query_deal_saved_search_matches_entity(self.context, entity_id, query)

    def deal_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        deal_type: str | None,
        territory: str | None,
        party: str | None,
        limit: int,
        offset: int = 0,
        *,
        status: str | None = None,
        direction: str | None = None,
        direction_reference_jurisdiction: str | None = None,
        asset_entity_id: str | None = None,
        target_entity_id: str | None = None,
        disease_entity_id: str | None = None,
        asset_modality: list[str] | None = None,
        asset_program_tag: list[str] | None = None,
        party_entity_id: str | None = None,
        party_role: str | None = None,
        party_country_region: str | None = None,
        party_organization_type: str | None = None,
        development_phase_at_transaction: str | None = None,
        current_development_phase: str | None = None,
        right_type: str | None = None,
        rights_territory: str | None = None,
        currency: str | None = None,
        announced_from: datetime | None = None,
        announced_to: datetime | None = None,
        terminated_from: datetime | None = None,
        terminated_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        upfront_amount_min: float | None = None,
        upfront_amount_max: float | None = None,
        total_potential_amount_min: float | None = None,
        total_potential_amount_max: float | None = None,
        sort_by: DealSortField = "announced_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[DealSortField]] | None = None,
    ) -> list[DealSearchItemRead]:
        return query_deal_search_items(
            self.context,
            entity_id,
            query,
            deal_type,
            territory,
            party,
            limit,
            offset,
            status=status,
            direction=direction,
            direction_reference_jurisdiction=direction_reference_jurisdiction,
            asset_entity_id=asset_entity_id,
            target_entity_id=target_entity_id,
            disease_entity_id=disease_entity_id,
            asset_modality=asset_modality,
            asset_program_tag=asset_program_tag,
            party_entity_id=party_entity_id,
            party_role=party_role,
            party_country_region=party_country_region,
            party_organization_type=party_organization_type,
            development_phase_at_transaction=development_phase_at_transaction,
            current_development_phase=current_development_phase,
            right_type=right_type,
            rights_territory=rights_territory,
            currency=currency,
            announced_from=announced_from,
            announced_to=announced_to,
            terminated_from=terminated_from,
            terminated_to=terminated_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            upfront_amount_min=upfront_amount_min,
            upfront_amount_max=upfront_amount_max,
            total_potential_amount_min=total_potential_amount_min,
            total_potential_amount_max=total_potential_amount_max,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def deal_detail(self, deal_id: str) -> DealSearchItemRead | None:
        return query_deal_detail(self.context, deal_id)

    def company_timeline(
        self,
        company_entity_id: str,
        limit: int,
        offset: int = 0,
    ) -> CompanyTimelineResult | None:
        return query_company_timeline(self.context, company_entity_id, limit, offset)

    def regulatory_events(
        self,
        entity_id: str | None,
        query: str | None,
        agency: str | None,
        limit: int,
        offset: int = 0,
        jurisdiction: str | None = None,
        event_type: str | None = None,
        status: str | None = None,
    ) -> list[RegulatoryEventRead]:
        return query_regulatory_events(
            self.context, entity_id, query, agency, limit, offset, jurisdiction, event_type, status
        )

    def search_regulatory_events(
        self,
        query: str | None,
        agency: str | None,
        jurisdiction: str | None,
        event_type: str | None,
        status: str | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        designation_type: str | None = None,
        label_change_type: str | None = None,
        has_boxed_warning: bool | None = None,
        safety_signal_type: str | None = None,
        safety_severity: str | None = None,
        safety_status: str | None = None,
        decision_from: datetime | None = None,
        decision_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        sort_by: RegulatorySortField = "decision_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[RegulatorySortField]] | None = None,
    ) -> RegulatoryEventSearchResult:
        return query_search_regulatory_events(
            self.context,
            query,
            agency,
            jurisdiction,
            event_type,
            status,
            limit,
            offset,
            entity_id=entity_id,
            designation_type=designation_type,
            label_change_type=label_change_type,
            has_boxed_warning=has_boxed_warning,
            safety_signal_type=safety_signal_type,
            safety_severity=safety_severity,
            safety_status=safety_status,
            decision_from=decision_from,
            decision_to=decision_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def regulatory_saved_search_matches_entity(
        self,
        entity_id: str,
        query: RegulatorySavedSearchQuery,
    ) -> bool:
        return query_regulatory_saved_search_matches_entity(self.context, entity_id, query)

    def regulatory_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        agency: str | None,
        jurisdiction: str | None,
        event_type: str | None,
        status: str | None,
        limit: int,
        offset: int = 0,
        *,
        designation_type: str | None = None,
        label_change_type: str | None = None,
        has_boxed_warning: bool | None = None,
        safety_signal_type: str | None = None,
        safety_severity: str | None = None,
        safety_status: str | None = None,
        decision_from: datetime | None = None,
        decision_to: datetime | None = None,
        source_updated_from: datetime | None = None,
        source_updated_to: datetime | None = None,
        sort_by: RegulatorySortField = "decision_date",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[RegulatorySortField]] | None = None,
    ) -> list[RegulatoryEventSearchItemRead]:
        return query_regulatory_search_items(
            self.context,
            entity_id,
            query,
            agency,
            jurisdiction,
            event_type,
            status,
            limit,
            offset,
            designation_type=designation_type,
            label_change_type=label_change_type,
            has_boxed_warning=has_boxed_warning,
            safety_signal_type=safety_signal_type,
            safety_severity=safety_severity,
            safety_status=safety_status,
            decision_from=decision_from,
            decision_to=decision_to,
            source_updated_from=source_updated_from,
            source_updated_to=source_updated_to,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def regulatory_event_detail(self, event_id: str) -> RegulatoryEventSearchItemRead | None:
        return query_regulatory_event_detail(self.context, event_id)

    def search_epidemiology_observations(
        self,
        query: str | None,
        measure: str | None,
        geography: str | None,
        unit: str | None,
        population_scope: str | None,
        age_group: str | None,
        sex: str | None,
        period_start_from: datetime | None,
        period_end_to: datetime | None,
        limit: int,
        offset: int,
        *,
        disease_entity_id: str | None = None,
        patient_population_id: str | None = None,
        sort_by: EpidemiologySortField = "period_end",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
    ) -> EpidemiologyObservationSearchResult:
        return query_search_epidemiology_observations(
            self.context,
            query,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            period_start_from,
            period_end_to,
            limit,
            offset,
            disease_entity_id=disease_entity_id,
            patient_population_id=patient_population_id,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def epidemiology_search_items(
        self,
        disease_entity_id: str | None,
        query: str | None,
        measure: str | None,
        geography: str | None,
        unit: str | None,
        population_scope: str | None,
        age_group: str | None,
        sex: str | None,
        period_start_from: datetime | None,
        period_end_to: datetime | None,
        limit: int,
        offset: int = 0,
        *,
        patient_population_id: str | None = None,
        sort_by: EpidemiologySortField = "period_end",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[EpidemiologySortField]] | None = None,
    ) -> list[EpidemiologyObservationSearchItemRead]:
        return query_epidemiology_search_items(
            self.context,
            disease_entity_id,
            query,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            period_start_from,
            period_end_to,
            limit,
            offset,
            patient_population_id=patient_population_id,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def epidemiology_saved_search_matches_entity(
        self,
        entity_id: str,
        query: EpidemiologySavedSearchQuery,
    ) -> bool:
        return query_epidemiology_saved_search_matches_entity(self.context, entity_id, query)

    def epidemiology_trend(
        self,
        disease_entity_id: str,
        measure: str | None,
        geography: str | None,
        unit: str | None,
        population_scope: str | None,
        age_group: str | None,
        sex: str | None,
        limit: int,
        *,
        patient_population_id: str | None = None,
        anchor_observation_id: str | None = None,
    ) -> EpidemiologyTrendResult | None:
        return query_epidemiology_trend(
            self.context,
            disease_entity_id,
            measure,
            geography,
            unit,
            population_scope,
            age_group,
            sex,
            limit,
            patient_population_id=patient_population_id,
            anchor_observation_id=anchor_observation_id,
        )

    def search_news_events(
        self,
        query: str | None,
        event_type: str | None,
        publisher: str | None,
        language: str | None,
        venue: str | None,
        published_from: datetime | None,
        published_to: datetime | None,
        limit: int,
        offset: int,
        *,
        entity_id: str | None = None,
        research_content_only: bool = False,
        sort_by: NewsSortField = "published_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[NewsSortField]] | None = None,
    ) -> NewsEventSearchResult:
        return query_search_news_events(
            self.context,
            query,
            event_type,
            publisher,
            language,
            venue,
            published_from,
            published_to,
            limit,
            offset,
            entity_id=entity_id,
            research_content_only=research_content_only,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def news_event_search_items(
        self,
        entity_id: str | None,
        query: str | None,
        event_type: str | None,
        publisher: str | None,
        language: str | None,
        venue: str | None,
        published_from: datetime | None,
        published_to: datetime | None,
        limit: int,
        offset: int = 0,
        *,
        sort_by: NewsSortField = "published_at",
        sort_direction: SortDirection = "desc",
        sort: Sequence[SortClause[NewsSortField]] | None = None,
    ) -> list[NewsEventSearchItemRead]:
        return query_news_event_search_items(
            self.context,
            entity_id,
            query,
            event_type,
            publisher,
            language,
            venue,
            published_from,
            published_to,
            limit,
            offset,
            sort_by=sort_by,
            sort_direction=sort_direction,
            sort=sort,
        )

    def news_saved_search_matches_entity(self, entity_id: str, query: NewsSavedSearchQuery) -> bool:
        return query_news_saved_search_matches_entity(self.context, entity_id, query)

    def news_event_detail(self, event_id: str) -> NewsEventSearchItemRead | None:
        return query_news_event_detail(self.context, event_id)
