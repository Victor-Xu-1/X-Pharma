import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  BarChart3,
  BookmarkPlus,
  ExternalLink,
  FileText,
  List,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import {
  ErrorState,
  formatDate,
  ProfessionalQueryState,
  QueryRefreshButton,
  Spinner,
  StatusBadge,
} from "../components/common";
import { DealLandscape, type DealLandscapeFilterField } from "../components/DealLandscape";
import { DomainExportControl } from "../components/DomainExportControl";
import { EmptyQueryResult } from "../components/EmptyQueryResult";
import { EntityFilterSelect } from "../components/EntityFilterSelect";
import { FacetMultiSelect } from "../components/FacetMultiSelect";
import { PublicResearchPanel } from "../components/PublicResearchPanel";
import { QueryResultSummary } from "../components/QueryResultSummary";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ResultPagination } from "../components/ResultPagination";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import { type ColumnDef, type SortingState, VirtualDataTable } from "../components/VirtualDataTable";
import {
  type DealAnalysisDimension,
  type DealAnalysisLimit,
  type DealAnalysisView,
  type DealSearchFilters,
  dealKeys,
  emptyDealSearchFilters,
  hasDealSearchFilter,
  loadDealDetail,
  saveDealSearch,
  searchDeals,
  validateDealSearchFilters,
} from "../lib/contracts/deals";
import { intelligenceKeys, searchEntities } from "../lib/contracts/intelligence";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { getSessionEntity, sessionKeys } from "../lib/contracts/session";
import { sortCriteriaFromTable, tableSortingFromCriteria } from "../lib/contracts/sorting";
import {
  dealTypeLabels,
  directionLabels,
  displayTerms,
  formatAmount,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../lib/dealDisplay";
import { facetOptions } from "../lib/facets";
import type { DealSearchItemRead } from "../lib/generated";
import { programTagLabel, publicProgramTags } from "../lib/programDisplay";
import { publicCoverageNotice } from "../lib/publicWarnings";
import { useFilterDraft } from "../lib/useFilterDraft";
import { usePagedEntitySelection } from "../lib/usePagedEntitySelection";
import { useQueryCancellation } from "../lib/useQueryCancellation";
import type { DealDossierSection } from "../lib/workspaceRouting";
import type { DossierEntityOpener } from "./EntityDossierView";

const PAGE_SIZE = 100;
const dealRowId = (deal: DealSearchItemRead) => deal.id;
const dealEntityId = (deal: DealSearchItemRead) => deal.entity_id;
const dealDossierTabs: ReadonlyArray<ResearchTabOption<DealDossierSection>> = [
  { key: "overview", label: "交易概览" },
  { key: "parties", label: "参与方" },
  { key: "assets", label: "资产与阶段" },
  { key: "rights", label: "地域权益" },
  { key: "terms", label: "条款与来源" },
];
const dealSortFields: DealSearchFilters["sortBy"][] = [
  "announced_at",
  "name",
  "deal_type",
  "status",
  "direction",
  "territory",
  "upfront_amount",
  "total_potential_amount",
];
const amountSortFields = new Set<DealSearchFilters["sortBy"]>(["upfront_amount", "total_potential_amount"]);
const appliedFilterLabels = {
  q: "关键词",
  deal_type: "交易类型",
  status: "交易状态",
  direction: "交易方向",
  direction_reference_jurisdiction: "方向参照地区",
  territory: "交易地域",
  asset_entity_id: "交易药品",
  target_entity_id: "关联靶点",
  disease_entity_id: "关联适应症",
  asset_modality: "资产模态",
  asset_program_tag: "资产项目标签",
  party: "参与方",
  party_entity_id: "参与机构",
  party_role: "参与角色",
  party_country_region: "机构所在地区",
  party_organization_type: "机构类型",
  development_phase_at_transaction: "交易时阶段",
  current_development_phase: "当前最高阶段",
  right_type: "权益类型",
  rights_territory: "权益地区",
  currency: "币种",
  announced_from: "初始披露起",
  announced_to: "初始披露止",
  terminated_from: "终止日期起",
  terminated_to: "终止日期止",
  source_updated_from: "信息更新起",
  source_updated_to: "信息更新止",
  upfront_amount_min: "首付款下限",
  upfront_amount_max: "首付款上限",
  total_potential_amount_min: "潜在总额下限",
  total_potential_amount_max: "潜在总额上限",
} as const;

const statusOptions = Object.keys(statusLabels);
const directionOptions = Object.keys(directionLabels);
const partyRoleOptions = Object.keys(partyRoleLabels);
const rightTypeOptions = Object.keys(rightTypeLabels);
const phaseOptions = Object.keys(phaseLabels);

function useDebouncedValue(value: string, delay: number) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [delay, value]);
  return debounced;
}

export function DealsView({
  displayMode,
  analysisDimension,
  analysisView,
  analysisLimit,
  initialFilters,
  initialOffset,
  selectedDealId,
  activeSection,
  onSearchChange,
  onDisplayModeChange,
  onAnalysisChange,
  onDealChange,
  onSectionChange,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
}: {
  displayMode: "list" | "landscape";
  analysisDimension: DealAnalysisDimension;
  analysisView: DealAnalysisView;
  analysisLimit: DealAnalysisLimit;
  initialFilters: DealSearchFilters;
  initialOffset: number;
  selectedDealId: string | null;
  activeSection: DealDossierSection;
  onSearchChange: (filters: DealSearchFilters, offset: number) => void;
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  onAnalysisChange: (next: {
    dimension: DealAnalysisDimension;
    view: DealAnalysisView;
    limit: DealAnalysisLimit;
  }) => void;
  onDealChange: (dealId: string | null) => void;
  onSectionChange: (section: DealDossierSection, replace?: boolean) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
}) {
  const [filters, setFilters] = useFilterDraft(initialFilters);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saveShared, setSaveShared] = useState(false);
  const [saveMonitor, setSaveMonitor] = useState(true);
  const [saveMessage, setSaveMessage] = useState("");
  const debouncedParty = useDebouncedValue(filters.party.trim(), 250);
  const resultQueryKey = dealKeys.search(initialFilters, initialOffset, analysisLimit);
  const result = useQuery({
    queryKey: resultQueryKey,
    queryFn: ({ signal }) => searchDeals(initialFilters, initialOffset, analysisLimit, signal),
    enabled: selectedDealId === null,
  });
  const queryCancellation = useQueryCancellation(resultQueryKey);
  const detail = useQuery({
    queryKey: dealKeys.detail(selectedDealId ?? ""),
    queryFn: ({ signal }) => loadDealDetail(selectedDealId ?? "", signal),
    enabled: Boolean(selectedDealId),
  });
  const selectedParty = useQuery({
    queryKey: sessionKeys.entity(initialFilters.partyEntityId),
    queryFn: ({ signal }) => getSessionEntity(initialFilters.partyEntityId, signal),
    enabled: selectedDealId === null && Boolean(initialFilters.partyEntityId && !initialFilters.party),
  });
  const partySuggestions = useQuery({
    queryKey: intelligenceKeys.search(debouncedParty, ["organization"], ""),
    queryFn: ({ signal }) => searchEntities(debouncedParty, ["organization"], "", signal),
    enabled: selectedDealId === null && debouncedParty.length >= 2 && !filters.partyEntityId,
  });
  const save = useMutation({ mutationFn: saveDealSearch });
  const openDealEntity = useCallback<DossierEntityOpener>(
    (entityType, entityId) => {
      switch (entityType) {
        case "drug":
          (onOpenDrug ?? onOpenEntity)(entityId);
          return;
        case "target":
          (onOpenTarget ?? onOpenEntity)(entityId);
          return;
        case "disease":
          (onOpenDisease ?? onOpenEntity)(entityId);
          return;
        case "organization":
          (onOpenOrganization ?? onOpenEntity)(entityId);
          return;
        default:
          onOpenEntity(entityId);
      }
    },
    [onOpenDisease, onOpenDrug, onOpenEntity, onOpenOrganization, onOpenTarget],
  );

  useEffect(() => {
    if (filters === initialFilters) setValidationError(null);
  }, [filters, initialFilters]);

  useEffect(() => {
    if (!initialFilters.party && initialFilters.partyEntityId && selectedParty.data?.name) {
      setFilters((current) => ({ ...current, party: selectedParty.data?.name ?? "" }));
    }
  }, [initialFilters.party, initialFilters.partyEntityId, selectedParty.data?.name, setFilters]);

  function updateFilter<K extends keyof DealSearchFilters>(key: K, value: DealSearchFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setValidationError(null);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const error = validateDealSearchFilters(filters);
    if (error) {
      setValidationError(error);
      return;
    }
    const sortBy = amountSortFields.has(filters.sortBy) && !filters.currency ? "announced_at" : filters.sortBy;
    onSearchChange({ ...filters, query: filters.query.trim(), party: filters.party.trim(), sortBy }, 0);
  }

  function clearFilters() {
    setFilters(emptyDealSearchFilters);
    setValidationError(null);
    onSearchChange(emptyDealSearchFilters, 0);
  }

  function applyLandscapeFilter(field: DealLandscapeFilterField, value: string) {
    if (value === "__missing__") return;
    if (field === "assetModality") {
      onSearchChange({ ...initialFilters, assetModalities: [value] }, 0);
      return;
    }
    onSearchChange({ ...initialFilters, [field]: value }, 0);
  }

  function chooseParty(entityId: string, name: string) {
    setFilters((current) => ({ ...current, party: name, partyEntityId: entityId }));
    setValidationError(null);
  }

  function changeSorting(nextSorting: SortingState) {
    const sort = sortCriteriaFromTable(nextSorting, { field: "announced_at", direction: "desc" });
    if (!sort.every((criterion) => dealSortFields.includes(criterion.field as DealSearchFilters["sortBy"]))) return;
    const normalizedSort = sort as NonNullable<DealSearchFilters["sort"]>;
    if (normalizedSort.some((criterion) => amountSortFields.has(criterion.field)) && !initialFilters.currency) return;
    onSearchChange(
      {
        ...initialFilters,
        sortBy: normalizedSort[0].field,
        sortDirection: normalizedSort[0].direction,
        sort: normalizedSort,
      },
      0,
    );
  }

  async function submitSavedSearch(event: FormEvent) {
    event.preventDefault();
    setSaveMessage("");
    try {
      const outcome = await save.mutateAsync({
        name: saveName,
        filters: initialFilters,
        displayMode,
        analysis: { dimension: analysisDimension, view: analysisView, limit: analysisLimit },
        shared: saveShared,
        monitor: saveMonitor,
      });
      setSaveOpen(false);
      setSaveMessage(outcome.message);
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "交易检索保存失败");
    }
  }

  const columns = useMemo<ColumnDef<DealSearchItemRead, unknown>[]>(
    () => [
      {
        accessorKey: "name",
        header: "交易名称",
        size: 250,
        cell: ({ row }) => (
          <button className="entity-name-button" type="button" onClick={() => onDealChange(row.original.id)}>
            <strong>{row.original.name}</strong>
            <small className="cell-subtitle">{displayTerms(row.original.terms)}</small>
          </button>
        ),
      },
      {
        accessorKey: "status",
        header: "状态",
        size: 88,
        cell: ({ getValue }) => <StatusBadge value={statusLabels[String(getValue())] ?? String(getValue())} />,
      },
      {
        accessorKey: "deal_type",
        header: "类型",
        size: 92,
        cell: ({ getValue }) => {
          const value = String(getValue() ?? "--");
          return <StatusBadge value={dealTypeLabels[value] ?? value} />;
        },
      },
      {
        accessorKey: "announced_at",
        header: "初始披露",
        size: 104,
        cell: ({ getValue }) => formatDate(String(getValue() ?? "")),
      },
      {
        accessorKey: "direction",
        header: "方向",
        size: 96,
        cell: ({ getValue }) => directionLabels[String(getValue())] ?? String(getValue()),
      },
      {
        id: "parties",
        header: "参与方与角色",
        size: 220,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="deal-role-list">
            {row.original.party_roles.length
              ? row.original.party_roles.map((association) => (
                  <button
                    type="button"
                    key={`${association.id}-${association.role}`}
                    onClick={() => openDealEntity(association.entity_type, association.id)}
                  >
                    {association.name}
                    <small>{partyRoleLabels[association.role] ?? association.role}</small>
                  </button>
                ))
              : row.original.party_entities.map((entity) => (
                  <button type="button" key={entity.id} onClick={() => openDealEntity(entity.entity_type, entity.id)}>
                    {entity.name}
                    <small>角色未披露</small>
                  </button>
                ))}
          </span>
        ),
      },
      {
        id: "assets",
        header: "资产与交易时阶段",
        size: 185,
        enableSorting: false,
        cell: ({ row }) => (
          <span className="deal-role-list">
            {row.original.asset_stages.length
              ? row.original.asset_stages.map((asset) => (
                  <button type="button" key={asset.id} onClick={() => openDealEntity(asset.entity_type, asset.id)}>
                    {asset.name}
                    <small>
                      {asset.development_phase_at_transaction
                        ? (phaseLabels[asset.development_phase_at_transaction] ??
                          asset.development_phase_at_transaction)
                        : "交易时阶段未披露"}
                      {asset.current_development_phase
                        ? ` → 当前 ${phaseLabels[asset.current_development_phase] ?? asset.current_development_phase}`
                        : ""}
                    </small>
                  </button>
                ))
              : row.original.asset_entities.map((entity) => (
                  <button type="button" key={entity.id} onClick={() => openDealEntity(entity.entity_type, entity.id)}>
                    {entity.name}
                    <small>交易阶段未披露</small>
                  </button>
                ))}
          </span>
        ),
      },
      {
        id: "rights",
        header: "权益",
        size: 175,
        enableSorting: false,
        cell: ({ row }) =>
          row.original.rights.length
            ? row.original.rights
                .slice(0, 2)
                .map((right) => `${rightTypeLabels[right.right_type] ?? right.right_type} · ${right.territory}`)
                .join(" / ")
            : "未披露",
      },
      { accessorKey: "territory", header: "交易地域", size: 105, cell: ({ getValue }) => String(getValue() ?? "--") },
      {
        accessorKey: "upfront_amount",
        header: "首付款",
        size: 110,
        enableSorting: Boolean(initialFilters.currency),
        cell: ({ row }) => formatAmount(row.original.upfront_amount, row.original.currency),
      },
      {
        accessorKey: "total_potential_amount",
        header: "潜在总额",
        size: 115,
        enableSorting: Boolean(initialFilters.currency),
        cell: ({ row }) => formatAmount(row.original.total_potential_amount, row.original.currency),
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
            title={`打开 ${row.original.name} 实体档案`}
            aria-label={`打开 ${row.original.name} 实体档案`}
            onClick={() => onDealChange(row.original.id)}
          >
            <ExternalLink size={16} />
          </button>
        ),
      },
    ],
    [initialFilters.currency, onDealChange, openDealEntity],
  );

  const data = result.data;
  const { selectedRowIds, selectedEntityIds, onSelectionChange, clearSelection } = usePagedEntitySelection(
    data?.items ?? [],
    dealRowId,
    dealEntityId,
  );
  const sorting: SortingState = tableSortingFromCriteria(
    initialFilters.sort,
    initialFilters.sortBy,
    initialFilters.sortDirection,
  );
  const dealTypes = facetOptions(data?.facets, "deal_type", filters.dealType);
  const territories = facetOptions(data?.facets, "territory", filters.territory);
  const partyCountries = facetOptions(data?.facets, "party_country_region", filters.partyCountryRegion);
  const partyOrganizationTypes = facetOptions(data?.facets, "party_organization_type", filters.partyOrganizationType);
  const assetModalities = facetOptions(data?.facets, "asset_modality", filters.assetModalities);
  const assetProgramTags = publicProgramTags(facetOptions(data?.facets, "asset_program_tag", filters.assetProgramTags));
  const rightsTerritories = facetOptions(data?.facets, "rights_territory", filters.rightsTerritory);
  const currencies = facetOptions(data?.facets, "currency", filters.currency);
  const hasFilters = hasDealSearchFilter(initialFilters);

  function retryResult() {
    queryCancellation.reset();
    void result.refetch();
  }

  if (selectedDealId) {
    return (
      <>
        <DealProfessionalDossier
          data={detail.data}
          loading={detail.isFetching}
          error={detail.error instanceof Error ? detail.error : null}
          activeSection={activeSection}
          onSectionChange={onSectionChange}
          onRetry={() => void detail.refetch()}
          onClose={() => onDealChange(null)}
          onOpenEntity={openDealEntity}
          onOpenProvenance={setProvenanceSelection}
        />
        {provenanceSelection ? (
          <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
        ) : null}
      </>
    );
  }

  return (
    <section className="data-section deal-section">
      <div className="explorer-intro">
        <p>检索许可、合作、并购和商业化交易，统一核对参与方角色、交易时阶段、权益、金额与来源时点。</p>
      </div>

      <PublicResearchPanel defaultQuery={initialFilters.query} defaultTopic="disclosures" />

      <form className="domain-filter-bar deal-filter-bar" onSubmit={submit} aria-label="交易筛选">
        <label className="domain-query-field">
          <span>关键词</span>
          <span className="input-with-icon">
            <Search size={16} />
            <input
              value={filters.query}
              onChange={(event) => updateFilter("query", event.target.value)}
              placeholder="交易名称、公司、资产或条款"
              maxLength={500}
            />
          </span>
        </label>
        <label>
          <span>交易类型</span>
          <select value={filters.dealType} onChange={(event) => updateFilter("dealType", event.target.value)}>
            <option value="">全部</option>
            {dealTypes.map((value) => (
              <option value={value} key={value}>
                {dealTypeLabels[value] ?? value} ({data?.facets?.deal_type?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>交易状态</span>
          <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
            <option value="">全部</option>
            {statusOptions.map((value) => (
              <option value={value} key={value}>
                {statusLabels[value]} ({data?.facets?.status?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>交易方向</span>
          <select
            aria-label="交易方向"
            value={filters.direction}
            onChange={(event) => updateFilter("direction", event.target.value)}
          >
            <option value="">全部</option>
            {directionOptions.map((value) => (
              <option value={value} key={value}>
                {directionLabels[value]} ({data?.facets?.direction?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>
        <EntityFilterSelect
          label="交易药品"
          entityType="drug"
          value={filters.assetEntityId}
          onChange={(entityId) => updateFilter("assetEntityId", entityId)}
          placeholder="输入药品名称或别名"
        />
        <EntityFilterSelect
          label="关联靶点"
          entityType="target"
          value={filters.targetEntityId}
          onChange={(entityId) => updateFilter("targetEntityId", entityId)}
          placeholder="输入靶点名称或别名"
        />
        <EntityFilterSelect
          label="关联适应症"
          entityType="disease"
          value={filters.diseaseEntityId}
          onChange={(entityId) => updateFilter("diseaseEntityId", entityId)}
          placeholder="输入适应症名称或别名"
        />
        <label className="deal-party-field">
          <span>参与机构</span>
          <input
            role="combobox"
            aria-autocomplete="list"
            aria-expanded={Boolean(partySuggestions.data?.items.length && !filters.partyEntityId)}
            aria-controls="deal-party-suggestions"
            value={filters.party}
            onChange={(event) =>
              setFilters((current) => ({ ...current, party: event.target.value, partyEntityId: "" }))
            }
            placeholder="至少输入 2 个字符"
            maxLength={500}
          />
          {!filters.partyEntityId && debouncedParty.length >= 2 ? (
            <div className="query-suggestions deal-party-suggestions" id="deal-party-suggestions" role="listbox">
              {partySuggestions.isFetching ? <span className="suggestion-status">正在查找机构</span> : null}
              {partySuggestions.data?.items.slice(0, 8).map((entity) => (
                <button type="button" role="option" key={entity.id} onClick={() => chooseParty(entity.id, entity.name)}>
                  <span>{entity.name}</span>
                  <small>
                    {entity.external_ids ? Object.values(entity.external_ids).slice(0, 2).join(" · ") : "机构"}
                  </small>
                </button>
              ))}
              {!partySuggestions.isFetching && partySuggestions.data?.items.length === 0 ? (
                <span className="suggestion-status">未找到匹配机构</span>
              ) : null}
            </div>
          ) : null}
        </label>
        <label>
          <span>参与角色</span>
          <select
            aria-label="参与角色"
            value={filters.partyRole}
            onChange={(event) => updateFilter("partyRole", event.target.value)}
          >
            <option value="">全部</option>
            {partyRoleOptions.map((value) => (
              <option value={value} key={value}>
                {partyRoleLabels[value]} ({data?.facets?.party_role?.[value] ?? 0})
              </option>
            ))}
          </select>
        </label>

        <details className="advanced-filter-panel">
          <summary>
            <SlidersHorizontal size={16} />
            更多交易条件
          </summary>
          <div className="advanced-filter-grid">
            <label>
              <span>方向参照地区</span>
              <input
                value={filters.directionReferenceJurisdiction}
                onChange={(event) => updateFilter("directionReferenceJurisdiction", event.target.value)}
                placeholder="例如 US"
                maxLength={120}
              />
            </label>
            <label>
              <span>交易地域</span>
              <select value={filters.territory} onChange={(event) => updateFilter("territory", event.target.value)}>
                <option value="">全部</option>
                {territories.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.territory?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>机构所在地区</span>
              <input
                list="deal-party-country-options"
                value={filters.partyCountryRegion}
                onChange={(event) => updateFilter("partyCountryRegion", event.target.value)}
                maxLength={120}
              />
              <datalist id="deal-party-country-options">
                {partyCountries.map((value) => (
                  <option value={value} key={value} label={String(data?.facets?.party_country_region?.[value] ?? 0)} />
                ))}
              </datalist>
            </label>
            <label>
              <span>机构类型</span>
              <input
                list="deal-party-organization-type-options"
                value={filters.partyOrganizationType}
                onChange={(event) => updateFilter("partyOrganizationType", event.target.value)}
                maxLength={120}
              />
              <datalist id="deal-party-organization-type-options">
                {partyOrganizationTypes.map((value) => (
                  <option
                    value={value}
                    key={value}
                    label={String(data?.facets?.party_organization_type?.[value] ?? 0)}
                  />
                ))}
              </datalist>
            </label>
            <FacetMultiSelect
              label="资产模态"
              options={assetModalities.map((value) => ({
                value,
                label: programTagLabel(value),
                count: data?.facets?.asset_modality?.[value] ?? 0,
              }))}
              selected={filters.assetModalities}
              onChange={(values) => updateFilter("assetModalities", values)}
            />
            <FacetMultiSelect
              label="资产项目标签"
              options={assetProgramTags.map((value) => ({
                value,
                label: value,
                count: data?.facets?.asset_program_tag?.[value] ?? 0,
              }))}
              selected={filters.assetProgramTags}
              onChange={(values) => updateFilter("assetProgramTags", values)}
            />
            <label>
              <span>交易时阶段</span>
              <select
                value={filters.developmentPhaseAtTransaction}
                onChange={(event) => updateFilter("developmentPhaseAtTransaction", event.target.value)}
              >
                <option value="">全部</option>
                {phaseOptions.map((value) => (
                  <option value={value} key={value}>
                    {phaseLabels[value]} ({data?.facets?.development_phase_at_transaction?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>当前最高阶段</span>
              <select
                value={filters.currentDevelopmentPhase}
                onChange={(event) => updateFilter("currentDevelopmentPhase", event.target.value)}
              >
                <option value="">全部</option>
                {phaseOptions.map((value) => (
                  <option value={value} key={value}>
                    {phaseLabels[value]} ({data?.facets?.current_development_phase?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>权益类型</span>
              <select value={filters.rightType} onChange={(event) => updateFilter("rightType", event.target.value)}>
                <option value="">全部</option>
                {rightTypeOptions.map((value) => (
                  <option value={value} key={value}>
                    {rightTypeLabels[value]} ({data?.facets?.right_type?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>权益地区</span>
              <select
                value={filters.rightsTerritory}
                onChange={(event) => updateFilter("rightsTerritory", event.target.value)}
              >
                <option value="">全部</option>
                {rightsTerritories.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.rights_territory?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>币种</span>
              <select
                aria-label="币种"
                value={filters.currency}
                onChange={(event) => updateFilter("currency", event.target.value)}
              >
                <option value="">全部</option>
                {currencies.map((value) => (
                  <option value={value} key={value}>
                    {value} ({data?.facets?.currency?.[value] ?? 0})
                  </option>
                ))}
              </select>
            </label>
            <DateRangeFields
              label="初始披露"
              from={filters.announcedFrom}
              to={filters.announcedTo}
              onFrom={(value) => updateFilter("announcedFrom", value)}
              onTo={(value) => updateFilter("announcedTo", value)}
            />
            <DateRangeFields
              label="终止日期"
              from={filters.terminatedFrom}
              to={filters.terminatedTo}
              onFrom={(value) => updateFilter("terminatedFrom", value)}
              onTo={(value) => updateFilter("terminatedTo", value)}
            />
            <DateRangeFields
              label="信息更新"
              from={filters.sourceUpdatedFrom}
              to={filters.sourceUpdatedTo}
              onFrom={(value) => updateFilter("sourceUpdatedFrom", value)}
              onTo={(value) => updateFilter("sourceUpdatedTo", value)}
            />
            <AmountRangeFields
              label="首付款"
              minimum={filters.upfrontAmountMin}
              maximum={filters.upfrontAmountMax}
              onMinimum={(value) => updateFilter("upfrontAmountMin", value)}
              onMaximum={(value) => updateFilter("upfrontAmountMax", value)}
            />
            <AmountRangeFields
              label="潜在总额"
              minimum={filters.totalPotentialAmountMin}
              maximum={filters.totalPotentialAmountMax}
              onMinimum={(value) => updateFilter("totalPotentialAmountMin", value)}
              onMaximum={(value) => updateFilter("totalPotentialAmountMax", value)}
            />
          </div>
        </details>

        {validationError ? (
          <p className="form-error deal-filter-error" role="alert">
            {validationError}
          </p>
        ) : null}
        <div className="domain-filter-actions deal-filter-actions">
          <button className="primary-button" type="submit" disabled={result.isFetching}>
            <Search size={16} />
            查询
          </button>
          <button className="secondary-button" type="button" onClick={clearFilters} disabled={!hasFilters}>
            清除
          </button>
        </div>
      </form>

      <AppliedFiltersBar filters={data?.applied_filters} labels={appliedFilterLabels} onClear={clearFilters} />

      <ProfessionalQueryState
        dataAvailable={Boolean(data)}
        isFetching={result.isFetching}
        isCancelled={queryCancellation.isCancelled}
        error={result.error}
        loadingLabel="正在查询交易"
        fallbackError="交易查询失败"
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
                unit="项交易"
                queriedAt={data.as_of}
                showRange={displayMode === "list"}
              />
              <div className="pipeline-result-actions">
                <QueryRefreshButton refreshing={result.isFetching} onRefresh={retryResult} />
                <fieldset className="segmented-control">
                  <legend className="sr-only">交易结果展示方式</legend>
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
                    统计
                  </button>
                </fieldset>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={!hasDealSearchFilter(initialFilters)}
                  title={hasDealSearchFilter(initialFilters) ? "保存或订阅当前交易查询" : "至少应用一个查询条件"}
                  onClick={() => {
                    setSaveName(initialFilters.query.trim() || "交易情报监控");
                    setSaveMessage("");
                    save.reset();
                    setSaveOpen(true);
                  }}
                >
                  <BookmarkPlus size={15} />
                  保存/订阅
                </button>
                <DomainExportControl dataset="deals" totalRows={data.total} />
              </div>
            </div>
            {data.total && displayMode === "landscape" ? (
              <DealLandscape
                landscape={data.landscape}
                dimension={analysisDimension}
                view={analysisView}
                limit={analysisLimit}
                onFilter={applyLandscapeFilter}
                onAnalysisChange={onAnalysisChange}
              />
            ) : data.items.length ? (
              <VirtualDataTable
                ariaLabel="交易结果"
                columns={columns}
                data={data.items}
                getRowId={(deal) => deal.id}
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
                  getRowLabel: (deal) => `对比 ${deal.name}`,
                  label: "选择对比交易",
                  maxSelectedRows: 20,
                }}
                preferenceKey="deals"
                totalRows={data.total}
                sorting={sorting}
                onSortingChange={changeSorting}
                sortingScope="all"
                defaultSorting={[{ id: "announced_at", desc: true }]}
              />
            ) : (
              <EmptyQueryResult domain="交易" filtered={Boolean(data.applied_filters?.length)} onClear={clearFilters} />
            )}
            {displayMode === "list" ? (
              <ResultPagination
                totalRows={data.total}
                offset={data.offset}
                pageSize={PAGE_SIZE}
                notice={publicCoverageNotice(data.warnings)}
                onPageChange={(offset) => onSearchChange(initialFilters, offset)}
                ariaLabel="交易结果分页"
              />
            ) : null}
          </div>
        ) : null}
      </ProfessionalQueryState>
      {saveMessage && !saveOpen ? (
        <p className={save.isError ? "inline-error" : "inline-feedback"} role={save.isError ? "alert" : "status"}>
          {saveMessage}
        </p>
      ) : null}
      <SavedSearchDialog
        open={saveOpen}
        domainLabel="交易"
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
    </section>
  );
}

function DateRangeFields({
  label,
  from,
  to,
  onFrom,
  onTo,
}: {
  label: string;
  from: string;
  to: string;
  onFrom: (value: string) => void;
  onTo: (value: string) => void;
}) {
  return (
    <fieldset className="compact-range-fields">
      <legend>{label}</legend>
      <label>
        <span>起</span>
        <input type="date" value={from} onChange={(event) => onFrom(event.target.value)} />
      </label>
      <label>
        <span>止</span>
        <input type="date" value={to} onChange={(event) => onTo(event.target.value)} />
      </label>
    </fieldset>
  );
}

function AmountRangeFields({
  label,
  minimum,
  maximum,
  onMinimum,
  onMaximum,
}: {
  label: string;
  minimum: string;
  maximum: string;
  onMinimum: (value: string) => void;
  onMaximum: (value: string) => void;
}) {
  return (
    <fieldset className="compact-range-fields">
      <legend>{label}</legend>
      <label>
        <span>下限</span>
        <input type="number" min="0" step="1" value={minimum} onChange={(event) => onMinimum(event.target.value)} />
      </label>
      <label>
        <span>上限</span>
        <input type="number" min="0" step="1" value={maximum} onChange={(event) => onMaximum(event.target.value)} />
      </label>
    </fieldset>
  );
}

function DealProfessionalDossier({
  data,
  loading,
  error,
  activeSection,
  onSectionChange,
  onRetry,
  onClose,
  onOpenEntity,
  onOpenProvenance,
}: {
  data: DealSearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  activeSection: DealDossierSection;
  onSectionChange: (section: DealDossierSection, replace?: boolean) => void;
  onRetry: () => void;
  onClose: () => void;
  onOpenEntity: DossierEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  return (
    <section className="data-section deal-professional-page" aria-labelledby="deal-title">
      <button className="trial-back-button" type="button" onClick={onClose}>
        <ArrowLeft size={17} />
        返回交易列表
      </button>
      {loading ? (
        <Spinner label="正在加载交易专业档案" />
      ) : error ? (
        <ErrorState message={error.message || "交易专业档案加载失败"} retry={onRetry} />
      ) : data ? (
        <>
          <header className="deal-professional-header">
            <div>
              <span>
                交易专业档案 · {dealTypeLabels[data.deal_type] ?? data.deal_type} · {formatDate(data.announced_at)}
              </span>
              <h2 id="deal-title">{data.name}</h2>
              <div className="trial-detail-status">
                <StatusBadge value={statusLabels[data.status] ?? data.status} />
                <span>{directionLabels[data.direction] ?? data.direction}</span>
                <span>{data.territory ?? "交易地域未披露"}</span>
              </div>
            </div>
          </header>
          <dl className="dossier-metrics deal-professional-metrics" aria-label="交易关键指标">
            <DetailValue term="交易状态" value={statusLabels[data.status] ?? data.status} />
            <DetailValue term="参与方" value={String(data.party_roles.length || data.party_entities.length)} />
            <DetailValue term="交易资产" value={String(data.asset_stages.length || data.asset_entities.length)} />
            <DetailValue term="地域权益" value={String(data.rights.length)} />
            <DetailValue term="首付款" value={formatAmount(data.upfront_amount, data.currency)} />
            <DetailValue term="潜在总额" value={formatAmount(data.total_potential_amount, data.currency)} />
          </dl>
          <ResearchTabList
            tabs={dealDossierTabs}
            activeTab={activeSection}
            onChange={onSectionChange}
            ariaLabel="交易专业档案分区"
            idPrefix="deal-dossier"
            className="trial-professional-tabs"
          />
          <div
            id={`deal-dossier-panel-${activeSection}`}
            role="tabpanel"
            aria-labelledby={`deal-dossier-tab-${activeSection}`}
            className="deal-professional-body"
          >
            {activeSection === "overview" ? (
              <section>
                <h3>交易口径</h3>
                <dl className="trial-detail-grid">
                  <DetailValue term="状态" value={statusLabels[data.status] ?? data.status} />
                  <DetailValue term="方向" value={directionLabels[data.direction] ?? data.direction} />
                  <DetailValue term="方向参照地区" value={data.direction_reference_jurisdiction} />
                  <DetailValue term="初始披露" value={formatDate(data.announced_at)} />
                  <DetailValue term="终止日期" value={formatDate(data.terminated_at)} />
                  <DetailValue term="信息更新" value={formatDate(data.source_updated_at)} />
                  <DetailValue term="首付款" value={formatAmount(data.upfront_amount, data.currency)} />
                  <DetailValue term="潜在总额" value={formatAmount(data.total_potential_amount, data.currency)} />
                </dl>
              </section>
            ) : null}
            {activeSection === "parties" ? (
              <section>
                <h3>参与方角色</h3>
                <div className="deal-detail-list">
                  {data.party_roles.length ? (
                    data.party_roles.map((association) => (
                      <button
                        key={`${association.id}-${association.role}`}
                        type="button"
                        onClick={() => onOpenEntity(association.entity_type, association.id)}
                      >
                        <strong>{association.name}</strong>
                        <span>{partyRoleLabels[association.role] ?? association.role}</span>
                        <small>
                          {[association.country_region, association.organization_type].filter(Boolean).join(" · ") ||
                            "机构属性未披露"}
                        </small>
                      </button>
                    ))
                  ) : (
                    <span>参与方角色未披露</span>
                  )}
                </div>
              </section>
            ) : null}
            {activeSection === "assets" ? (
              <section>
                <h3>交易资产与阶段</h3>
                <div className="deal-detail-list">
                  {data.asset_stages.length ? (
                    data.asset_stages.map((asset) => (
                      <button key={asset.id} type="button" onClick={() => onOpenEntity(asset.entity_type, asset.id)}>
                        <strong>{asset.name}</strong>
                        <span>
                          {asset.development_phase_at_transaction
                            ? (phaseLabels[asset.development_phase_at_transaction] ??
                              asset.development_phase_at_transaction)
                            : "交易时阶段未披露"}
                          {asset.current_development_phase
                            ? ` → 当前 ${phaseLabels[asset.current_development_phase] ?? asset.current_development_phase}`
                            : ""}
                        </span>
                        <small>当前阶段时点 {formatDate(asset.current_phase_as_of, true)}</small>
                      </button>
                    ))
                  ) : (
                    <span>交易资产未披露</span>
                  )}
                </div>
              </section>
            ) : null}
            {activeSection === "rights" ? (
              <section>
                <h3>地域权益</h3>
                {data.rights.length ? (
                  <ScrollableTableRegion ariaLabel="交易权益明细" className="deal-rights-table-frame">
                    <table className="deal-rights-table" aria-label="交易权益">
                      <colgroup>
                        <col className="deal-rights-holder-column" />
                        <col className="deal-rights-type-column" />
                        <col className="deal-rights-territory-column" />
                        <col className="deal-rights-exclusivity-column" />
                        <col className="deal-rights-scope-column" />
                      </colgroup>
                      <thead>
                        <tr>
                          <th>权益持有人</th>
                          <th>类型</th>
                          <th>地区</th>
                          <th>独占性</th>
                          <th>范围</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.rights.map((right) => (
                          <tr key={right.id}>
                            <td>
                              <button
                                type="button"
                                onClick={() => onOpenEntity("organization", right.holder_entity_id)}
                              >
                                {right.holder_name}
                              </button>
                            </td>
                            <td>{rightTypeLabels[right.right_type] ?? right.right_type}</td>
                            <td>{right.territory}</td>
                            <td>{right.exclusive === null ? "未披露" : right.exclusive ? "独占" : "非独占"}</td>
                            <td>{right.scope_description ?? "范围说明未披露"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ScrollableTableRegion>
                ) : (
                  <span>地域权益未披露</span>
                )}
              </section>
            ) : null}
            {activeSection === "terms" ? (
              <section>
                <h3>披露条款与来源</h3>
                <dl className="trial-detail-grid">
                  {Object.entries(data.terms).map(([key, value]) => (
                    <DetailValue key={key} term={key} value={String(value)} />
                  ))}
                  <DetailValue term="源资料" value={data.source_document_id ?? "未关联"} />
                </dl>
              </section>
            ) : null}
            <section>
              <h3>来源与证据</h3>
              <p className="regulatory-source-reference">
                <FileText size={15} />
                {data.source_document_id ? `来源文档 ${data.source_document_id}` : "来源文档未关联"}
              </p>
              <ProvenanceButton
                selection={{ resourceType: "deal", resourceId: data.id, label: data.name }}
                onOpen={onOpenProvenance}
              />
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}

function DetailValue({ term, value }: { term: string; value: string | null | undefined }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value || "未披露"}</dd>
    </div>
  );
}
