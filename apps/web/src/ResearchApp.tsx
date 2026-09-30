import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useCallback, useEffect, useState, useTransition } from "react";

import { ErrorState, Spinner } from "./components/common";
import { SessionBoundary } from "./components/SessionBoundary";
import { WorkspaceShell } from "./components/WorkspaceShell";
import type {
  DealAnalysisDimension,
  DealAnalysisLimit,
  DealAnalysisView,
  DealSearchFilters,
} from "./lib/contracts/deals";
import { dealSortFields } from "./lib/contracts/deals";
import { type EpidemiologyFilters, epidemiologySortFields } from "./lib/contracts/epidemiology";
import { type EntitySearchSortField, entitySortFields } from "./lib/contracts/intelligence";
import { loadSavedSearch, monitoringKeys, type SavedSearch } from "./lib/contracts/monitoring";
import { type NewsSearchFilters, newsSortFields } from "./lib/contracts/news";
import {
  type SortDirection as PatentSortDirection,
  type PatentSortField,
  patentSortFields,
} from "./lib/contracts/patents";
import {
  emptyPipelineSearchFilters,
  type PipelineResultGrain,
  type PipelineSearchFilters,
  pipelineSortFields,
} from "./lib/contracts/pipeline";
import { type RegulatorySearchFilters, regulatorySortFields } from "./lib/contracts/regulatory";
import { getSessionEntity, sessionKeys } from "./lib/contracts/session";
import { parseSortTokens, type SortCriterion, type SortDirection } from "./lib/contracts/sorting";
import { type SortDirection as TrialSortDirection, type TrialSortField, trialSortFields } from "./lib/contracts/trials";
import type {
  ChemistrySavedSearchQuery,
  ClinicalTrialSavedSearchQuery,
  DealSavedSearchQuery,
  EntitySearchQuery,
  EpidemiologySavedSearchQuery,
  NewsSavedSearchQuery,
  PatentSavedSearchQuery,
  PipelineSavedSearchQuery,
  RegulatorySavedSearchQuery,
} from "./lib/generated";
import { startResearchRum } from "./lib/rum";
import type { Entity, User } from "./lib/types";
import {
  type CompanyDossierSection,
  type DiseaseDossierSection,
  type DrugDossierSection,
  type EntityDossierSection,
  parseWorkbenchLocation,
  type TargetDossierSection,
  type ViewKey,
  type WorkspaceLocation,
  workbenchForView,
  workspaceUrl,
} from "./lib/workspaceRouting";

const ChemistryView = lazy(() => import("./views/ChemistryView").then((module) => ({ default: module.ChemistryView })));
const CollectionsView = lazy(() =>
  import("./views/CollectionsView").then((module) => ({ default: module.CollectionsView })),
);
const CompanyView = lazy(() => import("./views/CompanyView").then((module) => ({ default: module.CompanyView })));
const DealsView = lazy(() => import("./views/DealsView").then((module) => ({ default: module.DealsView })));
const DiseaseView = lazy(() => import("./views/DiseaseView").then((module) => ({ default: module.DiseaseView })));
const DrugView = lazy(() => import("./views/DrugView").then((module) => ({ default: module.DrugView })));
const EvidenceView = lazy(() => import("./views/EvidenceView").then((module) => ({ default: module.EvidenceView })));
const EpidemiologyView = lazy(() =>
  import("./views/EpidemiologyView").then((module) => ({ default: module.EpidemiologyView })),
);
const EntityDossierView = lazy(() =>
  import("./views/EntityDossierView").then((module) => ({ default: module.EntityDossierView })),
);
const ExplorerView = lazy(() => import("./views/ExplorerView").then((module) => ({ default: module.ExplorerView })));
const KnowledgeView = lazy(() => import("./views/KnowledgeView").then((module) => ({ default: module.KnowledgeView })));
const MonitoringView = lazy(() =>
  import("./views/MonitoringView").then((module) => ({ default: module.MonitoringView })),
);
const NewsView = lazy(() => import("./views/NewsView").then((module) => ({ default: module.NewsView })));
const PipelineView = lazy(() => import("./views/PipelineView").then((module) => ({ default: module.PipelineView })));
const PatentsView = lazy(() => import("./views/PatentsView").then((module) => ({ default: module.PatentsView })));
const RegulatoryView = lazy(() =>
  import("./views/RegulatoryView").then((module) => ({ default: module.RegulatoryView })),
);
const TrialsView = lazy(() => import("./views/TrialsView").then((module) => ({ default: module.TrialsView })));
const OverviewView = lazy(() => import("./views/OverviewView").then((module) => ({ default: module.OverviewView })));
const TargetView = lazy(() => import("./views/TargetView").then((module) => ({ default: module.TargetView })));

const specializedSectionByEntitySection: Record<
  EntityDossierSection,
  {
    company: CompanyDossierSection;
    disease: DiseaseDossierSection;
    drug: DrugDossierSection;
    target: TargetDossierSection;
  }
> = {
  overview: { company: "overview", disease: "overview", drug: "overview", target: "overview" },
  company_intelligence: { company: "overview", disease: "overview", drug: "overview", target: "overview" },
  relationships: { company: "relationships", disease: "relationships", drug: "relationships", target: "relationships" },
  programs: { company: "pipeline", disease: "pipeline", drug: "pipeline", target: "pipeline" },
  activities: { company: "overview", disease: "overview", drug: "activities", target: "activities" },
  clinical_trials: { company: "trials", disease: "trials", drug: "trials", target: "trials" },
  patents: { company: "patents", disease: "patents", drug: "patents", target: "patents" },
  deals: { company: "deals", disease: "deals", drug: "deals", target: "deals" },
  regulatory_events: { company: "regulatory", disease: "regulatory", drug: "regulatory", target: "regulatory" },
  news_events: { company: "news", disease: "news", drug: "news", target: "news" },
  structures: { company: "overview", disease: "overview", drug: "structures", target: "structures" },
};

function trialRoleGroupIds(location: WorkspaceLocation, role: string, groupedIds: string[] | undefined): string[] {
  if (groupedIds?.length) return groupedIds;
  if (location.trialRoleEntityRole !== role) return [];
  return Array.from(
    new Set([...(location.trialRoleEntityIds ?? []), location.trialRoleEntityId ?? ""].filter(Boolean)),
  ).sort();
}

export function pipelineFiltersFromLocation(location: WorkspaceLocation, fallbackTargetId = ""): PipelineSearchFilters {
  return {
    ...emptyPipelineSearchFilters(),
    query: location.query,
    modalities: location.pipelineModalities ?? [],
    innovationTypes: location.pipelineInnovationTypes ?? [],
    therapeuticAreas: location.pipelineTherapeuticAreas ?? [],
    drugCategories: location.pipelineDrugCategories ?? [],
    programStatus: location.pipelineProgramStatus === "all" ? "" : (location.pipelineProgramStatus ?? ""),
    organizationRole: location.pipelineOrganizationRole ?? "",
    organizationType: location.pipelineOrganizationType ?? "",
    organizationCountryRegion: location.pipelineOrganizationCountryRegion ?? "",
    phase: location.phase ?? "",
    geography: location.geography ?? "",
    statusDateFrom: location.pipelineStatusDateFrom ?? "",
    statusDateTo: location.pipelineStatusDateTo ?? "",
    drugEntityId: location.pipelineDrugEntityId ?? "",
    targetEntityId: location.pipelineTargetEntityId || fallbackTargetId,
    targetCombinationKey: location.pipelineTargetCombinationKey ?? "",
    diseaseEntityId: location.pipelineDiseaseEntityId ?? "",
    organizationEntityId: location.pipelineOrganizationEntityId ?? "",
    globalPhase: location.pipelineGlobalPhase ?? "",
    chinaPhase: location.pipelineChinaPhase ?? "",
    globalPhaseStartedFrom: location.pipelineGlobalPhaseStartedFrom ?? "",
    globalPhaseStartedTo: location.pipelineGlobalPhaseStartedTo ?? "",
    chinaPhaseStartedFrom: location.pipelineChinaPhaseStartedFrom ?? "",
    chinaPhaseStartedTo: location.pipelineChinaPhaseStartedTo ?? "",
    developmentRightsRegion: location.pipelineDevelopmentRightsRegion ?? "",
    commercializationRightsRegion: location.pipelineCommercializationRightsRegion ?? "",
    programTags: location.pipelineProgramTags ?? [],
    milestoneType: location.pipelineMilestoneType ?? "",
    milestoneFrom: location.pipelineMilestoneFrom ?? "",
    milestoneTo: location.pipelineMilestoneTo ?? "",
    hasClinicalResults: location.pipelineHasClinicalResults ?? "",
    clinicalResultEvaluation: location.pipelineClinicalResultEvaluation ?? "",
    hasDeal: location.pipelineHasDeal ?? "",
    dealCurrency: location.pipelineDealCurrency ?? "",
    dealTotalPotentialAmountMin: location.pipelineDealTotalPotentialAmountMin ?? "",
    dealTotalPotentialAmountMax: location.pipelineDealTotalPotentialAmountMax ?? "",
    sortBy: (location.pipelineSortBy ?? "status_date") as PipelineSearchFilters["sortBy"],
    sortDirection: (location.pipelineSortDirection ?? "desc") as PipelineSearchFilters["sortDirection"],
    sort: location.pipelineSort as PipelineSearchFilters["sort"],
    offset: location.offset ?? 0,
  };
}

function drugReturnLocation(returnTo: string | undefined): WorkspaceLocation | null {
  if (!returnTo) return null;
  const parsed = parseWorkbenchLocation("research", new URL(returnTo, window.location.origin).search);
  if (parsed.view === "pipeline") return parsed;
  if (parsed.view === "target" && parsed.targetSection === "pipeline" && parsed.entityId) return parsed;
  if (parsed.view === "collections" && parsed.collectionId && !parsed.invalidCollectionId) return parsed;
  if (parsed.view === "trials" && parsed.trialId && !parsed.invalidTrialId) return parsed;
  return null;
}

function targetReturnLocation(returnTo: string | undefined): WorkspaceLocation | null {
  if (!returnTo) return null;
  const parsed = parseWorkbenchLocation("research", new URL(returnTo, window.location.origin).search);
  if (parsed.view === "drug" && parsed.entityId && !parsed.invalidEntityId) return parsed;
  if (parsed.view === "trials" && parsed.trialId && !parsed.invalidTrialId) return parsed;
  return null;
}

function trialReturnLocation(returnTo: string | undefined): WorkspaceLocation | null {
  if (!returnTo) return null;
  const parsed = parseWorkbenchLocation("research", new URL(returnTo, window.location.origin).search);
  return ["target", "drug", "company", "disease", "entity"].includes(parsed.view) &&
    parsed.entityId &&
    !parsed.invalidEntityId
    ? parsed
    : null;
}

function trialReturnLabel(location: WorkspaceLocation | null): string | undefined {
  if (!location) return undefined;
  if (location.view === "target") return "返回靶点档案";
  if (location.view === "drug") return "返回药物档案";
  if (location.view === "company") return "返回公司档案";
  if (location.view === "disease") return "返回疾病档案";
  return "返回实体档案";
}

function locationWithPipelineFilters(location: WorkspaceLocation, filters: PipelineSearchFilters): WorkspaceLocation {
  return {
    ...location,
    query: filters.query,
    pipelineModalities: filters.modalities,
    pipelineInnovationTypes: filters.innovationTypes,
    pipelineTherapeuticAreas: filters.therapeuticAreas,
    pipelineDrugCategories: filters.drugCategories,
    pipelineProgramStatus: location.view === "target" && filters.programStatus === "" ? "all" : filters.programStatus,
    pipelineOrganizationRole: filters.organizationRole,
    pipelineOrganizationType: filters.organizationType,
    pipelineOrganizationCountryRegion: filters.organizationCountryRegion,
    phase: filters.phase,
    geography: filters.geography,
    pipelineStatusDateFrom: filters.statusDateFrom,
    pipelineStatusDateTo: filters.statusDateTo,
    pipelineDrugEntityId: filters.drugEntityId,
    pipelineTargetEntityId:
      location.view === "target" && filters.targetEntityId === location.entityId ? "" : filters.targetEntityId,
    pipelineTargetCombinationKey: filters.targetCombinationKey,
    pipelineDiseaseEntityId: filters.diseaseEntityId,
    pipelineOrganizationEntityId: filters.organizationEntityId,
    pipelineGlobalPhase: filters.globalPhase,
    pipelineChinaPhase: filters.chinaPhase,
    pipelineGlobalPhaseStartedFrom: filters.globalPhaseStartedFrom,
    pipelineGlobalPhaseStartedTo: filters.globalPhaseStartedTo,
    pipelineChinaPhaseStartedFrom: filters.chinaPhaseStartedFrom,
    pipelineChinaPhaseStartedTo: filters.chinaPhaseStartedTo,
    pipelineDevelopmentRightsRegion: filters.developmentRightsRegion,
    pipelineCommercializationRightsRegion: filters.commercializationRightsRegion,
    pipelineProgramTags: filters.programTags,
    pipelineMilestoneType: filters.milestoneType,
    pipelineMilestoneFrom: filters.milestoneFrom,
    pipelineMilestoneTo: filters.milestoneTo,
    pipelineHasClinicalResults: filters.hasClinicalResults,
    pipelineClinicalResultEvaluation: filters.clinicalResultEvaluation,
    pipelineHasDeal: filters.hasDeal,
    pipelineDealCurrency: filters.dealCurrency,
    pipelineDealTotalPotentialAmountMin: filters.dealTotalPotentialAmountMin,
    pipelineDealTotalPotentialAmountMax: filters.dealTotalPotentialAmountMax,
    pipelineSort: filters.sort,
    pipelineSortBy: filters.sortBy,
    pipelineSortDirection: filters.sortDirection,
    offset: filters.offset,
  };
}

function savedRepeatedValues(value: unknown): string[] {
  const values = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
  return Array.from(
    new Set(values.filter((item): item is string => typeof item === "string" && item.trim().length > 0)),
  )
    .map((item) => item.trim())
    .slice(0, 20);
}

function savedSort<Field extends string>(
  tokens: readonly string[] | null | undefined,
  fields: readonly Field[],
  sortBy: Field,
  sortDirection: SortDirection,
): SortCriterion<Field>[] {
  return parseSortTokens(tokens ?? [], new Set(fields), { field: sortBy, direction: sortDirection });
}

export function ResearchApp() {
  return (
    <SessionBoundary workbench="research">
      {({ user, logout, updateUser }) => <ResearchWorkspace user={user} onLogout={logout} onUserUpdated={updateUser} />}
    </SessionBoundary>
  );
}

function ResearchWorkspace({
  user,
  onLogout,
  onUserUpdated,
}: {
  user: User;
  onLogout: () => void;
  onUserUpdated: (user: User) => void;
}) {
  const [location, setLocation] = useState<WorkspaceLocation>(() =>
    parseWorkbenchLocation("research", window.location.search),
  );
  const [, startNavigationTransition] = useTransition();
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [pendingNavigationView, setPendingNavigationView] = useState<ViewKey | null>(null);
  const activeDrugReturnLocation = drugReturnLocation(location.returnTo);
  const activeTargetReturnLocation = targetReturnLocation(location.returnTo);
  const activeTrialReturnLocation = trialReturnLocation(location.returnTo);
  const routeEntity = useQuery({
    queryKey: sessionKeys.entity(location.entityId ?? ""),
    queryFn: ({ signal }) => getSessionEntity(location.entityId ?? "", signal),
    enabled: Boolean(
      (location.view === "explorer" ||
        location.view === "target" ||
        location.view === "drug" ||
        location.view === "company" ||
        location.view === "disease" ||
        location.view === "entity") &&
        !location.invalidEntityId &&
        location.entityId &&
        selectedEntity?.id !== location.entityId,
    ),
  });
  const routeChemistrySavedSearch = useQuery({
    queryKey: monitoringKeys.saved(location.chemistrySavedSearchId ?? ""),
    queryFn: ({ signal }) => loadSavedSearch(location.chemistrySavedSearchId ?? "", signal),
    enabled:
      location.view === "chemistry" &&
      Boolean(location.chemistrySavedSearchId) &&
      !location.invalidChemistrySavedSearchId,
  });

  useEffect(() => {
    void startResearchRum();
  }, []);

  useEffect(() => {
    const canonicalUrl = workspaceUrl(location);
    if (`${window.location.pathname}${window.location.search}` !== canonicalUrl) {
      window.history.replaceState(null, "", canonicalUrl);
    }
  }, [location]);

  useEffect(() => {
    const popState = () => {
      setPendingNavigationView(null);
      setLocation(parseWorkbenchLocation("research", window.location.search));
    };
    window.addEventListener("popstate", popState);
    return () => window.removeEventListener("popstate", popState);
  }, []);

  const navigate = useCallback(
    (next: WorkspaceLocation, replace = false, urgent = false) => {
      const method = replace ? "replaceState" : "pushState";
      window.history[method](null, "", workspaceUrl(next));
      const commitLocation = () => {
        setLocation(next);
        setPendingNavigationView((current) => (current === next.view ? null : current));
        if (
          (next.view !== "explorer" &&
            next.view !== "target" &&
            next.view !== "drug" &&
            next.view !== "company" &&
            next.view !== "disease" &&
            next.view !== "entity") ||
          !next.entityId
        ) {
          setSelectedEntity(null);
        }
      };
      // Query, sort, pagination and display-state changes stay in the same view but can
      // still rerender a dense result surface. Keep the URL synchronous for sharing and
      // history, while scheduling the non-urgent React tree update as a transition.
      if (urgent) {
        setPendingNavigationView(null);
        commitLocation();
        return;
      }
      setPendingNavigationView(next.view === location.view ? null : next.view);
      startNavigationTransition(commitLocation);
    },
    [location.view],
  );

  useEffect(() => {
    if (location.view !== "entity" || !routeEntity.data || routeEntity.data.id !== location.entityId) return;
    const specializedView =
      routeEntity.data.entity_type === "target"
        ? "target"
        : routeEntity.data.entity_type === "drug"
          ? "drug"
          : routeEntity.data.entity_type === "organization"
            ? "company"
            : routeEntity.data.entity_type === "disease"
              ? "disease"
              : null;
    if (!specializedView) return;
    setSelectedEntity(routeEntity.data);
    const mappedSection = specializedSectionByEntitySection[location.entitySection ?? "overview"];
    navigate(
      {
        ...location,
        view: specializedView,
        ...(specializedView === "target"
          ? { targetSection: mappedSection.target }
          : specializedView === "drug"
            ? { drugSection: mappedSection.drug }
            : specializedView === "company"
              ? { companySection: mappedSection.company }
              : { diseaseSection: mappedSection.disease }),
      },
      true,
    );
  }, [location, navigate, routeEntity.data]);

  const navigateToView = useCallback(
    (view: ViewKey) => {
      if (workbenchForView(view) !== "research") return;
      // Sidebar commands reset the draft query for the selected view. Commit this
      // command synchronously so a slow view transition cannot overwrite new input.
      navigate(
        {
          workbench: "research",
          view,
          query: "",
          entityType: "",
          reviewStatus: "",
          entityId: null,
          invalidEntityId: false,
        },
        false,
        true,
      );
    },
    [navigate],
  );

  function openSavedSearch(saved: SavedSearch) {
    if (saved.query_type === "chemistry_search") {
      navigate({
        workbench: "research",
        view: "chemistry",
        query: "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        chemistrySavedSearchId: saved.id,
        invalidChemistrySavedSearchId: false,
      });
      return;
    }
    if (saved.query_type === "pipeline_search") {
      const query = saved.query_json as PipelineSavedSearchQuery;
      const sort = savedSort(
        query.sort,
        pipelineSortFields,
        query.sort_by ?? "status_date",
        query.sort_direction ?? "desc",
      );
      navigate({
        workbench: "research",
        view: "pipeline",
        query: query.q ?? "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        pipelineModalities: Array.isArray(query.modality) ? query.modality : query.modality ? [query.modality] : [],
        pipelineInnovationTypes: query.innovation_type ?? [],
        pipelineTherapeuticAreas: query.therapeutic_area ?? [],
        pipelineDrugCategories: query.drug_category ?? [],
        pipelineProgramStatus: query.program_status ?? "",
        pipelineOrganizationRole: query.organization_role ?? "",
        pipelineOrganizationType: query.organization_type ?? "",
        pipelineOrganizationCountryRegion: query.organization_country_region ?? "",
        phase: query.phase ?? "",
        geography: query.geography ?? "",
        pipelineStatusDateFrom: query.status_date_from ?? "",
        pipelineStatusDateTo: query.status_date_to ?? "",
        pipelineDrugEntityId: query.drug_entity_id ?? "",
        pipelineTargetEntityId: query.target_entity_id ?? "",
        pipelineTargetCombinationKey: query.target_combination_key ?? "",
        pipelineDiseaseEntityId: query.disease_entity_id ?? "",
        pipelineOrganizationEntityId: query.organization_entity_id ?? "",
        pipelineGlobalPhase: query.global_phase ?? "",
        pipelineChinaPhase: query.china_phase ?? "",
        pipelineGlobalPhaseStartedFrom: query.global_phase_started_from ?? "",
        pipelineGlobalPhaseStartedTo: query.global_phase_started_to ?? "",
        pipelineChinaPhaseStartedFrom: query.china_phase_started_from ?? "",
        pipelineChinaPhaseStartedTo: query.china_phase_started_to ?? "",
        pipelineDevelopmentRightsRegion: query.development_rights_region ?? "",
        pipelineCommercializationRightsRegion: query.commercialization_rights_region ?? "",
        pipelineProgramTags: Array.isArray(query.program_tag)
          ? query.program_tag
          : query.program_tag
            ? [query.program_tag]
            : [],
        pipelineMilestoneType: query.milestone_type ?? "",
        pipelineMilestoneFrom: query.milestone_from ?? "",
        pipelineMilestoneTo: query.milestone_to ?? "",
        pipelineHasClinicalResults:
          query.has_clinical_results === undefined ? "" : query.has_clinical_results ? "true" : "false",
        pipelineClinicalResultEvaluation: query.clinical_result_evaluation ?? "",
        pipelineHasDeal: query.has_deal === undefined ? "" : query.has_deal ? "true" : "false",
        pipelineDealCurrency: query.deal_currency ?? "",
        pipelineDealTotalPotentialAmountMin: query.deal_total_potential_amount_min?.toString() ?? "",
        pipelineDealTotalPotentialAmountMax: query.deal_total_potential_amount_max?.toString() ?? "",
        pipelineSort: sort,
        pipelineSortBy: sort[0]?.field ?? "status_date",
        pipelineSortDirection: sort[0]?.direction ?? "desc",
        pipelineDisplayMode: query.display_mode ?? "list",
        pipelineAnalysisDimension: query.analysis_dimension ?? "all",
        pipelineAnalysisView: query.analysis_view ?? "chart",
        pipelineAnalysisLimit: query.analysis_limit ?? 8,
        pipelineAnalysisStageScope: query.analysis_stage_scope ?? "overall",
        pipelineTargetAggregation: query.target_aggregation ?? "all",
        offset: 0,
      });
      return;
    }
    if (saved.query_type === "clinical_trial_search") {
      const query = saved.query_json as ClinicalTrialSavedSearchQuery;
      const sort = savedSort(
        query.sort,
        trialSortFields,
        query.sort_by ?? "last_update_posted",
        query.sort_direction ?? "desc",
      );
      navigate({
        workbench: "research",
        view: "trials",
        query: query.q ?? "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        registry: query.registry ?? "",
        trialStatus: query.status ?? "",
        trialPhase: query.phase ?? "",
        studyType: query.study_type ?? "",
        trialAcronym: query.acronym ?? "",
        trialInitiationType: query.initiation_type ?? "",
        trialTherapyLine: query.therapy_line ?? "",
        trialHasResults: query.has_results === true ? "true" : query.has_results === false ? "false" : "",
        trialResultEvaluation: query.result_evaluation ?? "",
        trialResultsPostedFrom: query.results_posted_from ?? "",
        trialResultsPostedTo: query.results_posted_to ?? "",
        trialInvestigationalDrug: query.investigational_drug ?? "",
        trialCombinationDrug: query.combination_drug ?? "",
        trialInvestigationalTarget: query.investigational_target ?? "",
        trialCombinationTarget: query.combination_target ?? "",
        trialInvestigationalDrugEntityIds: query.investigational_drug_entity_ids ?? [],
        trialCombinationDrugEntityIds: query.combination_drug_entity_ids ?? [],
        trialInvestigationalTargetEntityIds: query.investigational_target_entity_ids ?? [],
        trialCombinationTargetEntityIds: query.combination_target_entity_ids ?? [],
        trialLinkedDrugModalities: query.linked_drug_modality ?? [],
        trialLinkedDrugInnovationTypes: query.linked_drug_innovation_type ?? [],
        trialLinkedDrugCategories: query.linked_drug_category ?? [],
        trialLinkedDrugProgramTags: query.linked_drug_program_tag ?? [],
        trialLinkedDrugGlobalPhase: query.linked_drug_global_phase ?? "",
        trialLinkedDrugOrganizationCountryRegion: query.linked_drug_organization_country_region ?? "",
        trialRoleEntityId: query.role_entity_id ?? "",
        trialRoleEntityIds: query.role_entity_ids ?? [],
        trialRoleEntityRole: query.role_entity_role ?? "",
        trialHasKeyResult: query.has_key_result === true ? "true" : query.has_key_result === false ? "false" : "",
        trialPublicationId: query.publication_id ?? "",
        trialConference: query.conference ?? "",
        trialDisclosedFrom: query.disclosed_from ?? "",
        trialDisclosedTo: query.disclosed_to ?? "",
        trialSort: sort,
        trialSortBy: sort[0]?.field ?? "last_update_posted",
        trialSortDirection: sort[0]?.direction ?? "desc",
        trialDisplayMode: query.display_mode ?? "list",
        trialAnalysisView: query.analysis_view ?? "chart",
        trialId: null,
        invalidTrialId: false,
        trialSection: "overview",
        offset: 0,
      });
      return;
    }
    if (saved.query_type === "patent_search") {
      const query = saved.query_json as PatentSavedSearchQuery;
      const sort = savedSort(
        query.sort,
        patentSortFields,
        query.sort_by ?? "priority_date",
        query.sort_direction ?? "desc",
      );
      navigate({
        workbench: "research",
        view: "patents",
        query: query.q ?? "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        applicant: query.applicant ?? "",
        legalStatus: query.legal_status ?? "",
        patentSort: sort,
        patentSortBy: sort[0]?.field ?? "priority_date",
        patentSortDirection: sort[0]?.direction ?? "desc",
        patentId: null,
        invalidPatentId: false,
        patentSection: "overview",
        patentDisplayMode: query.display_mode ?? "list",
        patentAnalysisView: query.analysis_view ?? "chart",
        patentEntityId: query.entity_id ?? "",
        patentPriorityFrom: query.priority_from ?? "",
        patentPriorityTo: query.priority_to ?? "",
        patentExpirationFrom: query.expiration_from ?? "",
        patentExpirationTo: query.expiration_to ?? "",
        offset: 0,
      });
      return;
    }
    if (saved.query_type === "deal_search") {
      const query = saved.query_json as DealSavedSearchQuery;
      const requestedSort = savedSort(
        query.sort,
        dealSortFields,
        query.sort_by ?? "announced_at",
        query.sort_direction ?? "desc",
      );
      const sort =
        requestedSort.some((criterion) => ["upfront_amount", "total_potential_amount"].includes(criterion.field)) &&
        !query.currency
          ? [{ field: "announced_at" as const, direction: "desc" as const }]
          : requestedSort;
      navigate({
        workbench: "research",
        view: "deals",
        query: query.q ?? "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        dealType: query.deal_type ?? "",
        dealStatus: query.status ?? "",
        dealDirection: query.direction ?? "",
        dealDirectionReferenceJurisdiction: query.direction_reference_jurisdiction ?? "",
        dealTerritory: query.territory ?? "",
        dealAssetEntityId: query.asset_entity_id ?? "",
        dealTargetEntityId: query.target_entity_id ?? "",
        dealDiseaseEntityId: query.disease_entity_id ?? "",
        dealAssetModalities: savedRepeatedValues(query.asset_modality),
        dealAssetProgramTags: savedRepeatedValues(query.asset_program_tag),
        dealParty: query.party ?? "",
        dealPartyEntityId: query.party_entity_id ?? "",
        dealPartyRole: query.party_role ?? "",
        dealPartyCountryRegion: query.party_country_region ?? "",
        dealPartyOrganizationType: query.party_organization_type ?? "",
        dealDevelopmentPhaseAtTransaction: query.development_phase_at_transaction ?? "",
        dealCurrentDevelopmentPhase: query.current_development_phase ?? "",
        dealRightType: query.right_type ?? "",
        dealRightsTerritory: query.rights_territory ?? "",
        dealCurrency: query.currency ?? "",
        dealAnnouncedFrom: query.announced_from ?? "",
        dealAnnouncedTo: query.announced_to ?? "",
        dealTerminatedFrom: query.terminated_from ?? "",
        dealTerminatedTo: query.terminated_to ?? "",
        dealSourceUpdatedFrom: query.source_updated_from ?? "",
        dealSourceUpdatedTo: query.source_updated_to ?? "",
        dealUpfrontAmountMin: query.upfront_amount_min?.toString() ?? "",
        dealUpfrontAmountMax: query.upfront_amount_max?.toString() ?? "",
        dealTotalPotentialAmountMin: query.total_potential_amount_min?.toString() ?? "",
        dealTotalPotentialAmountMax: query.total_potential_amount_max?.toString() ?? "",
        dealSort: sort,
        dealSortBy: sort[0]?.field ?? "announced_at",
        dealSortDirection: sort[0]?.direction ?? "desc",
        dealDisplayMode: query.display_mode ?? "list",
        dealAnalysisDimension: query.analysis_dimension ?? "all",
        dealAnalysisView: query.analysis_view ?? "chart",
        dealAnalysisLimit: query.analysis_limit ?? 8,
        dealId: null,
        invalidDealId: false,
        dealSection: "overview",
        offset: 0,
      });
      return;
    }
    if (saved.query_type === "regulatory_search") {
      const query = saved.query_json as RegulatorySavedSearchQuery;
      const sort = savedSort(
        query.sort,
        regulatorySortFields,
        query.sort_by ?? "decision_date",
        query.sort_direction ?? "desc",
      );
      navigate({
        workbench: "research",
        view: "regulatory",
        query: query.q ?? "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        regulatoryAgency: query.agency ?? "",
        regulatoryJurisdiction: query.jurisdiction ?? "",
        regulatoryEventType: query.event_type ?? "",
        regulatoryDisplayMode: query.display_mode ?? "list",
        regulatoryAnalysisView: query.analysis_view ?? "chart",
        regulatoryStatus: query.status ?? "",
        regulatoryDesignationType: query.designation_type ?? "",
        regulatoryLabelChangeType: query.label_change_type ?? "",
        regulatoryBoxedWarning:
          query.has_boxed_warning === true ? "true" : query.has_boxed_warning === false ? "false" : "",
        regulatorySafetySignalType: query.safety_signal_type ?? "",
        regulatorySafetySeverity: query.safety_severity ?? "",
        regulatorySafetyStatus: query.safety_status ?? "",
        regulatoryDecisionFrom: query.decision_from ?? "",
        regulatoryDecisionTo: query.decision_to ?? "",
        regulatorySourceUpdatedFrom: query.source_updated_from ?? "",
        regulatorySourceUpdatedTo: query.source_updated_to ?? "",
        regulatorySort: sort,
        regulatorySortBy: sort[0]?.field ?? "decision_date",
        regulatorySortDirection: sort[0]?.direction ?? "desc",
        regulatoryEventId: null,
        invalidRegulatoryEventId: false,
        regulatoryCompareIds: [],
        offset: 0,
      });
      return;
    }
    if (saved.query_type === "epidemiology_search") {
      const query = saved.query_json as EpidemiologySavedSearchQuery;
      const sort = savedSort(
        query.sort,
        epidemiologySortFields,
        query.sort_by ?? "period_end",
        query.sort_direction ?? "desc",
      );
      navigate({
        workbench: "research",
        view: "epidemiology",
        query: query.q ?? "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        epidemiologyDiseaseEntityId: query.disease_entity_id ?? "",
        epidemiologyMeasure: query.measure ?? "",
        epidemiologyGeography: query.geography ?? "",
        epidemiologyUnit: query.unit ?? "",
        epidemiologyPatientPopulationId: query.patient_population_id ?? "",
        epidemiologyPopulationScope: query.population_scope ?? "",
        epidemiologyAgeGroup: query.age_group ?? "",
        epidemiologySex: query.sex ?? "",
        epidemiologyPeriodStartFrom: query.period_start_from ?? "",
        epidemiologyPeriodEndTo: query.period_end_to ?? "",
        epidemiologySort: sort,
        epidemiologySortBy: sort[0]?.field ?? "period_end",
        epidemiologySortDirection: sort[0]?.direction ?? "desc",
        epidemiologyDisplayMode: query.display_mode ?? "list",
        epidemiologyAnalysisView: query.analysis_view ?? "chart",
        offset: 0,
      });
      return;
    }
    if (saved.query_type === "news_search") {
      const query = saved.query_json as NewsSavedSearchQuery;
      const sort = savedSort(
        query.sort,
        newsSortFields,
        query.sort_by ?? "published_at",
        query.sort_direction ?? "desc",
      );
      navigate({
        workbench: "research",
        view: "news",
        query: query.q ?? "",
        entityType: "",
        reviewStatus: "",
        entityId: null,
        invalidEntityId: false,
        newsEventType: query.event_type ?? "",
        newsPublisher: query.publisher ?? "",
        newsLanguage: query.language ?? "",
        newsVenue: query.venue ?? "",
        newsPublishedFrom: query.published_from ?? "",
        newsPublishedTo: query.published_to ?? "",
        newsContentScope: query.content_scope === "research" ? "research" : "",
        newsEntityId: query.entity_id ?? "",
        newsDisplayMode: query.display_mode ?? "list",
        newsSort: sort,
        newsSortBy: sort[0]?.field ?? "published_at",
        newsSortDirection: sort[0]?.direction ?? "desc",
        newsEventId: null,
        invalidNewsEventId: false,
        newsAnalysisView: query.analysis_view ?? "chart",
        offset: 0,
      });
      return;
    }
    const query = saved.query_json as EntitySearchQuery;
    const entityTypes = query.entity_types?.length ? query.entity_types : query.entity_type ? [query.entity_type] : [];
    const sort = savedSort(query.sort, entitySortFields, query.sort_by ?? "relevance", query.sort_direction ?? "desc");
    navigate({
      workbench: "research",
      view: "explorer",
      query: query.q ?? "",
      entityType: entityTypes.length === 1 ? (entityTypes[0] ?? "") : "",
      entityTypes,
      reviewStatus: query.review_status ?? "",
      entitySort: sort,
      entitySortBy: sort[0]?.field ?? "relevance",
      entitySortDirection: sort[0]?.direction ?? "desc",
      explorerDisplayMode: query.display_mode ?? "list",
      explorerAnalysisView: query.analysis_view ?? "chart",
      entityId: null,
      invalidEntityId: false,
    });
  }

  function openEntity(entity: Entity) {
    const view =
      entity.entity_type === "target"
        ? "target"
        : entity.entity_type === "drug"
          ? "drug"
          : entity.entity_type === "organization"
            ? "company"
            : entity.entity_type === "disease"
              ? "disease"
              : "entity";
    setSelectedEntity(entity);
    navigate({
      workbench: "research",
      view,
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId: entity.id,
      invalidEntityId: false,
      ...(view === "target"
        ? { targetSection: "overview" as const }
        : view === "drug"
          ? { drugSection: "overview" as const }
          : view === "company"
            ? { companySection: "overview" as const }
            : view === "disease"
              ? { diseaseSection: "overview" as const }
              : { entitySection: "overview" as const }),
    });
  }

  function openDrugById(entityId: string, returnTo?: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "drug",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      drugSection: "overview",
      ...(returnTo ? { returnTo } : {}),
    });
  }

  function openEntityById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "entity",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      entitySection: "overview",
    });
  }

  function openTargetById(entityId: string, returnTo?: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "target",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      targetSection: "overview",
      ...(returnTo ? { returnTo } : {}),
    });
  }

  function openTargetPipelineById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "target",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      targetSection: "pipeline",
    });
  }

  function openDiseaseById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "disease",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      diseaseSection: "overview",
    });
  }

  function openOrganizationById(entityId: string) {
    setSelectedEntity(null);
    navigate({
      workbench: "research",
      view: "company",
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId,
      invalidEntityId: false,
      companySection: "overview",
    });
  }

  function openEpidemiologyForDisease(diseaseId: string) {
    navigate({
      workbench: "research",
      view: "epidemiology",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      epidemiologyDiseaseEntityId: diseaseId,
      offset: 0,
    });
  }

  function openTrialById(trialId: string, returnTo?: string) {
    navigate({
      workbench: "research",
      view: "trials",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      trialId,
      invalidTrialId: false,
      trialSection: "overview",
      offset: 0,
      ...(returnTo ? { returnTo } : {}),
    });
  }

  function openDealById(dealId: string) {
    navigate({
      workbench: "research",
      view: "deals",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      dealId,
      invalidDealId: false,
      dealSection: "overview",
      offset: 0,
    });
  }

  function openPatentFamilyById(patentId: string) {
    navigate({
      workbench: "research",
      view: "patents",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      patentId,
      invalidPatentId: false,
      offset: 0,
    });
  }

  function openRegulatoryEventById(regulatoryEventId: string) {
    navigate({
      workbench: "research",
      view: "regulatory",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      regulatoryEventId,
      invalidRegulatoryEventId: false,
      regulatoryCompareIds: [],
      offset: 0,
    });
  }

  function openNewsEventById(newsEventId: string) {
    navigate({
      workbench: "research",
      view: "news",
      query: location.query,
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      newsEventId,
      invalidNewsEventId: false,
      offset: 0,
    });
  }

  return (
    <WorkspaceShell
      user={user}
      activeWorkbench="research"
      activeView={location.view}
      pendingView={pendingNavigationView}
      onView={navigateToView}
    >
      <Suspense fallback={<Spinner label="正在加载研究工作区" />}>
        {location.view === "overview" ? (
          <OverviewView user={user} onLogout={onLogout} onUserUpdated={onUserUpdated} />
        ) : null}
        {location.view === "explorer" ? (
          <ExplorerView
            initialQuery={location.query}
            initialEntityType={location.entityType}
            initialEntityTypes={location.entityTypes ?? []}
            initialReviewStatus={location.reviewStatus}
            initialSortBy={location.entitySortBy ?? "relevance"}
            initialSortDirection={location.entitySortDirection ?? "desc"}
            initialSort={location.entitySort as SortCriterion<EntitySearchSortField>[] | undefined}
            initialOffset={location.offset ?? 0}
            initialDisplayMode={location.explorerDisplayMode ?? "list"}
            initialAnalysisView={location.explorerAnalysisView ?? "chart"}
            initialSelectedEntityId={location.entityId}
            invalidSelectedEntityId={location.invalidEntityId}
            selectedEntity={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
            selectedEntityLoading={routeEntity.isFetching && selectedEntity?.id !== location.entityId}
            selectedEntityError={routeEntity.error instanceof Error ? routeEntity.error.message : ""}
            onSearchChange={(query, entityTypes, reviewStatus, sortBy, sortDirection, offset, sort) =>
              navigate(
                {
                  workbench: "research",
                  view: "explorer",
                  query,
                  entityType: entityTypes.length === 1 ? (entityTypes[0] ?? "") : "",
                  entityTypes,
                  reviewStatus,
                  entitySort: sort,
                  entitySortBy: sortBy,
                  entitySortDirection: sortDirection,
                  offset,
                  entityId: null,
                  invalidEntityId: false,
                },
                true,
              )
            }
            onDisplayModeChange={(explorerDisplayMode) =>
              navigate({ ...location, explorerDisplayMode, offset: 0, entityId: null, invalidEntityId: false })
            }
            onAnalysisViewChange={(explorerAnalysisView) => navigate({ ...location, explorerAnalysisView })}
            onOpenEntity={openEntity}
            onOpenTargetPipeline={openTargetPipelineById}
            onSelectedEntityChange={(entity) => {
              navigate({ ...location, entityId: entity?.id ?? null, invalidEntityId: false });
              setSelectedEntity(entity);
            }}
            onOpenSpecializedSearch={navigate}
          />
        ) : null}
        {location.view === "chemistry" ? (
          location.invalidChemistrySavedSearchId ? (
            <ErrorState message="结构检索保存链接无效" />
          ) : location.chemistrySavedSearchId && routeChemistrySavedSearch.isPending ? (
            <Spinner label="正在恢复已保存结构检索" />
          ) : location.chemistrySavedSearchId && routeChemistrySavedSearch.error ? (
            <ErrorState
              message={
                routeChemistrySavedSearch.error instanceof Error
                  ? routeChemistrySavedSearch.error.message
                  : "已保存结构检索暂不可用"
              }
              retry={() => void routeChemistrySavedSearch.refetch()}
            />
          ) : location.chemistrySavedSearchId && routeChemistrySavedSearch.data?.query_type !== "chemistry_search" ? (
            <ErrorState message="保存检索类型与结构检索页面不匹配" />
          ) : (
            <ChemistryView
              onInspectEntity={openEntityById}
              initialSearch={
                routeChemistrySavedSearch.data?.query_type === "chemistry_search"
                  ? (routeChemistrySavedSearch.data.query_json as ChemistrySavedSearchQuery)
                  : null
              }
              savedSearchId={location.chemistrySavedSearchId}
              onSearchCommit={() =>
                location.chemistrySavedSearchId
                  ? navigate({ ...location, chemistrySavedSearchId: null, invalidChemistrySavedSearchId: false }, true)
                  : undefined
              }
              onSavedSearch={(saved) =>
                navigate({ ...location, chemistrySavedSearchId: saved.id, invalidChemistrySavedSearchId: false }, true)
              }
            />
          )
        ) : null}
        {location.view === "pipeline" ? (
          <PipelineView
            displayMode={location.pipelineDisplayMode ?? "list"}
            resultGrain={
              location.pipelineResultGrain ??
              (location.pipelineTargetEntityId ? ("drug" as const) : ("program" as const))
            }
            analysisDimension={location.pipelineAnalysisDimension ?? "all"}
            analysisView={location.pipelineAnalysisView ?? "chart"}
            analysisLimit={location.pipelineAnalysisLimit ?? 8}
            analysisStageScope={location.pipelineAnalysisStageScope ?? "overall"}
            targetAggregation={location.pipelineTargetAggregation ?? "all"}
            initialFilters={{
              query: location.query,
              modalities: location.pipelineModalities ?? [],
              innovationTypes: location.pipelineInnovationTypes ?? [],
              therapeuticAreas: location.pipelineTherapeuticAreas ?? [],
              drugCategories: location.pipelineDrugCategories ?? [],
              programStatus: location.pipelineProgramStatus ?? "",
              organizationRole: location.pipelineOrganizationRole ?? "",
              organizationType: location.pipelineOrganizationType ?? "",
              organizationCountryRegion: location.pipelineOrganizationCountryRegion ?? "",
              phase: location.phase ?? "",
              geography: location.geography ?? "",
              statusDateFrom: location.pipelineStatusDateFrom ?? "",
              statusDateTo: location.pipelineStatusDateTo ?? "",
              drugEntityId: location.pipelineDrugEntityId ?? "",
              targetEntityId: location.pipelineTargetEntityId ?? "",
              targetCombinationKey: location.pipelineTargetCombinationKey ?? "",
              diseaseEntityId: location.pipelineDiseaseEntityId ?? "",
              organizationEntityId: location.pipelineOrganizationEntityId ?? "",
              globalPhase: location.pipelineGlobalPhase ?? "",
              chinaPhase: location.pipelineChinaPhase ?? "",
              globalPhaseStartedFrom: location.pipelineGlobalPhaseStartedFrom ?? "",
              globalPhaseStartedTo: location.pipelineGlobalPhaseStartedTo ?? "",
              chinaPhaseStartedFrom: location.pipelineChinaPhaseStartedFrom ?? "",
              chinaPhaseStartedTo: location.pipelineChinaPhaseStartedTo ?? "",
              developmentRightsRegion: location.pipelineDevelopmentRightsRegion ?? "",
              commercializationRightsRegion: location.pipelineCommercializationRightsRegion ?? "",
              programTags: location.pipelineProgramTags ?? [],
              milestoneType: location.pipelineMilestoneType ?? "",
              milestoneFrom: location.pipelineMilestoneFrom ?? "",
              milestoneTo: location.pipelineMilestoneTo ?? "",
              hasClinicalResults: location.pipelineHasClinicalResults ?? "",
              clinicalResultEvaluation: location.pipelineClinicalResultEvaluation ?? "",
              hasDeal: location.pipelineHasDeal ?? "",
              dealCurrency: location.pipelineDealCurrency ?? "",
              dealTotalPotentialAmountMin: location.pipelineDealTotalPotentialAmountMin ?? "",
              dealTotalPotentialAmountMax: location.pipelineDealTotalPotentialAmountMax ?? "",
              sortBy: (location.pipelineSortBy ?? "status_date") as PipelineSearchFilters["sortBy"],
              sortDirection: location.pipelineSortDirection ?? "desc",
              sort: location.pipelineSort as PipelineSearchFilters["sort"],
              offset: location.offset ?? 0,
            }}
            onSearchChange={(filters) =>
              navigate({
                workbench: "research",
                view: "pipeline",
                query: filters.query,
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                pipelineModalities: filters.modalities,
                pipelineInnovationTypes: filters.innovationTypes,
                pipelineTherapeuticAreas: filters.therapeuticAreas,
                pipelineDrugCategories: filters.drugCategories,
                pipelineProgramStatus: filters.programStatus,
                pipelineOrganizationRole: filters.organizationRole,
                pipelineOrganizationType: filters.organizationType,
                pipelineOrganizationCountryRegion: filters.organizationCountryRegion,
                phase: filters.phase,
                geography: filters.geography,
                pipelineStatusDateFrom: filters.statusDateFrom,
                pipelineStatusDateTo: filters.statusDateTo,
                pipelineDrugEntityId: filters.drugEntityId,
                pipelineTargetEntityId: filters.targetEntityId,
                pipelineTargetCombinationKey: filters.targetCombinationKey,
                pipelineDiseaseEntityId: filters.diseaseEntityId,
                pipelineOrganizationEntityId: filters.organizationEntityId,
                pipelineGlobalPhase: filters.globalPhase,
                pipelineChinaPhase: filters.chinaPhase,
                pipelineGlobalPhaseStartedFrom: filters.globalPhaseStartedFrom,
                pipelineGlobalPhaseStartedTo: filters.globalPhaseStartedTo,
                pipelineChinaPhaseStartedFrom: filters.chinaPhaseStartedFrom,
                pipelineChinaPhaseStartedTo: filters.chinaPhaseStartedTo,
                pipelineDevelopmentRightsRegion: filters.developmentRightsRegion,
                pipelineCommercializationRightsRegion: filters.commercializationRightsRegion,
                pipelineProgramTags: filters.programTags,
                pipelineMilestoneType: filters.milestoneType,
                pipelineMilestoneFrom: filters.milestoneFrom,
                pipelineMilestoneTo: filters.milestoneTo,
                pipelineHasClinicalResults: filters.hasClinicalResults,
                pipelineClinicalResultEvaluation: filters.clinicalResultEvaluation,
                pipelineHasDeal: filters.hasDeal,
                pipelineDealCurrency: filters.dealCurrency,
                pipelineDealTotalPotentialAmountMin: filters.dealTotalPotentialAmountMin,
                pipelineDealTotalPotentialAmountMax: filters.dealTotalPotentialAmountMax,
                pipelineSort: filters.sort,
                pipelineSortBy: filters.sortBy,
                pipelineSortDirection: filters.sortDirection,
                pipelineDisplayMode: location.pipelineDisplayMode ?? "list",
                pipelineResultGrain:
                  location.pipelineResultGrain ?? (filters.targetEntityId ? ("drug" as const) : ("program" as const)),
                pipelineAnalysisDimension: location.pipelineAnalysisDimension ?? "all",
                pipelineAnalysisView: location.pipelineAnalysisView ?? "chart",
                pipelineAnalysisLimit: location.pipelineAnalysisLimit ?? 8,
                pipelineAnalysisStageScope: location.pipelineAnalysisStageScope ?? "overall",
                pipelineTargetAggregation: location.pipelineTargetAggregation ?? "all",
                offset: filters.offset,
              })
            }
            onDisplayModeChange={(displayMode) =>
              navigate({ ...location, pipelineDisplayMode: displayMode, offset: 0 })
            }
            onResultGrainChange={(resultGrain: PipelineResultGrain) =>
              navigate({ ...location, pipelineResultGrain: resultGrain, offset: 0 })
            }
            onAnalysisChange={(analysis) =>
              navigate({
                ...location,
                pipelineDisplayMode: "landscape",
                pipelineAnalysisDimension: analysis.dimension,
                pipelineAnalysisView: analysis.view,
                pipelineAnalysisLimit: analysis.limit,
                pipelineAnalysisStageScope: analysis.stageScope,
                pipelineTargetAggregation: analysis.targetAggregation,
                offset: 0,
              })
            }
            onOpenDrug={(entityId) => openDrugById(entityId, workspaceUrl(location))}
            onOpenEntity={openEntityById}
            onOpenTarget={openTargetById}
            onOpenDisease={openDiseaseById}
            onOpenOrganization={openOrganizationById}
            onOpenTrialsForDrug={(drugEntityId) =>
              navigate({
                workbench: "research",
                view: "trials",
                query: "",
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                trialRoleEntityId: drugEntityId,
                trialRoleEntityRole: "",
                trialId: null,
                invalidTrialId: false,
                trialSection: "overview",
                offset: 0,
              })
            }
            onOpenDealsForDrug={(drugEntityId) =>
              navigate({
                workbench: "research",
                view: "deals",
                query: "",
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                dealAssetEntityId: drugEntityId,
                dealId: null,
                invalidDealId: false,
                dealSection: "overview",
                offset: 0,
              })
            }
          />
        ) : null}
        {location.view === "trials" ? (
          <TrialsView
            displayMode={location.trialDisplayMode ?? "list"}
            analysisView={location.trialAnalysisView ?? "chart"}
            initialQuery={location.query}
            initialRegistry={location.registry ?? ""}
            initialStatus={location.trialStatus ?? ""}
            initialPhase={location.trialPhase ?? ""}
            initialStudyType={location.studyType ?? ""}
            initialAcronym={location.trialAcronym ?? ""}
            initialInitiationType={location.trialInitiationType ?? ""}
            initialTherapyLine={location.trialTherapyLine ?? ""}
            initialHasResults={location.trialHasResults ?? ""}
            initialResultEvaluation={location.trialResultEvaluation ?? ""}
            initialResultsPostedFrom={location.trialResultsPostedFrom ?? ""}
            initialResultsPostedTo={location.trialResultsPostedTo ?? ""}
            initialInvestigationalDrug={location.trialInvestigationalDrug ?? ""}
            initialCombinationDrug={location.trialCombinationDrug ?? ""}
            initialInvestigationalTarget={location.trialInvestigationalTarget ?? ""}
            initialCombinationTarget={location.trialCombinationTarget ?? ""}
            initialInvestigationalDrugEntityIds={trialRoleGroupIds(
              location,
              "investigational_drug",
              location.trialInvestigationalDrugEntityIds,
            )}
            initialCombinationDrugEntityIds={trialRoleGroupIds(
              location,
              "combination_drug",
              location.trialCombinationDrugEntityIds,
            )}
            initialInvestigationalTargetEntityIds={trialRoleGroupIds(
              location,
              "investigational_target",
              location.trialInvestigationalTargetEntityIds,
            )}
            initialCombinationTargetEntityIds={trialRoleGroupIds(
              location,
              "combination_target",
              location.trialCombinationTargetEntityIds,
            )}
            initialLinkedDrugModalities={location.trialLinkedDrugModalities ?? []}
            initialLinkedDrugInnovationTypes={location.trialLinkedDrugInnovationTypes ?? []}
            initialLinkedDrugCategories={location.trialLinkedDrugCategories ?? []}
            initialLinkedDrugProgramTags={location.trialLinkedDrugProgramTags ?? []}
            initialLinkedDrugGlobalPhase={location.trialLinkedDrugGlobalPhase ?? ""}
            initialLinkedDrugOrganizationCountryRegion={location.trialLinkedDrugOrganizationCountryRegion ?? ""}
            initialRoleEntityId={location.trialRoleEntityRole ? "" : (location.trialRoleEntityId ?? "")}
            initialRoleEntityIds={location.trialRoleEntityRole ? [] : (location.trialRoleEntityIds ?? [])}
            initialRoleEntityRole={location.trialRoleEntityRole ? "" : (location.trialRoleEntityRole ?? "")}
            initialHasKeyResult={location.trialHasKeyResult ?? ""}
            initialPublicationId={location.trialPublicationId ?? ""}
            initialConference={location.trialConference ?? ""}
            initialDisclosedFrom={location.trialDisclosedFrom ?? ""}
            initialDisclosedTo={location.trialDisclosedTo ?? ""}
            initialSortBy={(location.trialSortBy ?? "last_update_posted") as TrialSortField}
            initialSortDirection={(location.trialSortDirection ?? "desc") as TrialSortDirection}
            initialSort={location.trialSort as SortCriterion<TrialSortField>[] | undefined}
            initialOffset={location.offset ?? 0}
            selectedTrialId={location.trialId ?? null}
            activeSection={location.trialSection ?? "overview"}
            onSearchChange={(change) =>
              navigate({
                workbench: "research",
                view: "trials",
                query: change.query,
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                registry: change.registry,
                trialStatus: change.status,
                trialPhase: change.phase,
                studyType: change.studyType,
                trialAcronym: change.acronym,
                trialInitiationType: change.initiationType,
                trialTherapyLine: change.therapyLine,
                trialHasResults: change.hasResults,
                trialResultEvaluation: change.resultEvaluation,
                trialResultsPostedFrom: change.resultsPostedFrom,
                trialResultsPostedTo: change.resultsPostedTo,
                trialInvestigationalDrug: change.investigationalDrug,
                trialCombinationDrug: change.combinationDrug,
                trialInvestigationalTarget: change.investigationalTarget,
                trialCombinationTarget: change.combinationTarget,
                trialInvestigationalDrugEntityIds: change.investigationalDrugEntityIds,
                trialCombinationDrugEntityIds: change.combinationDrugEntityIds,
                trialInvestigationalTargetEntityIds: change.investigationalTargetEntityIds,
                trialCombinationTargetEntityIds: change.combinationTargetEntityIds,
                trialLinkedDrugModalities: change.linkedDrugModalities,
                trialLinkedDrugInnovationTypes: change.linkedDrugInnovationTypes,
                trialLinkedDrugCategories: change.linkedDrugCategories,
                trialLinkedDrugProgramTags: change.linkedDrugProgramTags,
                trialLinkedDrugGlobalPhase: change.linkedDrugGlobalPhase,
                trialLinkedDrugOrganizationCountryRegion: change.linkedDrugOrganizationCountryRegion,
                trialRoleEntityId: change.roleEntityId,
                trialRoleEntityIds: change.roleEntityIds,
                trialRoleEntityRole: change.roleEntityRole,
                trialHasKeyResult: change.hasKeyResult,
                trialPublicationId: change.publicationId,
                trialConference: change.conference,
                trialDisclosedFrom: change.disclosedFrom,
                trialDisclosedTo: change.disclosedTo,
                trialSort: change.sort,
                trialSortBy: change.sortBy,
                trialSortDirection: change.sortDirection,
                trialDisplayMode: location.trialDisplayMode ?? "list",
                trialId: null,
                invalidTrialId: false,
                offset: change.offset,
              })
            }
            onTrialChange={(trialId) =>
              navigate(
                {
                  ...location,
                  trialId,
                  invalidTrialId: false,
                  trialSection: "overview",
                },
                trialId === null,
              )
            }
            returnLabel={trialReturnLabel(activeTrialReturnLocation)}
            onReturn={activeTrialReturnLocation ? () => navigate(activeTrialReturnLocation, true, true) : undefined}
            onSectionChange={(trialSection, replace = false) => navigate({ ...location, trialSection }, replace)}
            onOpenEntity={openEntityById}
            onOpenDrug={(entityId) => openDrugById(entityId, location.trialId ? workspaceUrl(location) : undefined)}
            onOpenTarget={(entityId) => openTargetById(entityId, location.trialId ? workspaceUrl(location) : undefined)}
            onOpenDisease={openDiseaseById}
            onOpenOrganization={openOrganizationById}
            onAnalysisViewChange={(trialAnalysisView) =>
              navigate({ ...location, trialAnalysisView, trialId: null, invalidTrialId: false })
            }
            onDisplayModeChange={(trialDisplayMode) =>
              navigate({ ...location, trialDisplayMode, trialId: null, invalidTrialId: false, offset: 0 })
            }
          />
        ) : null}
        {location.view === "patents" ? (
          <PatentsView
            initialQuery={location.query}
            initialEntityId={location.patentEntityId ?? ""}
            initialApplicant={location.applicant ?? ""}
            initialLegalStatus={location.legalStatus ?? ""}
            initialPriorityFrom={location.patentPriorityFrom ?? ""}
            initialPriorityTo={location.patentPriorityTo ?? ""}
            initialExpirationFrom={location.patentExpirationFrom ?? ""}
            initialExpirationTo={location.patentExpirationTo ?? ""}
            initialSortBy={(location.patentSortBy ?? "priority_date") as PatentSortField}
            initialSortDirection={(location.patentSortDirection ?? "desc") as PatentSortDirection}
            initialSort={location.patentSort as SortCriterion<PatentSortField>[] | undefined}
            initialOffset={location.offset ?? 0}
            displayMode={location.patentDisplayMode ?? "list"}
            analysisView={location.patentAnalysisView ?? "chart"}
            onDisplayModeChange={(patentDisplayMode) =>
              navigate({ ...location, patentDisplayMode, patentId: null, invalidPatentId: false, offset: 0 })
            }
            onAnalysisViewChange={(patentAnalysisView) =>
              navigate({ ...location, patentAnalysisView, patentId: null, invalidPatentId: false })
            }
            selectedPatentId={location.patentId ?? null}
            activeSection={location.patentSection ?? "overview"}
            onSearchChange={(input, offset) =>
              navigate({
                workbench: "research",
                view: "patents",
                query: input.query,
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                patentEntityId: input.entityId,
                applicant: input.applicant,
                legalStatus: input.legalStatus,
                patentPriorityFrom: input.priorityFrom,
                patentPriorityTo: input.priorityTo,
                patentExpirationFrom: input.expirationFrom,
                patentExpirationTo: input.expirationTo,
                patentSort: input.sort,
                patentSortBy: input.sortBy,
                patentSortDirection: input.sortDirection,
                patentDisplayMode: input.displayMode,
                patentAnalysisView: input.analysisView,
                patentId: null,
                invalidPatentId: false,
                offset,
              })
            }
            onPatentChange={(patentId) =>
              navigate(
                {
                  ...location,
                  patentId,
                  invalidPatentId: false,
                  patentSection: "overview",
                },
                patentId === null,
              )
            }
            onSectionChange={(patentSection, replace = false) => navigate({ ...location, patentSection }, replace)}
            onOpenEntity={openEntityById}
            onOpenDrug={openDrugById}
            onOpenTarget={openTargetById}
            onOpenDisease={openDiseaseById}
            onOpenOrganization={openOrganizationById}
          />
        ) : null}
        {location.view === "deals" ? (
          <DealsView
            displayMode={location.dealDisplayMode ?? "list"}
            analysisDimension={(location.dealAnalysisDimension ?? "all") as DealAnalysisDimension}
            analysisView={(location.dealAnalysisView ?? "chart") as DealAnalysisView}
            analysisLimit={(location.dealAnalysisLimit ?? 8) as DealAnalysisLimit}
            initialFilters={{
              query: location.query,
              dealType: location.dealType ?? "",
              status: location.dealStatus ?? "",
              direction: location.dealDirection ?? "",
              directionReferenceJurisdiction: location.dealDirectionReferenceJurisdiction ?? "",
              territory: location.dealTerritory ?? "",
              assetEntityId: location.dealAssetEntityId ?? "",
              targetEntityId: location.dealTargetEntityId ?? "",
              diseaseEntityId: location.dealDiseaseEntityId ?? "",
              assetModalities: location.dealAssetModalities ?? [],
              assetProgramTags: location.dealAssetProgramTags ?? [],
              party: location.dealParty ?? "",
              partyEntityId: location.dealPartyEntityId ?? "",
              partyRole: location.dealPartyRole ?? "",
              partyCountryRegion: location.dealPartyCountryRegion ?? "",
              partyOrganizationType: location.dealPartyOrganizationType ?? "",
              developmentPhaseAtTransaction: location.dealDevelopmentPhaseAtTransaction ?? "",
              currentDevelopmentPhase: location.dealCurrentDevelopmentPhase ?? "",
              rightType: location.dealRightType ?? "",
              rightsTerritory: location.dealRightsTerritory ?? "",
              currency: location.dealCurrency ?? "",
              announcedFrom: location.dealAnnouncedFrom ?? "",
              announcedTo: location.dealAnnouncedTo ?? "",
              terminatedFrom: location.dealTerminatedFrom ?? "",
              terminatedTo: location.dealTerminatedTo ?? "",
              sourceUpdatedFrom: location.dealSourceUpdatedFrom ?? "",
              sourceUpdatedTo: location.dealSourceUpdatedTo ?? "",
              upfrontAmountMin: location.dealUpfrontAmountMin ?? "",
              upfrontAmountMax: location.dealUpfrontAmountMax ?? "",
              totalPotentialAmountMin: location.dealTotalPotentialAmountMin ?? "",
              totalPotentialAmountMax: location.dealTotalPotentialAmountMax ?? "",
              sortBy: (location.dealSortBy ?? "announced_at") as DealSearchFilters["sortBy"],
              sortDirection: location.dealSortDirection ?? "desc",
              sort: location.dealSort as DealSearchFilters["sort"],
            }}
            initialOffset={location.offset ?? 0}
            selectedDealId={location.dealId ?? null}
            activeSection={location.dealSection ?? "overview"}
            onSearchChange={(filters, offset) =>
              navigate({
                workbench: "research",
                view: "deals",
                query: filters.query,
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                dealType: filters.dealType,
                dealStatus: filters.status,
                dealDirection: filters.direction,
                dealDirectionReferenceJurisdiction: filters.directionReferenceJurisdiction,
                dealTerritory: filters.territory,
                dealAssetEntityId: filters.assetEntityId,
                dealTargetEntityId: filters.targetEntityId,
                dealDiseaseEntityId: filters.diseaseEntityId,
                dealAssetModalities: filters.assetModalities,
                dealAssetProgramTags: filters.assetProgramTags,
                dealParty: filters.party,
                dealPartyEntityId: filters.partyEntityId,
                dealPartyRole: filters.partyRole,
                dealPartyCountryRegion: filters.partyCountryRegion,
                dealPartyOrganizationType: filters.partyOrganizationType,
                dealDevelopmentPhaseAtTransaction: filters.developmentPhaseAtTransaction,
                dealCurrentDevelopmentPhase: filters.currentDevelopmentPhase,
                dealRightType: filters.rightType,
                dealRightsTerritory: filters.rightsTerritory,
                dealCurrency: filters.currency,
                dealAnnouncedFrom: filters.announcedFrom,
                dealAnnouncedTo: filters.announcedTo,
                dealTerminatedFrom: filters.terminatedFrom,
                dealTerminatedTo: filters.terminatedTo,
                dealSourceUpdatedFrom: filters.sourceUpdatedFrom,
                dealSourceUpdatedTo: filters.sourceUpdatedTo,
                dealUpfrontAmountMin: filters.upfrontAmountMin,
                dealUpfrontAmountMax: filters.upfrontAmountMax,
                dealTotalPotentialAmountMin: filters.totalPotentialAmountMin,
                dealTotalPotentialAmountMax: filters.totalPotentialAmountMax,
                dealSort: filters.sort,
                dealSortBy: filters.sortBy,
                dealSortDirection: filters.sortDirection,
                dealDisplayMode: location.dealDisplayMode ?? "list",
                dealAnalysisDimension: location.dealAnalysisDimension ?? "all",
                dealAnalysisView: location.dealAnalysisView ?? "chart",
                dealAnalysisLimit: location.dealAnalysisLimit ?? 8,
                dealId: null,
                invalidDealId: false,
                offset,
              })
            }
            onDisplayModeChange={(dealDisplayMode) => navigate({ ...location, dealDisplayMode, offset: 0 })}
            onAnalysisChange={({ dimension, view, limit }) =>
              navigate({
                ...location,
                dealDisplayMode: "landscape",
                dealAnalysisDimension: dimension,
                dealAnalysisView: view,
                dealAnalysisLimit: limit,
                offset: 0,
              })
            }
            onDealChange={(dealId) =>
              navigate(
                {
                  ...location,
                  dealId,
                  invalidDealId: false,
                  dealSection: "overview",
                },
                dealId === null,
              )
            }
            onSectionChange={(dealSection, replace = false) => navigate({ ...location, dealSection }, replace)}
            onOpenEntity={openEntityById}
            onOpenDrug={openDrugById}
            onOpenTarget={openTargetById}
            onOpenDisease={openDiseaseById}
            onOpenOrganization={openOrganizationById}
          />
        ) : null}
        {location.view === "regulatory" ? (
          <RegulatoryView
            initialFilters={{
              query: location.query,
              agency: location.regulatoryAgency ?? "",
              jurisdiction: location.regulatoryJurisdiction ?? "",
              eventType: location.regulatoryEventType ?? "",
              displayMode: location.regulatoryDisplayMode ?? "list",
              analysisView: location.regulatoryAnalysisView ?? "chart",
              status: location.regulatoryStatus ?? "",
              designationType: location.regulatoryDesignationType ?? "",
              labelChangeType: location.regulatoryLabelChangeType ?? "",
              boxedWarning: location.regulatoryBoxedWarning ?? "",
              safetySignalType: location.regulatorySafetySignalType ?? "",
              safetySeverity: location.regulatorySafetySeverity ?? "",
              safetyStatus: location.regulatorySafetyStatus ?? "",
              decisionFrom: location.regulatoryDecisionFrom ?? "",
              decisionTo: location.regulatoryDecisionTo ?? "",
              sourceUpdatedFrom: location.regulatorySourceUpdatedFrom ?? "",
              sourceUpdatedTo: location.regulatorySourceUpdatedTo ?? "",
              sortBy: (location.regulatorySortBy ?? "decision_date") as RegulatorySearchFilters["sortBy"],
              sortDirection: location.regulatorySortDirection ?? "desc",
              sort: location.regulatorySort as RegulatorySearchFilters["sort"],
            }}
            initialOffset={location.offset ?? 0}
            selectedEventId={location.regulatoryEventId ?? null}
            comparedEventIds={location.regulatoryCompareIds ?? []}
            onSearchChange={(filters, offset) =>
              navigate({
                ...location,
                query: filters.query,
                regulatoryAgency: filters.agency,
                regulatoryJurisdiction: filters.jurisdiction,
                regulatoryEventType: filters.eventType,
                regulatoryDisplayMode: filters.displayMode,
                regulatoryAnalysisView: filters.analysisView,
                regulatoryStatus: filters.status,
                regulatoryDesignationType: filters.designationType,
                regulatoryLabelChangeType: filters.labelChangeType,
                regulatoryBoxedWarning: filters.boxedWarning,
                regulatorySafetySignalType: filters.safetySignalType,
                regulatorySafetySeverity: filters.safetySeverity,
                regulatorySafetyStatus: filters.safetyStatus,
                regulatoryDecisionFrom: filters.decisionFrom,
                regulatoryDecisionTo: filters.decisionTo,
                regulatorySourceUpdatedFrom: filters.sourceUpdatedFrom,
                regulatorySourceUpdatedTo: filters.sourceUpdatedTo,
                regulatorySort: filters.sort,
                regulatorySortBy: filters.sortBy,
                regulatorySortDirection: filters.sortDirection,
                offset,
              })
            }
            onEventChange={(regulatoryEventId) =>
              navigate(
                {
                  ...location,
                  regulatoryEventId,
                  invalidRegulatoryEventId: false,
                },
                regulatoryEventId === null,
              )
            }
            onCompareChange={(regulatoryCompareIds) => navigate({ ...location, regulatoryCompareIds })}
            onOpenEntity={openEntityById}
            onOpenDrug={openDrugById}
            onOpenTarget={openTargetById}
            onOpenDisease={openDiseaseById}
            onOpenOrganization={openOrganizationById}
          />
        ) : null}
        {location.view === "epidemiology" ? (
          <EpidemiologyView
            initialFilters={{
              query: location.query,
              diseaseEntityId: location.epidemiologyDiseaseEntityId ?? "",
              measure: location.epidemiologyMeasure ?? "",
              geography: location.epidemiologyGeography ?? "",
              unit: location.epidemiologyUnit ?? "",
              patientPopulationId: location.epidemiologyPatientPopulationId ?? "",
              populationScope: location.epidemiologyPopulationScope ?? "",
              ageGroup: location.epidemiologyAgeGroup ?? "",
              sex: location.epidemiologySex ?? "",
              periodStartFrom: location.epidemiologyPeriodStartFrom ?? "",
              periodEndTo: location.epidemiologyPeriodEndTo ?? "",
              sortBy: (location.epidemiologySortBy ?? "period_end") as EpidemiologyFilters["sortBy"],
              sortDirection: location.epidemiologySortDirection ?? "desc",
              sort: location.epidemiologySort as EpidemiologyFilters["sort"],
              displayMode: location.epidemiologyDisplayMode ?? "list",
              analysisView: location.epidemiologyAnalysisView ?? "chart",
            }}
            initialOffset={location.offset ?? 0}
            onSearchChange={(filters, offset) =>
              navigate({
                workbench: "research",
                view: "epidemiology",
                query: filters.query,
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                epidemiologyDiseaseEntityId: filters.diseaseEntityId,
                epidemiologyMeasure: filters.measure,
                epidemiologyDisplayMode: filters.displayMode,
                epidemiologyAnalysisView: filters.analysisView,
                epidemiologyGeography: filters.geography,
                epidemiologyUnit: filters.unit,
                epidemiologyPatientPopulationId: filters.patientPopulationId,
                epidemiologyPopulationScope: filters.populationScope,
                epidemiologyAgeGroup: filters.ageGroup,
                epidemiologySex: filters.sex,
                epidemiologyPeriodStartFrom: filters.periodStartFrom,
                epidemiologyPeriodEndTo: filters.periodEndTo,
                epidemiologySort: filters.sort,
                epidemiologySortBy: filters.sortBy,
                epidemiologySortDirection: filters.sortDirection,
                offset,
              })
            }
            onOpenEntity={openEntityById}
            onOpenDrug={openDrugById}
            onOpenTarget={openTargetById}
            onOpenDisease={openDiseaseById}
            onOpenOrganization={openOrganizationById}
          />
        ) : null}
        {location.view === "news" ? (
          <NewsView
            initialFilters={{
              query: location.query,
              entityId: location.newsEntityId ?? "",
              eventType: location.newsEventType ?? "",
              publisher: location.newsPublisher ?? "",
              language: location.newsLanguage ?? "",
              venue: location.newsVenue ?? "",
              publishedFrom: location.newsPublishedFrom ?? "",
              publishedTo: location.newsPublishedTo ?? "",
              contentScope: location.newsContentScope ?? "",
              displayMode: location.newsDisplayMode ?? "list",
              analysisView: location.newsAnalysisView ?? "chart",
              sortBy: (location.newsSortBy ?? "published_at") as NewsSearchFilters["sortBy"],
              sortDirection: location.newsSortDirection ?? "desc",
              sort: location.newsSort as NewsSearchFilters["sort"],
            }}
            initialOffset={location.offset ?? 0}
            selectedNewsEventId={location.newsEventId ?? null}
            onSearchChange={(filters, offset) =>
              navigate({
                workbench: "research",
                view: "news",
                query: filters.query,
                entityType: "",
                reviewStatus: "",
                entityId: null,
                invalidEntityId: false,
                newsEntityId: filters.entityId,
                newsEventType: filters.eventType,
                newsAnalysisView: filters.analysisView,
                newsPublisher: filters.publisher,
                newsLanguage: filters.language,
                newsVenue: filters.venue,
                newsPublishedFrom: filters.publishedFrom,
                newsPublishedTo: filters.publishedTo,
                newsContentScope: filters.contentScope,
                newsDisplayMode: filters.displayMode,
                newsSort: filters.sort,
                newsSortBy: filters.sortBy,
                newsSortDirection: filters.sortDirection,
                newsEventId: null,
                invalidNewsEventId: false,
                offset,
              })
            }
            onNewsEventChange={(newsEventId) =>
              navigate(
                {
                  ...location,
                  newsEventId,
                  invalidNewsEventId: false,
                },
                newsEventId === null,
              )
            }
            onOpenEntity={openEntityById}
            onOpenDrug={openDrugById}
            onOpenTarget={openTargetById}
            onOpenDisease={openDiseaseById}
            onOpenOrganization={openOrganizationById}
          />
        ) : null}
        {location.view === "target" ? (
          routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
            <Spinner label="正在恢复靶点深链接" />
          ) : location.invalidEntityId || routeEntity.error ? (
            <ErrorState
              message={
                location.invalidEntityId
                  ? "链接中的实体 ID 无效"
                  : routeEntity.error instanceof Error
                    ? routeEntity.error.message
                    : "靶点链接加载失败"
              }
              retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
            />
          ) : (
            <TargetView
              target={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
              activeSection={location.targetSection ?? "overview"}
              onSectionChange={(targetSection) => navigate({ ...location, targetSection })}
              initialPipelineFilters={pipelineFiltersFromLocation(location, location.entityId ?? "")}
              onPipelineSearchChange={(filters) => navigate(locationWithPipelineFilters(location, filters), true)}
              onPipelineLandscapeFilterApply={(filters, targetPipelineDisplayMode) =>
                navigate({
                  ...locationWithPipelineFilters(location, filters),
                  targetPipelineDisplayMode,
                  offset: 0,
                })
              }
              initialPipelineDisplayMode={location.targetPipelineDisplayMode ?? "drug"}
              onPipelineDisplayModeChange={(targetPipelineDisplayMode) =>
                navigate({
                  ...location,
                  targetPipelineDisplayMode,
                  offset: 0,
                })
              }
              initialPipelineAnalysis={{
                dimension: location.pipelineAnalysisDimension ?? "all",
                view: location.pipelineAnalysisView ?? "chart",
                limit: location.pipelineAnalysisLimit ?? 20,
                stageScope: location.pipelineAnalysisStageScope ?? "overall",
                targetAggregation: location.pipelineTargetAggregation ?? "all",
              }}
              onPipelineAnalysisChange={(analysis) =>
                navigate({
                  ...location,
                  targetPipelineDisplayMode: "landscape",
                  pipelineAnalysisDimension: analysis.dimension,
                  pipelineAnalysisView: analysis.view,
                  pipelineAnalysisLimit: analysis.limit,
                  pipelineAnalysisStageScope: analysis.stageScope,
                  pipelineTargetAggregation: analysis.targetAggregation,
                  offset: 0,
                })
              }
              onOpenEntity={openEntityById}
              onOpenDrug={(entityId) => openDrugById(entityId, workspaceUrl(location))}
              onOpenTarget={openTargetById}
              onOpenDisease={openDiseaseById}
              onOpenOrganization={openOrganizationById}
              onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
              onOpenPatent={openPatentFamilyById}
              onOpenDeal={openDealById}
              onOpenRegulatoryEvent={openRegulatoryEventById}
              onOpenNewsEvent={openNewsEventById}
              returnLabel={
                activeTargetReturnLocation?.view === "trials"
                  ? "返回临床试验"
                  : activeTargetReturnLocation
                    ? "返回药物档案"
                    : undefined
              }
              onReturn={activeTargetReturnLocation ? () => navigate(activeTargetReturnLocation, true, true) : undefined}
              onOpenEvidence={(query) =>
                navigate({
                  workbench: "research",
                  view: "evidence",
                  query,
                  entityType: "",
                  reviewStatus: "",
                  entityId: null,
                  invalidEntityId: false,
                  evidenceDatasetKeys: [],
                  evidenceDocumentId: null,
                  evidenceChunkIndex: null,
                })
              }
              onOpenComparison={(collectionId, entityIds) =>
                navigate(
                  {
                    ...location,
                    view: "collections",
                    query: "",
                    entityType: "",
                    reviewStatus: "",
                    entityId: null,
                    invalidEntityId: false,
                    collectionId,
                    invalidCollectionId: false,
                    collectionCompareEntityIds: entityIds.slice(0, 4),
                  },
                  false,
                  true,
                )
              }
            />
          )
        ) : null}
        {location.view === "drug" ? (
          routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
            <Spinner label="正在恢复药物档案深链接" />
          ) : location.invalidEntityId || routeEntity.error ? (
            <ErrorState
              message={
                location.invalidEntityId
                  ? "链接中的药物 ID 无效"
                  : routeEntity.error instanceof Error
                    ? routeEntity.error.message
                    : "药物档案链接加载失败"
              }
              retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
            />
          ) : (
            <DrugView
              drug={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
              activeSection={location.drugSection ?? "overview"}
              programOffset={location.offset ?? 0}
              onProgramOffsetChange={(offset) => navigate({ ...location, offset })}
              onSectionChange={(drugSection, replace = false) =>
                navigate({ ...location, drugSection, offset: 0 }, replace)
              }
              onOpenEntity={openEntityById}
              onOpenDrug={(entityId) => openDrugById(entityId, location.returnTo)}
              onOpenTarget={(entityId) => openTargetById(entityId, workspaceUrl(location))}
              onOpenDisease={openDiseaseById}
              onOpenOrganization={openOrganizationById}
              onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
              onOpenPatent={openPatentFamilyById}
              onOpenDeal={openDealById}
              onOpenRegulatoryEvent={openRegulatoryEventById}
              onOpenNewsEvent={openNewsEventById}
              returnTargetId={
                activeDrugReturnLocation?.view === "target"
                  ? (activeDrugReturnLocation.entityId ?? undefined)
                  : undefined
              }
              onReturnToTarget={
                activeDrugReturnLocation?.view === "target"
                  ? () => navigate(activeDrugReturnLocation, true, true)
                  : undefined
              }
              returnLabel={
                activeDrugReturnLocation?.view === "pipeline"
                  ? "返回管线查询"
                  : activeDrugReturnLocation?.view === "collections"
                    ? "返回对比列表"
                    : activeDrugReturnLocation?.view === "trials"
                      ? "返回临床试验"
                      : undefined
              }
              onReturn={
                activeDrugReturnLocation?.view === "pipeline" ||
                activeDrugReturnLocation?.view === "collections" ||
                activeDrugReturnLocation?.view === "trials"
                  ? () => navigate(activeDrugReturnLocation, true, true)
                  : undefined
              }
            />
          )
        ) : null}
        {location.view === "company" ? (
          routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
            <Spinner label="正在恢复公司档案深链接" />
          ) : location.invalidEntityId || routeEntity.error ? (
            <ErrorState
              message={
                location.invalidEntityId
                  ? "链接中的公司 ID 无效"
                  : routeEntity.error instanceof Error
                    ? routeEntity.error.message
                    : "公司档案链接加载失败"
              }
              retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
            />
          ) : (
            <CompanyView
              company={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
              activeSection={location.companySection ?? "overview"}
              onSectionChange={(companySection, replace = false) => navigate({ ...location, companySection }, replace)}
              onOpenEntity={openEntityById}
              onOpenDrug={openDrugById}
              onOpenTarget={openTargetById}
              onOpenDisease={openDiseaseById}
              onOpenOrganization={openOrganizationById}
              onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
              onOpenPatent={openPatentFamilyById}
              onOpenDeal={openDealById}
              onOpenRegulatoryEvent={openRegulatoryEventById}
              onOpenNewsEvent={openNewsEventById}
            />
          )
        ) : null}
        {location.view === "disease" ? (
          routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
            <Spinner label="正在恢复疾病档案深链接" />
          ) : location.invalidEntityId || routeEntity.error ? (
            <ErrorState
              message={
                location.invalidEntityId
                  ? "链接中的疾病 ID 无效"
                  : routeEntity.error instanceof Error
                    ? routeEntity.error.message
                    : "疾病档案链接加载失败"
              }
              retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
            />
          ) : (
            <DiseaseView
              disease={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
              activeSection={location.diseaseSection ?? "overview"}
              onSectionChange={(diseaseSection, replace = false) => navigate({ ...location, diseaseSection }, replace)}
              onOpenEpidemiology={openEpidemiologyForDisease}
              onOpenEntity={openEntityById}
              onOpenDrug={openDrugById}
              onOpenTarget={openTargetById}
              onOpenDisease={openDiseaseById}
              onOpenOrganization={openOrganizationById}
              onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
              onOpenPatent={openPatentFamilyById}
              onOpenDeal={openDealById}
              onOpenRegulatoryEvent={openRegulatoryEventById}
              onOpenNewsEvent={openNewsEventById}
            />
          )
        ) : null}
        {location.view === "entity" ? (
          routeEntity.isFetching && selectedEntity?.id !== location.entityId ? (
            <Spinner label="正在恢复领域档案深链接" />
          ) : location.invalidEntityId || routeEntity.error ? (
            <ErrorState
              message={
                location.invalidEntityId
                  ? "链接中的实体 ID 无效"
                  : routeEntity.error instanceof Error
                    ? routeEntity.error.message
                    : "领域档案链接加载失败"
              }
              retry={location.entityId && !location.invalidEntityId ? () => void routeEntity.refetch() : undefined}
            />
          ) : (
            <EntityDossierView
              entity={selectedEntity?.id === location.entityId ? selectedEntity : (routeEntity.data ?? null)}
              activeSection={location.entitySection ?? "overview"}
              onSectionChange={(entitySection, replace = false) => navigate({ ...location, entitySection }, replace)}
              onOpenEntity={openEntityById}
              onOpenDrug={openDrugById}
              onOpenTarget={openTargetById}
              onOpenDisease={openDiseaseById}
              onOpenOrganization={openOrganizationById}
              onOpenTrial={(trialId) => openTrialById(trialId, workspaceUrl(location))}
              onOpenPatent={openPatentFamilyById}
              onOpenDeal={openDealById}
              onOpenRegulatoryEvent={openRegulatoryEventById}
              onOpenNewsEvent={openNewsEventById}
            />
          )
        ) : null}
        {location.view === "evidence" ? (
          <EvidenceView
            initialQuery={location.query}
            initialDatasetKeys={location.evidenceDatasetKeys}
            initialDocumentId={location.evidenceDocumentId}
            initialChunkIndex={location.evidenceChunkIndex}
            onLocationChange={(next) =>
              navigate({
                ...location,
                view: "evidence",
                query: next.query,
                entityId: null,
                invalidEntityId: false,
                evidenceDatasetKeys: next.datasetKeys,
                evidenceDocumentId: next.documentId,
                evidenceChunkIndex: next.chunkIndex,
              })
            }
          />
        ) : null}
        {location.view === "knowledge" ? (
          <KnowledgeView
            initialQuery={location.query}
            initialPageId={location.knowledgePageId}
            initialPanel={location.knowledgePanel ?? "document"}
            initialVersionNumber={location.knowledgeVersionNumber}
            invalidPageId={location.invalidKnowledgePageId}
            onLocationChange={(next) =>
              navigate({
                ...location,
                view: "knowledge",
                query: next.query,
                entityId: null,
                invalidEntityId: false,
                knowledgePageId: next.pageId,
                invalidKnowledgePageId: false,
                knowledgePanel: next.panel,
                knowledgeVersionNumber: next.versionNumber,
              })
            }
          />
        ) : null}
        {location.view === "monitoring" ? (
          <MonitoringView
            user={user}
            activeTab={location.monitoringTab ?? "alerts"}
            onOpenEntity={openEntityById}
            onOpenSearch={openSavedSearch}
            onTabChange={(monitoringTab) => {
              if (monitoringTab !== (location.monitoringTab ?? "alerts")) {
                navigate({ ...location, monitoringTab });
              }
            }}
          />
        ) : null}
        {location.view === "collections" ? (
          <CollectionsView
            activeCollectionId={location.collectionId ?? null}
            comparedEntityIds={location.collectionCompareEntityIds ?? []}
            onLocationChange={(collectionId, collectionCompareEntityIds, replace = false) =>
              navigate(
                {
                  ...location,
                  collectionId,
                  invalidCollectionId: false,
                  collectionCompareEntityIds,
                },
                replace,
                true,
              )
            }
            onOpenEntity={(entity) =>
              entity.entity_type === "drug" ? openDrugById(entity.id, workspaceUrl(location)) : openEntity(entity)
            }
          />
        ) : null}
      </Suspense>
    </WorkspaceShell>
  );
}
