import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  BarChart3,
  BookmarkPlus,
  CalendarDays,
  ExternalLink,
  FileText,
  List,
  MapPin,
  Search,
  Users,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { ClinicalTrialLandscape } from "../components/ClinicalTrialLandscape";
import {
  EmptyState,
  ErrorState,
  formatDate,
  ProfessionalQueryState,
  QueryRefreshButton,
  Spinner,
  StatusBadge,
} from "../components/common";
import { DomainExportControl } from "../components/DomainExportControl";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { EntityMultiFilterSelect } from "../components/EntityMultiFilterSelect";
import { FacetMultiSelect } from "../components/FacetMultiSelect";
import { InlineEntityLinks } from "../components/InlineEntityLinks";
import { QueryResultSummary } from "../components/QueryResultSummary";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import { SecondaryFilters } from "../components/SecondaryFilters";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { type SortCriterion, sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import {
  hasTrialSearchFilter,
  loadTrialDetail,
  type SortDirection,
  saveClinicalTrialSearch,
  searchTrials,
  type TrialSavedSearchInput,
  type TrialSortField,
  trialKeys,
  trialSortFields,
} from "../lib/contracts/trials";
import { facetOptions } from "../lib/facets";
import type {
  ClinicalTrialDetailRead,
  ClinicalTrialSearchItemRead,
  EntityType,
  TrialResultEvaluation,
} from "../lib/generated";
import { trialLinkedPhaseLabels as developmentPhaseLabels } from "../lib/phasePresentation";
import { programTagLabel, publicProgramTags } from "../lib/programDisplay";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { clinicalTrialPhaseLabel, clinicalTrialStatusLabel, clinicalTrialStudyTypeLabel } from "../lib/trialDisplay";
import {
  trialInitiationTypeLabels as initiationTypeLabels,
  trialKeyResultLabels as keyResultLabels,
  trialResultEvaluationLabels as resultEvaluationLabels,
  trialTherapyLineLabels as therapyLineLabels,
} from "../lib/trialFilters";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { TrialDossierSection } from "../lib/workspaceRouting";

const PAGE_SIZE = 100;
type TrialEntityOpener = (entityType: EntityType, entityId: string) => void;
const trialRowId = (trial: ClinicalTrialSearchItemRead) => trial.id;
const trialEntityId = (trial: ClinicalTrialSearchItemRead) => trial.entity_id;
const defaultTrialSorting: SortingState = [{ id: "last_update_posted", desc: true }];
const appliedFilterLabels = {
  q: "关键词",
  registry: "注册平台",
  status: "招募状态",
  phase: "临床分期",
  study_type: "研究类型",
  acronym: "试验简称",
  initiation_type: "发起类型",
  therapy_line: "治疗线次",
  has_results: "结果发布",
  result_evaluation: "结果最优评价",
  results_posted_from: "结果发布日期",
  results_posted_to: "结果发布日期",
  investigational_drug: "试验药物",
  combination_drug: "联用药物",
  investigational_target: "试验靶点",
  combination_target: "联用靶点",
  investigational_drug_entity_ids: "试验药物（任一）",
  combination_drug_entity_ids: "联用药物（任一）",
  investigational_target_entity_ids: "试验靶点（任一）",
  combination_target_entity_ids: "联用靶点（任一）",
  linked_drug_modality: "关联药物 Modality",
  linked_drug_innovation_type: "关联药物创新类型",
  linked_drug_category: "关联药物类别",
  linked_drug_program_tag: "关联药物标签",
  linked_drug_global_phase: "关联药物全球阶段",
  linked_drug_organization_country_region: "关联药物研发机构国家/地区",
  role_entity_id: "关联药物",
  role_entity_ids: "关联药物（任一）",
  role_entity_role: "药物角色",
  has_key_result: "关键结果",
  publication_id: "发表编号",
  conference: "会议",
  disclosed_from: "披露日期",
  disclosed_to: "披露日期",
} as const;

const trialRoleLabels: Record<string, string> = {
  investigational_drug: "试验药物",
  combination_drug: "联用药物",
  investigational_target: "试验靶点",
  combination_target: "联用靶点",
};

type TrialSearchChange = TrialSavedSearchInput & { offset: number };

const emptyTrialSearchInput: TrialSavedSearchInput = {
  query: "",
  registry: "",
  status: "",
  phase: "",
  studyType: "",
  acronym: "",
  initiationType: "",
  therapyLine: "",
  hasResults: "",
  resultEvaluation: "",
  resultsPostedFrom: "",
  resultsPostedTo: "",
  investigationalDrug: "",
  combinationDrug: "",
  investigationalTarget: "",
  combinationTarget: "",
  investigationalDrugEntityIds: [],
  combinationDrugEntityIds: [],
  investigationalTargetEntityIds: [],
  combinationTargetEntityIds: [],
  linkedDrugModalities: [],
  linkedDrugInnovationTypes: [],
  linkedDrugCategories: [],
  linkedDrugProgramTags: [],
  linkedDrugGlobalPhase: "",
  linkedDrugOrganizationCountryRegion: "",
  roleEntityId: "",
  roleEntityIds: [],
  roleEntityRole: "",
  hasKeyResult: "",
  publicationId: "",
  conference: "",
  disclosedFrom: "",
  disclosedTo: "",
  sortBy: "last_update_posted",
  sortDirection: "desc",
  displayMode: "list",
  analysisView: "chart",
};

const disclosureTypeLabels: Record<string, string> = {
  journal_article: "期刊论文",
  conference_abstract: "会议摘要",
  conference_presentation: "会议报告",
  registry_result: "注册结果",
  press_release: "新闻稿",
  poster: "Poster",
  other: "其他披露",
};

function displayList(values: string[], empty = "--", max = 2) {
  if (!values.length) return empty;
  const visible = values.slice(0, max).join("、");
  return values.length > max ? `${visible} 等 ${values.length} 项` : visible;
}

function objectNames(values: Array<Record<string, unknown>>) {
  const names = values
    .map((item) => item.name ?? item.title ?? item.label)
    .filter((value): value is string => typeof value === "string" && Boolean(value.trim()));
  return displayList(names);
}

function primaryOutcomeSummary(trial: ClinicalTrialSearchItemRead) {
  const outcome = trial.outcomes.find((item) => item.outcome_type?.toUpperCase() === "PRIMARY") ?? trial.outcomes[0];
  const result = outcome?.results?.[0];
  if (!outcome || !result) return "未报告";
  return `${outcome.measure}: ${result.value}${result.unit ? ` ${result.unit}` : ""}`;
}

function RoleEntityLinks({
  roles,
  acceptedRoles,
  onOpenEntity,
  compact = false,
  label,
}: {
  roles: ClinicalTrialSearchItemRead["entity_roles"];
  acceptedRoles: string[];
  onOpenEntity: TrialEntityOpener;
  compact?: boolean;
  label?: string;
}) {
  const items = (roles ?? []).filter((item) => acceptedRoles.includes(item.role));
  return (
    <InlineEntityLinks
      label={label ?? acceptedRoles.map((role) => trialRoleLabels[role]).join("与")}
      compact={compact}
      items={items.map((item) => ({
        ...item,
        key: `${item.role}-${item.entity_id}`,
        label: `${trialRoleLabels[item.role]}: ${item.name}`,
      }))}
      onSelect={(item) => onOpenEntity(item.entity_type, item.entity_id)}
    />
  );
}

export function TrialsView({
  displayMode,
  analysisView,
  initialQuery,
  initialRegistry,
  initialStatus,
  initialPhase,
  initialStudyType,
  initialAcronym,
  initialInitiationType,
  initialTherapyLine,
  initialHasResults,
  initialResultEvaluation,
  initialResultsPostedFrom,
  initialResultsPostedTo,
  initialInvestigationalDrug,
  initialCombinationDrug,
  initialInvestigationalTarget,
  initialCombinationTarget,
  initialInvestigationalDrugEntityIds,
  initialCombinationDrugEntityIds,
  initialInvestigationalTargetEntityIds,
  initialCombinationTargetEntityIds,
  initialLinkedDrugModalities,
  initialLinkedDrugInnovationTypes,
  initialLinkedDrugCategories,
  initialLinkedDrugProgramTags,
  initialLinkedDrugGlobalPhase,
  initialLinkedDrugOrganizationCountryRegion,
  initialRoleEntityId,
  initialRoleEntityIds,
  initialRoleEntityRole,
  initialHasKeyResult,
  initialPublicationId,
  initialConference,
  initialDisclosedFrom,
  initialDisclosedTo,
  initialSortBy,
  initialSortDirection,
  initialSort,
  initialOffset,
  selectedTrialId,
  activeSection,
  onSearchChange,
  onTrialChange,
  onSectionChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
  onDisplayModeChange,
  onAnalysisViewChange,
  showListReturn = true,
}: {
  displayMode: "list" | "landscape";
  analysisView: "chart" | "table";
  initialQuery: string;
  initialRegistry: string;
  initialStatus: string;
  initialPhase: string;
  initialStudyType: string;
  initialAcronym: string;
  initialInitiationType: string;
  initialTherapyLine: string;
  initialHasResults: string;
  initialResultEvaluation: string;
  initialResultsPostedFrom: string;
  initialResultsPostedTo: string;
  initialInvestigationalDrug: string;
  initialCombinationDrug: string;
  initialInvestigationalTarget: string;
  initialCombinationTarget: string;
  initialInvestigationalDrugEntityIds: string[];
  initialCombinationDrugEntityIds: string[];
  initialInvestigationalTargetEntityIds: string[];
  initialCombinationTargetEntityIds: string[];
  initialLinkedDrugModalities: string[];
  initialLinkedDrugInnovationTypes: string[];
  initialLinkedDrugCategories: string[];
  initialLinkedDrugProgramTags: string[];
  initialLinkedDrugGlobalPhase: string;
  initialLinkedDrugOrganizationCountryRegion: string;
  initialRoleEntityId: string;
  initialRoleEntityIds: string[];
  initialRoleEntityRole: string;
  initialHasKeyResult: string;
  initialPublicationId: string;
  initialConference: string;
  initialDisclosedFrom: string;
  initialDisclosedTo: string;
  initialSortBy: TrialSortField;
  initialSortDirection: SortDirection;
  initialSort?: SortCriterion<TrialSortField>[];
  initialOffset: number;
  selectedTrialId: string | null;
  activeSection: TrialDossierSection;
  onSearchChange: (change: TrialSearchChange) => void;
  onTrialChange: (trialId: string | null) => void;
  onSectionChange: (section: TrialDossierSection, replace?: boolean) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (entityId: string) => void;
  onOpenTarget?: (entityId: string) => void;
  onOpenDisease?: (entityId: string) => void;
  onOpenOrganization?: (entityId: string) => void;
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  onAnalysisViewChange: (view: "chart" | "table") => void;
  showListReturn?: boolean;
}) {
  const openDrug = onOpenDrug ?? onOpenEntity;
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const openTrialEntity = useCallback<TrialEntityOpener>(
    (entityType, entityId) => {
      switch (entityType) {
        case "drug":
          openDrug(entityId);
          return;
        case "target":
          openTarget(entityId);
          return;
        case "disease":
          openDisease(entityId);
          return;
        case "organization":
          openOrganization(entityId);
          return;
        default:
          onOpenEntity(entityId);
      }
    },
    [onOpenEntity, openDisease, openDrug, openOrganization, openTarget],
  );
  const [query, setQuery] = useState(initialQuery);
  const [registry, setRegistry] = useState(initialRegistry);
  const [status, setStatus] = useState(initialStatus);
  const [phase, setPhase] = useState(initialPhase);
  const [studyType, setStudyType] = useState(initialStudyType);
  const [acronym, setAcronym] = useState(initialAcronym);
  const [initiationType, setInitiationType] = useState(initialInitiationType);
  const [therapyLine, setTherapyLine] = useState(initialTherapyLine);
  const [hasResults, setHasResults] = useState(initialHasResults);
  const [resultEvaluation, setResultEvaluation] = useState(initialResultEvaluation);
  const [resultsPostedFrom, setResultsPostedFrom] = useState(initialResultsPostedFrom);
  const [resultsPostedTo, setResultsPostedTo] = useState(initialResultsPostedTo);
  const [investigationalDrug, setInvestigationalDrug] = useState(initialInvestigationalDrug);
  const [combinationDrug, setCombinationDrug] = useState(initialCombinationDrug);
  const [investigationalTarget, setInvestigationalTarget] = useState(initialInvestigationalTarget);
  const [combinationTarget, setCombinationTarget] = useState(initialCombinationTarget);
  const [investigationalDrugEntityIds, setInvestigationalDrugEntityIds] = useState(initialInvestigationalDrugEntityIds);
  const [combinationDrugEntityIds, setCombinationDrugEntityIds] = useState(initialCombinationDrugEntityIds);
  const [investigationalTargetEntityIds, setInvestigationalTargetEntityIds] = useState(
    initialInvestigationalTargetEntityIds,
  );
  const [combinationTargetEntityIds, setCombinationTargetEntityIds] = useState(initialCombinationTargetEntityIds);
  const [linkedDrugModalities, setLinkedDrugModalities] = useState(initialLinkedDrugModalities);
  const [linkedDrugInnovationTypes, setLinkedDrugInnovationTypes] = useState(initialLinkedDrugInnovationTypes);
  const [linkedDrugCategories, setLinkedDrugCategories] = useState(initialLinkedDrugCategories);
  const [linkedDrugProgramTags, setLinkedDrugProgramTags] = useState(initialLinkedDrugProgramTags);
  const [linkedDrugGlobalPhase, setLinkedDrugGlobalPhase] = useState(initialLinkedDrugGlobalPhase);
  const [linkedDrugOrganizationCountryRegion, setLinkedDrugOrganizationCountryRegion] = useState(
    initialLinkedDrugOrganizationCountryRegion,
  );
  const [linkedProgramFiltersOpen, setLinkedProgramFiltersOpen] = useState(
    Boolean(
      initialLinkedDrugModalities.length ||
        initialLinkedDrugInnovationTypes.length ||
        initialLinkedDrugCategories.length ||
        initialLinkedDrugProgramTags.length ||
        initialLinkedDrugGlobalPhase ||
        initialLinkedDrugOrganizationCountryRegion,
    ),
  );
  const [roleEntityId, setRoleEntityId] = useState(initialRoleEntityId);
  const [roleEntityIds, setRoleEntityIds] = useState(initialRoleEntityIds);
  const [roleEntityRole, setRoleEntityRole] = useState(initialRoleEntityRole);
  const [roleEntityLabels, setRoleEntityLabels] = useState<Record<string, string>>({});
  const [hasKeyResult, setHasKeyResult] = useState(initialHasKeyResult);
  const [publicationId, setPublicationId] = useState(initialPublicationId);
  const [conference, setConference] = useState(initialConference);
  const [disclosedFrom, setDisclosedFrom] = useState(initialDisclosedFrom);
  const [disclosedTo, setDisclosedTo] = useState(initialDisclosedTo);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const appliedSearchInput: TrialSavedSearchInput = {
    query: initialQuery,
    registry: initialRegistry,
    status: initialStatus,
    phase: initialPhase,
    studyType: initialStudyType,
    acronym: initialAcronym,
    initiationType: initialInitiationType,
    therapyLine: initialTherapyLine,
    hasResults: initialHasResults,
    resultEvaluation: initialResultEvaluation,
    resultsPostedFrom: initialResultsPostedFrom,
    resultsPostedTo: initialResultsPostedTo,
    investigationalDrug: initialInvestigationalDrug,
    combinationDrug: initialCombinationDrug,
    investigationalTarget: initialInvestigationalTarget,
    combinationTarget: initialCombinationTarget,
    investigationalDrugEntityIds: initialInvestigationalDrugEntityIds,
    combinationDrugEntityIds: initialCombinationDrugEntityIds,
    investigationalTargetEntityIds: initialInvestigationalTargetEntityIds,
    combinationTargetEntityIds: initialCombinationTargetEntityIds,
    linkedDrugModalities: initialLinkedDrugModalities,
    linkedDrugInnovationTypes: initialLinkedDrugInnovationTypes,
    linkedDrugCategories: initialLinkedDrugCategories,
    linkedDrugProgramTags: initialLinkedDrugProgramTags,
    linkedDrugGlobalPhase: initialLinkedDrugGlobalPhase,
    linkedDrugOrganizationCountryRegion: initialLinkedDrugOrganizationCountryRegion,
    roleEntityId: initialRoleEntityId,
    roleEntityIds: initialRoleEntityIds,
    roleEntityRole: initialRoleEntityRole,
    hasKeyResult: initialHasKeyResult,
    publicationId: initialPublicationId,
    conference: initialConference,
    disclosedFrom: initialDisclosedFrom,
    disclosedTo: initialDisclosedTo,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    sort: initialSort,
    displayMode,
    analysisView,
  };
  const draftSearchInput: TrialSavedSearchInput = {
    query,
    registry,
    status,
    phase,
    studyType,
    acronym,
    initiationType,
    therapyLine,
    hasResults,
    resultEvaluation,
    resultsPostedFrom,
    resultsPostedTo,
    investigationalDrug,
    combinationDrug,
    investigationalTarget,
    combinationTarget,
    investigationalDrugEntityIds,
    combinationDrugEntityIds,
    investigationalTargetEntityIds,
    combinationTargetEntityIds,
    linkedDrugModalities,
    linkedDrugInnovationTypes,
    linkedDrugCategories,
    linkedDrugProgramTags,
    linkedDrugGlobalPhase,
    linkedDrugOrganizationCountryRegion,
    roleEntityId,
    roleEntityIds,
    roleEntityRole,
    hasKeyResult,
    publicationId,
    conference,
    disclosedFrom,
    disclosedTo,
    sortBy: initialSortBy,
    sortDirection: initialSortDirection,
    sort: initialSort,
    displayMode,
    analysisView,
  };
  const resultQueryKey = trialKeys.search(
    initialQuery,
    initialRegistry,
    initialStatus,
    initialPhase,
    initialStudyType,
    initialAcronym,
    initialInitiationType,
    initialTherapyLine,
    initialHasResults,
    initialResultEvaluation,
    initialResultsPostedFrom,
    initialResultsPostedTo,
    initialInvestigationalDrug,
    initialCombinationDrug,
    initialInvestigationalTarget,
    initialCombinationTarget,
    initialInvestigationalDrugEntityIds,
    initialCombinationDrugEntityIds,
    initialInvestigationalTargetEntityIds,
    initialCombinationTargetEntityIds,
    initialLinkedDrugModalities,
    initialLinkedDrugInnovationTypes,
    initialLinkedDrugCategories,
    initialLinkedDrugProgramTags,
    initialLinkedDrugGlobalPhase,
    initialLinkedDrugOrganizationCountryRegion,
    initialRoleEntityId,
    initialRoleEntityIds,
    initialRoleEntityRole,
    initialHasKeyResult,
    initialPublicationId,
    initialConference,
    initialDisclosedFrom,
    initialDisclosedTo,
    initialSortBy,
    initialSortDirection,
    initialOffset,
    initialSort,
  );
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) =>
      searchTrials(
        initialQuery,
        initialRegistry,
        initialStatus,
        initialPhase,
        initialStudyType,
        initialAcronym,
        initialInitiationType,
        initialTherapyLine,
        initialHasResults,
        initialResultEvaluation,
        initialResultsPostedFrom,
        initialResultsPostedTo,
        initialInvestigationalDrug,
        initialCombinationDrug,
        initialInvestigationalTarget,
        initialCombinationTarget,
        initialInvestigationalDrugEntityIds,
        initialCombinationDrugEntityIds,
        initialInvestigationalTargetEntityIds,
        initialCombinationTargetEntityIds,
        initialLinkedDrugModalities,
        initialLinkedDrugInnovationTypes,
        initialLinkedDrugCategories,
        initialLinkedDrugProgramTags,
        initialLinkedDrugGlobalPhase,
        initialLinkedDrugOrganizationCountryRegion,
        initialRoleEntityId,
        initialRoleEntityIds,
        initialRoleEntityRole,
        initialHasKeyResult,
        initialPublicationId,
        initialConference,
        initialDisclosedFrom,
        initialDisclosedTo,
        initialSortBy,
        initialSortDirection,
        initialOffset,
        signal,
        initialSort,
      ),
    enabled: selectedTrialId === null,
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const detail = useQuery({
    queryKey: trialKeys.detail(selectedTrialId ?? ""),
    queryFn: ({ signal }) => loadTrialDetail(selectedTrialId ?? "", signal),
    enabled: selectedTrialId !== null,
  });
  const save = useMutation({ mutationFn: saveClinicalTrialSearch });

  function rememberRoleEntity(entityId: string, displayName?: string) {
    if (!entityId || !displayName) return;
    setRoleEntityLabels((current) =>
      current[entityId] === displayName ? current : { ...current, [entityId]: displayName },
    );
  }

  useEffect(() => {
    setQuery(initialQuery);
    setRegistry(initialRegistry);
    setStatus(initialStatus);
    setPhase(initialPhase);
    setStudyType(initialStudyType);
    setAcronym(initialAcronym);
    setInitiationType(initialInitiationType);
    setTherapyLine(initialTherapyLine);
    setHasResults(initialHasResults);
    setResultEvaluation(initialResultEvaluation);
    setResultsPostedFrom(initialResultsPostedFrom);
    setResultsPostedTo(initialResultsPostedTo);
    setInvestigationalDrug(initialInvestigationalDrug);
    setCombinationDrug(initialCombinationDrug);
    setInvestigationalTarget(initialInvestigationalTarget);
    setCombinationTarget(initialCombinationTarget);
    setInvestigationalDrugEntityIds(initialInvestigationalDrugEntityIds);
    setCombinationDrugEntityIds(initialCombinationDrugEntityIds);
    setInvestigationalTargetEntityIds(initialInvestigationalTargetEntityIds);
    setCombinationTargetEntityIds(initialCombinationTargetEntityIds);
    setLinkedDrugModalities(initialLinkedDrugModalities);
    setLinkedDrugInnovationTypes(initialLinkedDrugInnovationTypes);
    setLinkedDrugCategories(initialLinkedDrugCategories);
    setLinkedDrugProgramTags(initialLinkedDrugProgramTags);
    setLinkedDrugGlobalPhase(initialLinkedDrugGlobalPhase);
    setLinkedDrugOrganizationCountryRegion(initialLinkedDrugOrganizationCountryRegion);
    if (
      initialLinkedDrugModalities.length ||
      initialLinkedDrugInnovationTypes.length ||
      initialLinkedDrugCategories.length ||
      initialLinkedDrugProgramTags.length ||
      initialLinkedDrugGlobalPhase ||
      initialLinkedDrugOrganizationCountryRegion
    ) {
      setLinkedProgramFiltersOpen(true);
    }
    setRoleEntityId(initialRoleEntityId);
    setRoleEntityIds(initialRoleEntityIds);
    setRoleEntityRole(initialRoleEntityRole);
    setHasKeyResult(initialHasKeyResult);
    setPublicationId(initialPublicationId);
    setConference(initialConference);
    setDisclosedFrom(initialDisclosedFrom);
    setDisclosedTo(initialDisclosedTo);
  }, [
    initialHasResults,
    initialAcronym,
    initialInitiationType,
    initialPhase,
    initialQuery,
    initialRegistry,
    initialResultEvaluation,
    initialResultsPostedFrom,
    initialResultsPostedTo,
    initialInvestigationalDrug,
    initialCombinationDrug,
    initialInvestigationalTarget,
    initialCombinationTarget,
    initialInvestigationalDrugEntityIds,
    initialCombinationDrugEntityIds,
    initialInvestigationalTargetEntityIds,
    initialCombinationTargetEntityIds,
    initialLinkedDrugModalities,
    initialLinkedDrugInnovationTypes,
    initialLinkedDrugCategories,
    initialLinkedDrugProgramTags,
    initialLinkedDrugGlobalPhase,
    initialLinkedDrugOrganizationCountryRegion,
    initialRoleEntityId,
    initialRoleEntityIds,
    initialRoleEntityRole,
    initialHasKeyResult,
    initialPublicationId,
    initialConference,
    initialDisclosedFrom,
    initialDisclosedTo,
    initialStatus,
    initialStudyType,
    initialTherapyLine,
  ]);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSearchChange({
      ...draftSearchInput,
      query: query.trim(),
      acronym: acronym.trim(),
      investigationalDrug: investigationalDrug.trim(),
      combinationDrug: combinationDrug.trim(),
      investigationalTarget: investigationalTarget.trim(),
      combinationTarget: combinationTarget.trim(),
      publicationId: publicationId.trim(),
      conference: conference.trim(),
      offset: 0,
    });
  }

  function clearFilters() {
    setQuery("");
    setRegistry("");
    setStatus("");
    setPhase("");
    setStudyType("");
    setAcronym("");
    setInitiationType("");
    setTherapyLine("");
    setHasResults("");
    setResultEvaluation("");
    setResultsPostedFrom("");
    setResultsPostedTo("");
    setInvestigationalDrug("");
    setCombinationDrug("");
    setInvestigationalTarget("");
    setCombinationTarget("");
    setInvestigationalDrugEntityIds([]);
    setCombinationDrugEntityIds([]);
    setInvestigationalTargetEntityIds([]);
    setCombinationTargetEntityIds([]);
    setLinkedDrugModalities([]);
    setLinkedDrugInnovationTypes([]);
    setLinkedDrugCategories([]);
    setLinkedDrugProgramTags([]);
    setLinkedDrugGlobalPhase("");
    setLinkedDrugOrganizationCountryRegion("");
    setLinkedProgramFiltersOpen(false);
    setRoleEntityId("");
    setRoleEntityIds([]);
    setRoleEntityRole("");
    setRoleEntityLabels({});
    setHasKeyResult("");
    setPublicationId("");
    setConference("");
    setDisclosedFrom("");
    setDisclosedTo("");
    onSearchChange({ ...emptyTrialSearchInput, offset: 0 });
  }

  async function submitSavedSearch(event: FormEvent) {
    event.preventDefault();
    setSaveMessage("");
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        input: appliedSearchInput,
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveMessage(outcome.message);
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "临床试验检索保存失败");
    }
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "last_update_posted", direction: "desc" });
    if (!sort.every((criterion) => trialSortFields.includes(criterion.field as TrialSortField))) return;
    const normalizedSort = sort as SortCriterion<TrialSortField>[];
    onSearchChange({
      ...appliedSearchInput,
      sortBy: normalizedSort[0].field,
      sortDirection: normalizedSort[0].direction,
      sort: normalizedSort,
      offset: 0,
    });
  }

  function changePage(offset: number) {
    onSearchChange({ ...appliedSearchInput, offset });
  }

  function applyLandscapeFilter(field: "phase" | "result_evaluation", value: string) {
    onSearchChange({
      ...appliedSearchInput,
      phase: field === "phase" ? value : initialPhase,
      resultEvaluation: field === "result_evaluation" ? value : initialResultEvaluation,
      offset: 0,
    });
  }

  const columns = useMemo<ColumnDef<ClinicalTrialSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "registry_id",
        header: "注册号与试验",
        size: 260,
        cell: ({ row }) => (
          <button className="entity-name-button" type="button" onClick={() => onTrialChange(row.original.id)}>
            <strong>{row.original.registry_id}</strong>
            <small className="cell-subtitle">{row.original.official_title}</small>
          </button>
        ),
      },
      {
        accessorKey: "acronym",
        header: "试验简称",
        size: 130,
        cell: ({ getValue }) => String(getValue() ?? "--"),
      },
      {
        accessorKey: "initiation_type",
        header: "发起类型",
        size: 150,
        cell: ({ getValue }) => initiationTypeLabels[String(getValue() ?? "")] ?? "--",
      },
      {
        accessorKey: "therapy_lines",
        header: "治疗线次",
        size: 150,
        enableSorting: false,
        cell: ({ row }) =>
          displayList(
            row.original.therapy_lines.map((value) => therapyLineLabels[value] ?? value),
            "--",
            3,
          ),
      },
      {
        id: "primary_outcome",
        header: "核心疗效",
        size: 220,
        enableSorting: false,
        cell: ({ row }) => primaryOutcomeSummary(row.original),
      },
      {
        accessorKey: "has_results",
        header: "结果",
        size: 82,
        cell: ({ getValue }) => <StatusBadge value={getValue() ? "已发布" : "未发布"} />,
      },
      {
        accessorKey: "result_evaluation",
        header: "最优评价",
        size: 96,
        cell: ({ getValue }) => {
          const value = getValue() as TrialResultEvaluation | null;
          return value ? <StatusBadge value={resultEvaluationLabels[value]} /> : <span>未评价</span>;
        },
      },
      {
        accessorKey: "phases",
        header: "分期",
        size: 90,
        enableSorting: false,
        cell: ({ row }) => displayList(row.original.phases.map(clinicalTrialPhaseLabel)),
      },
      {
        accessorKey: "overall_status",
        header: "状态",
        size: 110,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "UNKNOWN");
          return <StatusBadge value={value} label={clinicalTrialStatusLabel(value)} />;
        },
      },
      {
        accessorKey: "conditions",
        header: "适应症/疾病",
        size: 150,
        enableSorting: false,
        cell: ({ row }) => displayList(row.original.conditions),
      },
      {
        id: "drug_roles",
        header: "试验/联用药物",
        size: 180,
        enableSorting: false,
        cell: ({ row }) => (
          <RoleEntityLinks
            roles={row.original.entity_roles}
            acceptedRoles={["investigational_drug", "combination_drug"]}
            onOpenEntity={openTrialEntity}
            compact
            label={`${row.original.registry_id} 的药物关联`}
          />
        ),
      },
      {
        id: "target_roles",
        header: "试验/联用靶点",
        size: 180,
        enableSorting: false,
        cell: ({ row }) => (
          <RoleEntityLinks
            roles={row.original.entity_roles}
            acceptedRoles={["investigational_target", "combination_target"]}
            onOpenEntity={openTrialEntity}
            compact
            label={`${row.original.registry_id} 的靶点关联`}
          />
        ),
      },
      {
        accessorKey: "key_result_count",
        header: "关键结果",
        size: 90,
        enableSorting: false,
        cell: ({ getValue }) => {
          const count = Number(getValue() ?? 0);
          return <StatusBadge value={count ? `${count} 项` : "--"} />;
        },
      },
      {
        accessorKey: "latest_result_disclosure",
        header: "最近披露",
        size: 190,
        enableSorting: false,
        cell: ({ getValue }) => {
          const disclosure = getValue() as ClinicalTrialSearchItemRead["latest_result_disclosure"];
          if (!disclosure) return "--";
          return (
            <span className="cell-stack">
              <strong>{disclosureTypeLabels[disclosure.disclosure_type] ?? disclosure.disclosure_type}</strong>
              <small>{formatDate(disclosure.disclosed_at)}</small>
              {disclosure.external_id ? <small>{disclosure.external_id}</small> : null}
            </span>
          );
        },
      },
      {
        accessorKey: "interventions",
        header: "干预措施",
        size: 130,
        enableSorting: false,
        cell: ({ row }) => objectNames(row.original.interventions),
      },
      {
        accessorKey: "sponsors",
        header: "申办方",
        size: 140,
        enableSorting: false,
        cell: ({ row }) => objectNames(row.original.sponsors),
      },
      {
        accessorKey: "enrollment",
        header: "入组",
        size: 80,
        cell: ({ getValue }) => (getValue() == null ? "--" : Number(getValue()).toLocaleString()),
      },
      {
        accessorKey: "study_type",
        header: "研究类型",
        size: 100,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "");
          return clinicalTrialStudyTypeLabel(value);
        },
      },
      {
        accessorKey: "last_update_posted",
        header: "最近更新",
        size: 105,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        id: "linked_entities",
        header: "关联实体",
        size: 165,
        enableSorting: false,
        cell: ({ row }) => (
          <InlineEntityLinks
            label={`${row.original.registry_id} 的关联实体`}
            items={row.original.linked_entities.map((entity) => ({ ...entity, key: entity.id, label: entity.name }))}
            onSelect={(entity) => openTrialEntity(entity.entity_type, entity.id)}
          />
        ),
      },
      {
        id: "open",
        header: "档案",
        size: 55,
        enableSorting: false,
        cell: ({ row }) => (
          <button
            className="icon-button"
            type="button"
            title={`查看 ${row.original.registry_id} 试验详情`}
            aria-label={`查看 ${row.original.registry_id} 试验详情`}
            onClick={() => onTrialChange(row.original.id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [openTrialEntity, onTrialChange],
  );

  const data = result.data;
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    trialRowId,
    trialEntityId,
  );
  const appliedFilterValueLabels = useMemo(
    () => ({
      result_evaluation: resultEvaluationLabels,
      initiation_type: initiationTypeLabels,
      therapy_line: therapyLineLabels,
      role_entity_role: trialRoleLabels,
      role_entity_id: roleEntityLabels,
      role_entity_ids: roleEntityLabels,
      investigational_drug_entity_ids: roleEntityLabels,
      combination_drug_entity_ids: roleEntityLabels,
      investigational_target_entity_ids: roleEntityLabels,
      combination_target_entity_ids: roleEntityLabels,
      linked_drug_global_phase: developmentPhaseLabels,
    }),
    [roleEntityLabels],
  );
  const sorting: SortingState = tableSortingFromCriteria(initialSort, initialSortBy, initialSortDirection);
  const registries = facetOptions(data?.facets, "registry", registry);
  const statuses = facetOptions(data?.facets, "overall_status", status);
  const phases = facetOptions(data?.facets, "phase", phase);
  const studyTypes = facetOptions(data?.facets, "study_type", studyType);
  const linkedDrugModalityOptions = facetOptions(data?.facets, "linked_drug_modality", linkedDrugModalities);
  const linkedDrugInnovationTypeOptions = facetOptions(
    data?.facets,
    "linked_drug_innovation_type",
    linkedDrugInnovationTypes,
  );
  const linkedDrugCategoryOptions = facetOptions(data?.facets, "linked_drug_category", linkedDrugCategories);
  const linkedDrugProgramTagOptions = publicProgramTags(
    facetOptions(data?.facets, "linked_drug_program_tag", linkedDrugProgramTags),
  );
  const linkedDrugGlobalPhases = facetOptions(data?.facets, "linked_drug_global_phase", linkedDrugGlobalPhase);
  const linkedDrugOrganizationCountries = facetOptions(
    data?.facets,
    "linked_drug_organization_country_region",
    linkedDrugOrganizationCountryRegion,
  );
  const hasFilters = Boolean(
    initialQuery ||
      initialRegistry ||
      initialStatus ||
      initialPhase ||
      initialStudyType ||
      initialAcronym ||
      initialInitiationType ||
      initialTherapyLine ||
      initialHasResults ||
      initialResultEvaluation ||
      initialResultsPostedFrom ||
      initialResultsPostedTo ||
      initialInvestigationalDrug ||
      initialCombinationDrug ||
      initialInvestigationalTarget ||
      initialCombinationTarget ||
      initialInvestigationalDrugEntityIds.length > 0 ||
      initialCombinationDrugEntityIds.length > 0 ||
      initialInvestigationalTargetEntityIds.length > 0 ||
      initialCombinationTargetEntityIds.length > 0 ||
      initialLinkedDrugModalities.length > 0 ||
      initialLinkedDrugInnovationTypes.length > 0 ||
      initialLinkedDrugCategories.length > 0 ||
      initialLinkedDrugProgramTags.length > 0 ||
      initialLinkedDrugGlobalPhase ||
      initialLinkedDrugOrganizationCountryRegion ||
      initialRoleEntityId ||
      initialRoleEntityIds.length > 0 ||
      initialRoleEntityRole ||
      initialHasKeyResult ||
      initialPublicationId ||
      initialConference ||
      initialDisclosedFrom ||
      initialDisclosedTo,
  );

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  if (selectedTrialId) {
    return (
      <>
        <TrialProfessionalDossier
          trialId={selectedTrialId}
          data={detail.data}
          loading={detail.isLoading}
          error={detail.error}
          activeSection={activeSection}
          onRetry={() => void detail.refetch()}
          onBack={showListReturn ? () => onTrialChange(null) : undefined}
          onSectionChange={onSectionChange}
          onOpenTrialEntity={openTrialEntity}
          onOpenProvenance={setProvenanceSelection}
        />
        {provenanceSelection ? (
          <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
        ) : null}
      </>
    );
  }

  return (
    <>
      <section className="data-section trial-section">
        <div className="explorer-intro">
          <p>聚合注册平台的试验设计、状态、分期、适应症、干预和申办方，并关联药物与靶点信息。</p>
          <p>注册干预列表不自动区分主药与联合用药；角色条件只匹配有明确角色证据的记录。</p>
        </div>

        <form className="domain-filter-bar trial-filter-bar" onSubmit={submit} aria-label="临床试验筛选">
          <label className="domain-query-field">
            <span>关键词</span>
            <span className="input-with-icon">
              <Search size={16} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="注册号、标题、疾病、干预、申办方或关联实体"
                maxLength={500}
              />
            </span>
          </label>
          <label>
            <span>招募状态</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">全部</option>
              {statuses.map((value) => (
                <option value={value} key={value}>
                  {clinicalTrialStatusLabel(value)} ({data?.facets?.overall_status?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>临床分期</span>
            <select value={phase} onChange={(event) => setPhase(event.target.value)}>
              <option value="">全部</option>
              {phases.map((value) => (
                <option value={value} key={value}>
                  {clinicalTrialPhaseLabel(value)} ({data?.facets?.phase?.[value] ?? 0})
                </option>
              ))}
            </select>
          </label>
          <EntityMultiFilterSelect
            label="试验药物（任一）"
            entityType="drug"
            values={investigationalDrugEntityIds}
            placeholder="输入至少 2 个字符添加试验药物"
            onResolved={rememberRoleEntity}
            onChange={(entityIds, selectedId, displayName) => {
              setInvestigationalDrugEntityIds(entityIds);
              setRoleEntityId("");
              setRoleEntityIds([]);
              setRoleEntityRole("");
              if (selectedId) rememberRoleEntity(selectedId, displayName);
            }}
          />
          <EntityMultiFilterSelect
            label="试验靶点（任一）"
            entityType="target"
            values={investigationalTargetEntityIds}
            placeholder="输入至少 2 个字符添加试验靶点"
            onResolved={rememberRoleEntity}
            onChange={(entityIds, selectedId, displayName) => {
              setInvestigationalTargetEntityIds(entityIds);
              setRoleEntityId("");
              setRoleEntityIds([]);
              setRoleEntityRole("");
              if (selectedId) rememberRoleEntity(selectedId, displayName);
            }}
          />
          <SecondaryFilters
            label="试验设计与注册信息"
            activeCount={[registry, studyType, acronym, initiationType, therapyLine].filter(Boolean).length}
          >
            <label>
              <span>注册平台</span>
              <select value={registry} onChange={(event) => setRegistry(event.target.value)}>
                <option value="">全部</option>
                {registries.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.registry?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>研究类型</span>
              <select value={studyType} onChange={(event) => setStudyType(event.target.value)}>
                <option value="">全部</option>
                {studyTypes.map((value) => (
                  <option value={value} key={value}>
                    {clinicalTrialStudyTypeLabel(value)} ({data?.facets?.study_type?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>试验简称</span>
              <input
                value={acronym}
                onChange={(event) => setAcronym(event.target.value)}
                placeholder="如 KEYNOTE、CheckMate"
                maxLength={240}
              />
            </label>
            <label>
              <span>发起类型</span>
              <select value={initiationType} onChange={(event) => setInitiationType(event.target.value)}>
                <option value="">全部</option>
                {Object.entries(initiationTypeLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label} ({data?.facets?.initiation_type?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>治疗线次</span>
              <select value={therapyLine} onChange={(event) => setTherapyLine(event.target.value)}>
                <option value="">全部</option>
                {Object.entries(therapyLineLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label} ({data?.facets?.therapy_line?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
          </SecondaryFilters>
          <SecondaryFilters
            label="联用药物与靶点"
            activeCount={[combinationDrugEntityIds.length, combinationTargetEntityIds.length].filter(Boolean).length}
          >
            <EntityMultiFilterSelect
              label="联用药物（任一）"
              entityType="drug"
              values={combinationDrugEntityIds}
              placeholder="输入至少 2 个字符添加联用药物"
              onResolved={rememberRoleEntity}
              onChange={(entityIds, selectedId, displayName) => {
                setCombinationDrugEntityIds(entityIds);
                setRoleEntityId("");
                setRoleEntityIds([]);
                setRoleEntityRole("");
                if (selectedId) rememberRoleEntity(selectedId, displayName);
              }}
            />
            <EntityMultiFilterSelect
              label="联用靶点（任一）"
              entityType="target"
              values={combinationTargetEntityIds}
              placeholder="输入至少 2 个字符添加联用靶点"
              onResolved={rememberRoleEntity}
              onChange={(entityIds, selectedId, displayName) => {
                setCombinationTargetEntityIds(entityIds);
                setRoleEntityId("");
                setRoleEntityIds([]);
                setRoleEntityRole("");
                if (selectedId) rememberRoleEntity(selectedId, displayName);
              }}
            />
          </SecondaryFilters>
          <details
            className="advanced-filters trial-linked-program-filters"
            open={linkedProgramFiltersOpen}
            onToggle={(event) => setLinkedProgramFiltersOpen(event.currentTarget.open)}
          >
            <summary>
              关联药物属性
              <span>同一药物项目</span>
            </summary>
            <div className="trial-linked-program-grid">
              <FacetMultiSelect
                label="Modality"
                options={linkedDrugModalityOptions.map((value) => ({
                  value,
                  label: programTagLabel(value),
                  count: data?.facets?.linked_drug_modality?.[value] ?? 0,
                }))}
                selected={linkedDrugModalities}
                onChange={setLinkedDrugModalities}
              />
              <FacetMultiSelect
                label="创新类型"
                options={linkedDrugInnovationTypeOptions.map((value) => ({
                  value,
                  label: value,
                  count: data?.facets?.linked_drug_innovation_type?.[value] ?? 0,
                }))}
                selected={linkedDrugInnovationTypes}
                onChange={setLinkedDrugInnovationTypes}
              />
              <FacetMultiSelect
                label="药品类别"
                options={linkedDrugCategoryOptions.map((value) => ({
                  value,
                  label: value,
                  count: data?.facets?.linked_drug_category?.[value] ?? 0,
                }))}
                selected={linkedDrugCategories}
                onChange={setLinkedDrugCategories}
              />
              <FacetMultiSelect
                label="药品标签"
                options={linkedDrugProgramTagOptions.map((value) => ({
                  value,
                  label: value,
                  count: data?.facets?.linked_drug_program_tag?.[value] ?? 0,
                }))}
                selected={linkedDrugProgramTags}
                onChange={setLinkedDrugProgramTags}
              />
              <label>
                <span>全球最高阶段</span>
                <select
                  value={linkedDrugGlobalPhase}
                  onChange={(event) => setLinkedDrugGlobalPhase(event.target.value)}
                >
                  <option value="">全部</option>
                  {linkedDrugGlobalPhases.map((value) => (
                    <option value={value} key={value}>
                      {developmentPhaseLabels[value] ?? value} ({data?.facets?.linked_drug_global_phase?.[value] ?? 0})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>研发机构国家/地区</span>
                <select
                  value={linkedDrugOrganizationCountryRegion}
                  onChange={(event) => setLinkedDrugOrganizationCountryRegion(event.target.value)}
                >
                  <option value="">全部</option>
                  {linkedDrugOrganizationCountries.map((value) => (
                    <option value={value} key={value}>
                      {value} ({data?.facets?.linked_drug_organization_country_region?.[value] ?? 0})
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </details>
          <SecondaryFilters
            label="试验结果、日期与发表"
            activeCount={
              [
                hasResults,
                resultEvaluation,
                resultsPostedFrom,
                resultsPostedTo,
                hasKeyResult,
                publicationId,
                conference,
                disclosedFrom,
                disclosedTo,
              ].filter(Boolean).length
            }
          >
            <label>
              <span>结果发布</span>
              <select
                aria-label="结果发布"
                value={hasResults}
                onChange={(event) => {
                  const value = event.target.value;
                  setHasResults(value);
                  if (value === "false") setResultEvaluation("");
                }}
              >
                <option value="">全部</option>
                <option value="true">已发布结果 ({data?.facets?.has_results?.true ?? 0})</option>
                <option value="false">尚未发布 ({data?.facets?.has_results?.false ?? 0})</option>
              </select>
            </label>
            <label>
              <span>结果最优评价</span>
              <select
                value={resultEvaluation}
                disabled={hasResults === "false"}
                onChange={(event) => setResultEvaluation(event.target.value)}
              >
                <option value="">全部</option>
                {Object.entries(resultEvaluationLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label} ({data?.facets?.result_evaluation?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>结果发布日期起</span>
              <input
                type="date"
                value={resultsPostedFrom}
                max={resultsPostedTo || undefined}
                onChange={(event) => setResultsPostedFrom(event.target.value)}
              />
            </label>
            <label>
              <span>结果发布日期止</span>
              <input
                type="date"
                value={resultsPostedTo}
                min={resultsPostedFrom || undefined}
                onChange={(event) => setResultsPostedTo(event.target.value)}
              />
            </label>
            <label>
              <span>关键结果</span>
              <select value={hasKeyResult} onChange={(event) => setHasKeyResult(event.target.value)}>
                <option value="">全部</option>
                {Object.entries(keyResultLabels).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label} ({data?.facets?.has_key_result?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>发表编号</span>
              <input
                value={publicationId}
                onChange={(event) => setPublicationId(event.target.value)}
                placeholder="PMID、DOI 或会议摘要编号"
                maxLength={240}
              />
            </label>
            <label>
              <span>会议</span>
              <input value={conference} onChange={(event) => setConference(event.target.value)} maxLength={500} />
            </label>
            <label>
              <span>披露日期起</span>
              <input
                type="date"
                value={disclosedFrom}
                max={disclosedTo || undefined}
                onChange={(event) => setDisclosedFrom(event.target.value)}
              />
            </label>
            <label>
              <span>披露日期止</span>
              <input
                type="date"
                value={disclosedTo}
                min={disclosedFrom || undefined}
                onChange={(event) => setDisclosedTo(event.target.value)}
              />
            </label>
          </SecondaryFilters>
          <div className="domain-filter-actions">
            <button className="primary-button" type="submit" disabled={result.isFetching}>
              <Search size={16} />
              查询
            </button>
            <button className="secondary-button" type="button" onClick={clearFilters} disabled={!hasFilters}>
              清除
            </button>
          </div>
        </form>

        <AppliedFiltersBar
          filters={data?.applied_filters}
          labels={appliedFilterLabels}
          valueLabels={appliedFilterValueLabels}
          onClear={clearFilters}
        />

        <ProfessionalQueryState
          dataAvailable={Boolean(data)}
          isFetching={result.isFetching}
          isCancelled={queryCancellation.isCancelled}
          error={result.error}
          loadingLabel="正在查询临床试验"
          fallbackError="临床试验查询失败"
          onCancel={queryCancellation.cancel}
          onRetry={retryResult}
          onDismissCancellation={queryCancellation.reset}
        >
          {data ? (
            <div className="domain-results">
              <div className="pipeline-result-toolbar">
                <QueryResultSummary
                  total={data.total}
                  offset={data.offset}
                  count={data.items.length}
                  unit="项临床试验"
                  queriedAt={data.as_of}
                />
                <div className="pipeline-result-actions">
                  <QueryRefreshButton refreshing={result.isFetching} onRefresh={retryResult} />
                  <fieldset className="segmented-control">
                    <legend className="sr-only">临床结果展示方式</legend>
                    <button
                      type="button"
                      aria-pressed={displayMode === "list"}
                      onClick={() => onDisplayModeChange("list")}
                    >
                      <List size={15} />
                      列表
                    </button>
                    <button
                      type="button"
                      aria-pressed={displayMode === "landscape"}
                      onClick={() => onDisplayModeChange("landscape")}
                    >
                      <BarChart3 size={15} />
                      可视化
                    </button>
                  </fieldset>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={!hasTrialSearchFilter(appliedSearchInput)}
                    title={
                      hasTrialSearchFilter(appliedSearchInput) ? "保存或订阅当前临床试验查询" : "至少应用一个查询条件"
                    }
                    onClick={() => {
                      setSaveName(initialQuery.trim() || "临床试验情报监控");
                      setSaveMessage("");
                      save.reset();
                      setSaveOpen(true);
                    }}
                  >
                    <BookmarkPlus size={15} />
                    保存/订阅
                  </button>
                  <DomainExportControl dataset="trials" totalRows={data.total} />
                </div>
              </div>
              {data.total && displayMode === "landscape" ? (
                <ClinicalTrialLandscape
                  landscape={data.landscape}
                  onFilter={applyLandscapeFilter}
                  view={analysisView}
                  onViewChange={onAnalysisViewChange}
                />
              ) : data.items.length ? (
                <VirtualDataTable
                  ariaLabel="临床试验结果"
                  columns={columns}
                  data={data.items}
                  getRowId={(trial) => trial.id}
                  preferenceKey="clinical-trials"
                  totalRows={data.total}
                  sorting={sorting}
                  defaultSorting={defaultTrialSorting}
                  onSortingChange={changeSorting}
                  sortingScope="all"
                  toolbarActions={
                    <AddToComparisonControl
                      selectedEntityIds={selectedEntityIds}
                      onAdded={(message) => {
                        setSaveMessage(message);
                        clearSelection();
                      }}
                    />
                  }
                  rowSelection={{
                    selectedRowIds,
                    onChange: onSelectionChange,
                    getRowLabel: (trial) => `对比 ${trial.registry_id}`,
                    label: "选择对比试验",
                    maxSelectedRows: 20,
                  }}
                />
              ) : (
                <EmptyQueryResult
                  domain="临床试验"
                  filtered={Boolean(data.applied_filters?.length)}
                  onClear={clearFilters}
                />
              )}
              {displayMode === "list" ? (
                <ResultPagination
                  totalRows={data.total}
                  offset={data.offset}
                  pageSize={PAGE_SIZE}
                  notice={publicCoverageNotice(data.warnings)}
                  onPageChange={changePage}
                  ariaLabel="临床试验结果分页"
                />
              ) : (
                <footer className="pipeline-landscape-footer">
                  <span>{publicCoverageNotice(data.warnings)}</span>
                </footer>
              )}
            </div>
          ) : null}
        </ProfessionalQueryState>
      </section>
      {saveMessage && !saveOpen ? (
        <p className={save.isError ? "inline-error" : "inline-feedback"} role={save.isError ? "alert" : "status"}>
          {saveMessage}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel="临床试验"
        name={saveName}
        shared={saveShared}
        monitor={saveMonitor}
        pending={save.isPending}
        error={save.isError ? saveMessage : ""}
        onNameChange={setSaveName}
        onSharedChange={setSaveShared}
        onMonitorChange={setSaveMonitor}
        onClose={() => setSaveOpen(false)}
        onSubmit={(event) => void submitSavedSearch(event)}
      />
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}

const trialDetailTabs: Array<ResearchTabOption<TrialDossierSection>> = [
  { key: "overview", label: "概览" },
  { key: "design", label: "设计与入组" },
  { key: "outcomes", label: "终点与结果" },
  { key: "timeline", label: "时间线与中心" },
];

function TrialProfessionalDossier({
  trialId,
  data,
  loading,
  error,
  activeSection,
  onRetry,
  onBack,
  onSectionChange,
  onOpenTrialEntity,
  onOpenProvenance,
}: {
  trialId: string;
  data: ClinicalTrialDetailRead | undefined;
  loading: boolean;
  error: Error | null;
  activeSection: TrialDossierSection;
  onRetry: () => void;
  onBack?: () => void;
  onSectionChange: (section: TrialDossierSection, replace?: boolean) => void;
  onOpenTrialEntity: TrialEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  return (
    <section className="trial-professional-page" aria-labelledby="trial-title">
      {onBack ? (
        <button className="trial-back-button" type="button" onClick={onBack}>
          <ArrowLeft size={16} aria-hidden="true" />
          返回试验列表
        </button>
      ) : null}
      <header className="trial-professional-header">
        <div className="trial-professional-symbol">
          <CalendarDays size={23} />
        </div>
        <div className="trial-professional-identity">
          <span>临床试验专业档案 · {data ? `${data.registry_name} · ${data.registry_id}` : trialId}</span>
          <h2 id="trial-title">{data?.official_title ?? "临床试验专业档案"}</h2>
          <p>{data ? displayList(data.conditions, "适应症未记录", 6) : "正在恢复临床试验深链接"}</p>
        </div>
        {data ? (
          <div>
            <StatusBadge
              value={data.overall_status ?? "UNKNOWN"}
              label={clinicalTrialStatusLabel(data.overall_status)}
            />
          </div>
        ) : null}
      </header>

      {loading ? <Spinner label="正在加载临床试验专业档案" /> : null}
      {error ? <ErrorState message={error.message || "临床试验专业档案加载失败"} retry={onRetry} /> : null}
      {data ? (
        <>
          <dl className="dossier-metrics trial-professional-metrics">
            <div>
              <dt>临床分期</dt>
              <dd>{displayList(data.phases.map(clinicalTrialPhaseLabel), "未记录")}</dd>
            </div>
            <div>
              <dt>试验简称</dt>
              <dd>{data.acronym ?? "--"}</dd>
            </div>
            <div>
              <dt>发起类型</dt>
              <dd>{initiationTypeLabels[data.initiation_type ?? ""] ?? "--"}</dd>
            </div>
            <div>
              <dt>治疗线次</dt>
              <dd>
                {displayList(
                  data.therapy_lines.map((value) => therapyLineLabels[value] ?? value),
                  "--",
                  3,
                )}
              </dd>
            </div>
            <div>
              <dt>招募状态</dt>
              <dd>{clinicalTrialStatusLabel(data.overall_status)}</dd>
            </div>
            <div>
              <dt>计划入组</dt>
              <dd>{data.enrollment?.toLocaleString() ?? "--"}</dd>
            </div>
            <div>
              <dt>结果状态</dt>
              <dd>{data.has_results ? "已发布" : "未发布"}</dd>
            </div>
            <div>
              <dt>关键结果</dt>
              <dd>{data.key_result_count ?? 0}</dd>
            </div>
            <div>
              <dt>最近更新</dt>
              <dd>{formatDate(data.last_update_posted)}</dd>
            </div>
          </dl>
          <ResearchTabList
            tabs={trialDetailTabs}
            activeTab={activeSection}
            onChange={onSectionChange}
            ariaLabel="临床试验专业档案分区"
            idPrefix="trial-dossier"
          />
          <div
            className="trial-professional-body"
            id={`trial-dossier-panel-${activeSection}`}
            role="tabpanel"
            aria-labelledby={`trial-dossier-tab-${activeSection}`}
          >
            {activeSection === "overview" ? <TrialOverview data={data} onOpenEntity={onOpenTrialEntity} /> : null}
            {activeSection === "design" ? <TrialDesign data={data} /> : null}
            {activeSection === "outcomes" ? <TrialOutcomes data={data} /> : null}
            {activeSection === "timeline" ? <TrialTimeline data={data} /> : null}
          </div>
          <footer className="trial-detail-footer">
            <span>数据更新 {formatDate(data.last_update_posted, true)}</span>
            <ProvenanceButton
              selection={{ resourceType: "clinical_trial", resourceId: data.id, label: data.registry_id }}
              onOpen={onOpenProvenance}
            />
          </footer>
        </>
      ) : null}
    </section>
  );
}

function TrialOverview({ data, onOpenEntity }: { data: ClinicalTrialDetailRead; onOpenEntity: TrialEntityOpener }) {
  return (
    <div className="trial-detail-sections">
      <section>
        <h3>关键属性</h3>
        <dl className="trial-detail-grid">
          <DetailValue term="注册号" value={data.registry_id} />
          <DetailValue term="试验简称" value={data.acronym} />
          <DetailValue term="发起类型" value={initiationTypeLabels[data.initiation_type ?? ""] ?? "未记录"} />
          <DetailValue
            term="治疗线次"
            value={displayList(
              data.therapy_lines.map((value) => therapyLineLabels[value] ?? value),
              "未记录",
              6,
            )}
          />
          <DetailValue term="研究类型" value={clinicalTrialStudyTypeLabel(data.study_type)} />
          <DetailValue term="计划入组" value={data.enrollment?.toLocaleString()} />
          <DetailValue term="开始日期" value={formatDate(data.start_date)} />
          <DetailValue term="预计完成" value={formatDate(data.completion_date)} />
          <DetailValue term="首次结果" value={formatDate(data.results_first_posted)} />
          <DetailValue
            term="最优评价"
            value={data.result_evaluation ? resultEvaluationLabels[data.result_evaluation] : "未评价"}
          />
        </dl>
      </section>
      <section>
        <h3>适应症与干预</h3>
        <dl className="trial-detail-grid">
          <DetailValue term="适应症" value={displayList(data.conditions, "未记录", 6)} />
          <DetailValue
            term="干预措施"
            value={displayList(
              data.interventions.map((item) => item.name),
              "未记录",
              6,
            )}
          />
          <DetailValue
            term="申办方"
            value={displayList(
              data.sponsors.map((item) => item.name),
              "未记录",
              6,
            )}
          />
          <DetailValue
            term="国家/地区"
            value={displayList(uniqueValues(data.locations.map((item) => item.country)), "未记录", 8)}
          />
        </dl>
      </section>
      <section>
        <h3>关联药物与靶点</h3>
        {(data.entity_roles ?? []).length ? (
          <div className="trial-role-groups">
            {Object.entries(trialRoleLabels).map(([role, label]) => {
              const roles = (data.entity_roles ?? []).filter((item) => item.role === role);
              if (!roles.length) return null;
              return (
                <div key={role}>
                  <span>{label}</span>
                  <RoleEntityLinks roles={roles} acceptedRoles={[role]} onOpenEntity={onOpenEntity} />
                </div>
              );
            })}
          </div>
        ) : (
          <EmptyState title="暂无角色化药物或靶点关联" />
        )}
      </section>
      <section>
        <h3>关联实体</h3>
        {data.linked_entities.length ? (
          <div className="trial-linked-entities">
            {data.linked_entities.map((entity) => (
              <button
                className="secondary-button"
                type="button"
                key={entity.id}
                onClick={() => onOpenEntity(entity.entity_type, entity.id)}
              >
                {entity.name}
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无关联药物或靶点信息" />
        )}
      </section>
    </div>
  );
}

function TrialDesign({ data }: { data: ClinicalTrialDetailRead }) {
  const design = data.study_design;
  const eligibility = data.eligibility;
  return (
    <div className="trial-detail-sections">
      <section>
        <h3>研究设计</h3>
        <dl className="trial-detail-grid">
          <DetailValue term="分配方式" value={design.allocation} />
          <DetailValue term="干预模型" value={design.intervention_model ?? design.observational_model} />
          <DetailValue term="主要目的" value={design.primary_purpose} />
          <DetailValue term="时间视角" value={design.time_perspective} />
          <DetailValue term="盲法" value={design.masking} />
          <DetailValue term="盲法对象" value={displayList(design.who_masked ?? [], "未记录", 8)} />
        </dl>
        {design.intervention_model_description || design.masking_description ? (
          <p className="trial-detail-note">{design.intervention_model_description ?? design.masking_description}</p>
        ) : null}
      </section>
      <section>
        <h3>队列与治疗组</h3>
        {data.arms.length ? (
          <div className="trial-arm-list">
            {data.arms.map((arm) => (
              <article key={`${arm.label}-${arm.type ?? "arm"}`}>
                <div>
                  <strong>{arm.label}</strong>
                  <StatusBadge value={arm.type ?? "未分类"} />
                </div>
                <p>{arm.description ?? "未记录队列说明"}</p>
                <span>{displayList(arm.intervention_names ?? [], "未关联干预")}</span>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无队列或治疗组记录" />
        )}
      </section>
      <section>
        <h3>入组资格</h3>
        <dl className="trial-detail-grid">
          <DetailValue term="最低年龄" value={eligibility.minimum_age} />
          <DetailValue term="最高年龄" value={eligibility.maximum_age} />
          <DetailValue term="性别" value={eligibility.sex} />
          <DetailValue term="健康志愿者" value={displayBoolean(eligibility.healthy_volunteers)} />
          <DetailValue term="抽样方式" value={eligibility.sampling_method} />
        </dl>
        {eligibility.criteria ? <pre className="trial-eligibility-criteria">{eligibility.criteria}</pre> : null}
      </section>
    </div>
  );
}

function TrialOutcomes({ data }: { data: ClinicalTrialDetailRead }) {
  return (
    <div className="trial-detail-sections">
      <section className="trial-outcome-list">
        <h3>终点与统计结果</h3>
        {data.outcomes.length ? (
          data.outcomes.map((outcome) => (
            <section key={JSON.stringify([outcome.outcome_type, outcome.measure, outcome.time_frame, outcome.results])}>
              <header>
                <StatusBadge value={outcome.outcome_type ?? "终点"} />
                <div>
                  <h3>{outcome.measure}</h3>
                  <span>{outcome.time_frame ?? "时间窗未记录"}</span>
                </div>
              </header>
              {outcome.description ? <p>{outcome.description}</p> : null}
              {outcome.results?.length ? (
                <ScrollableTableRegion ariaLabel={`结构化结果：${outcome.measure}`}>
                  <table>
                    <thead>
                      <tr>
                        <th>队列</th>
                        <th>结果</th>
                        <th>分析人数</th>
                        <th>区间/离散度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {outcome.results.map((result) => (
                        <tr key={`${result.group_label}-${result.value}`}>
                          <td>{result.group_label}</td>
                          <td>
                            <strong>{result.value}</strong> {result.unit ?? ""}
                          </td>
                          <td>{result.participants?.toLocaleString() ?? "--"}</td>
                          <td>{formatResultRange(result.lower_limit, result.upper_limit, result.dispersion)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </ScrollableTableRegion>
              ) : (
                <p className="trial-detail-note">终点已登记，尚未观察到结构化结果。</p>
              )}
              {outcome.statistical_analyses?.length ? (
                <div className="trial-analysis-list">
                  {outcome.statistical_analyses.map((analysis) => (
                    <p
                      key={JSON.stringify([
                        analysis.method,
                        analysis.p_value,
                        analysis.parameter_type,
                        analysis.parameter_value,
                        analysis.lower_limit,
                        analysis.upper_limit,
                      ])}
                    >
                      <strong>{analysis.method ?? analysis.parameter_type ?? "统计分析"}</strong>
                      <span>
                        {analysis.p_value ? `p=${analysis.p_value}` : ""}
                        {analysis.parameter_value != null ? ` ${analysis.parameter_value}` : ""}
                        {analysis.lower_limit != null && analysis.upper_limit != null
                          ? ` · ${analysis.confidence_interval_percent ?? 95}% CI ${analysis.lower_limit}-${analysis.upper_limit}`
                          : ""}
                      </span>
                    </p>
                  ))}
                </div>
              ) : null}
            </section>
          ))
        ) : (
          <EmptyState title="暂无终点记录" detail="当前可用来源未提供结构化终点" />
        )}
      </section>
      <section>
        <h3>结果披露与版本</h3>
        {(data.result_disclosures ?? []).length ? (
          <div className="trial-disclosure-list">
            {(data.result_disclosures ?? []).map((disclosure) => (
              <article key={disclosure.id}>
                <header>
                  <div>
                    <StatusBadge
                      value={disclosureTypeLabels[disclosure.disclosure_type] ?? disclosure.disclosure_type}
                    />
                    {disclosure.is_key_result ? <StatusBadge value="关键结果" /> : null}
                  </div>
                  <span>{formatDate(disclosure.disclosed_at)}</span>
                </header>
                <strong>{disclosure.title}</strong>
                <small>
                  {disclosure.external_id ?? "无外部编号"} · 版本 {disclosure.version}
                  {disclosure.conference_name ? ` · ${disclosure.conference_name}` : ""}
                </small>
                {disclosure.result_evaluation ? (
                  <span>{resultEvaluationLabels[disclosure.result_evaluation]}</span>
                ) : null}
                {disclosure.source_quote ? <p>{disclosure.source_quote}</p> : null}
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无结果披露记录" detail="试验可保留注册结果，披露版本仅在来源明确提供时入库" />
        )}
      </section>
    </div>
  );
}

function TrialTimeline({ data }: { data: ClinicalTrialDetailRead }) {
  return (
    <div className="trial-detail-sections">
      <section>
        <h3>状态时间线</h3>
        {data.status_history.length ? (
          <ol className="trial-status-timeline">
            {[...data.status_history].reverse().map((event) => (
              <li key={`${event.status}-${event.effective_at}`}>
                <CalendarDays size={17} />
                <div>
                  <strong>{clinicalTrialStatusLabel(event.status)}</strong>
                  <span>{formatDate(event.effective_at, true)}</span>
                  {event.reason ? <p>{event.reason}</p> : null}
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState title="暂无历史状态记录" />
        )}
      </section>
      <section>
        <h3>研究中心</h3>
        {data.locations.length ? (
          <div className="trial-location-list">
            {data.locations.map((location) => (
              <div
                key={JSON.stringify([
                  location.facility,
                  location.city,
                  location.state,
                  location.country,
                  location.status,
                ])}
              >
                <MapPin size={17} />
                <div>
                  <strong>{location.facility ?? location.city ?? location.country}</strong>
                  <span>{[location.city, location.state, location.country].filter(Boolean).join(" · ")}</span>
                </div>
                {location.status ? <StatusBadge value={location.status} /> : null}
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无研究中心记录" />
        )}
      </section>
      <section className="trial-source-summary">
        <FileText size={18} />
        <div>
          <strong>{data.source_document_id ? "来源记录已收录" : "来源记录待补充"}</strong>
          <span>最近更新 {formatDate(data.last_update_posted, true)}</span>
        </div>
        <Users size={18} />
        <span>{data.enrollment?.toLocaleString() ?? "--"} 人</span>
      </section>
    </div>
  );
}

function DetailValue({ term, value }: { term: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value === null || value === undefined || value === "" ? "--" : value}</dd>
    </div>
  );
}

function uniqueValues(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

function displayBoolean(value: boolean | null | undefined) {
  return value === true ? "是" : value === false ? "否" : "--";
}

function formatResultRange(
  lower: number | null | undefined,
  upper: number | null | undefined,
  dispersion?: string | null,
) {
  if (lower != null && upper != null) return `${lower}-${upper}`;
  return dispersion ?? "--";
}
