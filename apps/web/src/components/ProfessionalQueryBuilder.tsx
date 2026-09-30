import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ClipboardList,
  FileBadge,
  FlaskConical,
  Handshake,
  Landmark,
  Newspaper,
  RefreshCw,
  RotateCcw,
  SlidersHorizontal,
  TrendingUp,
} from "lucide-react";
import { useEffect, useState } from "react";
import { dealKeys, loadDealFacetCatalog } from "../lib/contracts/deals";
import { epidemiologyKeys, loadEpidemiologyFacetCatalog } from "../lib/contracts/epidemiology";
import { loadNewsFacetCatalog, newsKeys } from "../lib/contracts/news";
import { loadPatentFacetCatalog, patentKeys, patentLegalStatusLabels } from "../lib/contracts/patents";
import { loadPipelineFacetCatalog, pipelineKeys } from "../lib/contracts/pipeline";
import { loadRegulatoryFacetCatalog, regulatoryKeys } from "../lib/contracts/regulatory";
import {
  dealTypeLabels,
  directionLabels,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../lib/dealDisplay";
import { epidemiologyMeasureLabels, epidemiologySexLabels } from "../lib/epidemiologyDisplay";
import { newsEntityTypes, newsEventTypeLabels, newsLanguageLabels } from "../lib/newsDisplay";
import { pipelineBooleanSignalLabels, pipelineResultEvaluationLabels } from "../lib/pipelineSignals";
import {
  countProfessionalConditions,
  createProfessionalSearchDraft,
  identifyProfessionalDatePreset,
  type PatentEntityType,
  type ProfessionalDatePreset,
  type ProfessionalSearchDomain,
  type ProfessionalSearchDraft,
  professionalSearchLocation,
  resolveProfessionalDatePreset,
  validateProfessionalSearch,
} from "../lib/professionalSearch";
import {
  boxedWarningLabels,
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  safetySignalLabels,
  safetyStatusLabels,
  severityLabels,
} from "../lib/regulatoryDisplay";
import {
  trialInitiationTypeLabels,
  trialKeyResultLabels,
  trialResultEvaluationLabels,
  trialTherapyLineLabels,
} from "../lib/trialFilters";
import type { WorkspaceLocation } from "../lib/workspaceRouting";
import { EntityFilterSelect } from "./EntityFilterSelect";
import { FacetMultiSelect, type FacetMultiSelectOption } from "./FacetMultiSelect";

const domains: Array<{
  value: ProfessionalSearchDomain;
  label: string;
  detail: string;
  icon: typeof FlaskConical;
}> = [
  { value: "pipeline", label: "药物与管线", detail: "实体、模态、阶段与地区", icon: FlaskConical },
  { value: "trials", label: "临床试验", detail: "注册、状态、分期与结果", icon: ClipboardList },
  { value: "patents", label: "专利情报", detail: "申请人、法律状态与专利族", icon: FileBadge },
  { value: "deals", label: "交易与公司", detail: "参与方、类型、方向与地域", icon: Handshake },
  { value: "regulatory", label: "监管与安全", detail: "机构、辖区、事件与状态", icon: Landmark },
  { value: "epidemiology", label: "流行病学", detail: "指标、地区、人群与周期", icon: TrendingUp },
  { value: "news", label: "资讯与会议", detail: "事件、发布方、语言与日期", icon: Newspaper },
];

const pipelinePhases = [
  ["discovery", "发现"],
  ["preclinical", "临床前"],
  ["ind", "IND"],
  ["phase_1", "I 期"],
  ["phase_1_2", "I/II 期"],
  ["phase_2", "II 期"],
  ["phase_2_3", "II/III 期"],
  ["phase_3", "III 期"],
  ["filed", "已申报"],
  ["approved", "已批准"],
] as const;

const trialPhases = [
  ["EARLY_PHASE1", "早期 I 期"],
  ["PHASE1", "I 期"],
  ["PHASE1_PHASE2", "I/II 期"],
  ["PHASE2", "II 期"],
  ["PHASE2_PHASE3", "II/III 期"],
  ["PHASE3", "III 期"],
  ["PHASE4", "IV 期"],
] as const;

type FacetCatalogState = "loading" | "failed" | "ready";

const pipelineProgramStatusLabels: Record<string, string> = {
  active: "进行中",
  inactive: "已停止",
  unknown: "状态未披露",
};

const pipelineOrganizationRoleLabels: Record<string, string> = {
  originator: "原研方",
  collaborator: "合作方",
  licensee: "被许可方",
  licensor: "许可方",
  manufacturer: "生产方",
  other: "其他",
};

function facetOptions(values: Record<string, number> | undefined, selected: string[] = []): FacetMultiSelectOption[] {
  const catalog = new Map(Object.entries(values ?? {}));
  for (const value of selected) {
    if (value && !catalog.has(value)) catalog.set(value, 0);
  }
  return [...catalog]
    .map(([value, count]) => ({ value, label: value, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function labeledFacetOptions(
  values: Record<string, number> | undefined,
  selected: string[],
  labels: Record<string, string>,
): FacetMultiSelectOption[] {
  return facetOptions(values, selected).map((option) => ({
    ...option,
    label: labels[option.value] ?? option.label,
  }));
}

function GovernedFacetPlaceholder({ label, state }: { label: string; state: Exclude<FacetCatalogState, "ready"> }) {
  return (
    <div className="professional-facet-placeholder" aria-disabled="true">
      <span>{label}</span>
      <small>{state === "loading" ? "读取中" : "暂不可用"}</small>
    </div>
  );
}

function GovernedFacetField({
  label,
  options,
  selected,
  state,
  onChange,
}: {
  label: string;
  options: FacetMultiSelectOption[];
  selected: string[];
  state: FacetCatalogState;
  onChange: (values: string[]) => void;
}) {
  if (state !== "ready") return <GovernedFacetPlaceholder label={label} state={state} />;
  if (!options.length) {
    // Empty governed catalogs are not a user-facing filter. Keep the form focused on conditions that can be used.
    return null;
  }
  return <FacetMultiSelect label={label} options={options} selected={selected} onChange={onChange} />;
}

function GovernedFacetSelect({
  label,
  options,
  value,
  state,
  disabled = false,
  onChange,
}: {
  label: string;
  options: FacetMultiSelectOption[];
  value: string;
  state: FacetCatalogState;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  if (state !== "ready") return <GovernedFacetPlaceholder label={label} state={state} />;
  if (!options.length) {
    // Empty governed catalogs are not a user-facing filter. Keep the form focused on conditions that can be used.
    return null;
  }
  return (
    <label>
      <span>{label}</span>
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="">全部</option>
        {options.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label} ({option.count})
          </option>
        ))}
      </select>
    </label>
  );
}

function DateRange({
  label,
  from,
  to,
  onChange,
}: {
  label: string;
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}) {
  const [preset, setPreset] = useState<ProfessionalDatePreset>(() => identifyProfessionalDatePreset(from, to));

  useEffect(() => {
    setPreset(identifyProfessionalDatePreset(from, to));
  }, [from, to]);

  function selectPreset(value: ProfessionalDatePreset) {
    setPreset(value);
    if (value === "custom") return;
    const range = resolveProfessionalDatePreset(value);
    onChange(range.from, range.to);
  }

  return (
    <fieldset className="professional-date-range" aria-label={label}>
      <legend>{label}</legend>
      <label className="professional-date-preset">
        <span>{label}时间范围</span>
        <select
          aria-label={`${label}时间范围`}
          value={preset}
          onChange={(event) => selectPreset(event.target.value as ProfessionalDatePreset)}
        >
          <option value="all">全部</option>
          <option value="last_month">近 1 个月</option>
          <option value="last_6_months">近半年</option>
          <option value="last_year">近 1 年</option>
          <option value="custom">自定义</option>
        </select>
      </label>
      {preset === "custom" ? (
        <div className="professional-custom-date-range">
          <label>
            <span>起</span>
            <input type="date" value={from} onChange={(event) => onChange(event.target.value, to)} />
          </label>
          <label>
            <span>止</span>
            <input type="date" value={to} onChange={(event) => onChange(from, event.target.value)} />
          </label>
        </div>
      ) : preset !== "all" ? (
        <output className="professional-date-output" aria-live="polite">
          {from} 至 {to}
        </output>
      ) : null}
    </fieldset>
  );
}

export function ProfessionalQueryBuilder({
  query,
  onExecute,
}: {
  query: string;
  onExecute: (location: WorkspaceLocation) => void;
}) {
  const [draft, setDraft] = useState(() => createProfessionalSearchDraft("pipeline", query));
  const [error, setError] = useState("");
  const pipelineCatalog = useQuery({
    queryKey: pipelineKeys.facetCatalog(),
    queryFn: ({ signal }) => loadPipelineFacetCatalog(signal),
    enabled: draft.domain === "pipeline",
    staleTime: 5 * 60 * 1000,
  });
  const patentCatalog = useQuery({
    queryKey: patentKeys.facetCatalog(),
    queryFn: ({ signal }) => loadPatentFacetCatalog(signal),
    enabled: draft.domain === "patents",
    staleTime: 5 * 60 * 1000,
  });
  const dealCatalog = useQuery({
    queryKey: dealKeys.facetCatalog(),
    queryFn: ({ signal }) => loadDealFacetCatalog(signal),
    enabled: draft.domain === "deals",
    staleTime: 5 * 60 * 1000,
  });
  const regulatoryCatalog = useQuery({
    queryKey: regulatoryKeys.facetCatalog(),
    queryFn: ({ signal }) => loadRegulatoryFacetCatalog(signal),
    enabled: draft.domain === "regulatory",
    staleTime: 5 * 60 * 1000,
  });
  const epidemiologyCatalog = useQuery({
    queryKey: epidemiologyKeys.facetCatalog(),
    queryFn: ({ signal }) => loadEpidemiologyFacetCatalog(signal),
    enabled: draft.domain === "epidemiology",
    staleTime: 5 * 60 * 1000,
  });
  const newsCatalog = useQuery({
    queryKey: newsKeys.facetCatalog(),
    queryFn: ({ signal }) => loadNewsFacetCatalog(signal),
    enabled: draft.domain === "news",
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    setDraft((current) => ({ ...current, query }));
  }, [query]);

  function update<K extends keyof ProfessionalSearchDraft>(key: K, value: ProfessionalSearchDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
    setError("");
  }

  function updateDateRange(
    fromKey: keyof ProfessionalSearchDraft,
    toKey: keyof ProfessionalSearchDraft,
    from: string,
    to: string,
  ) {
    setDraft((current) => ({ ...current, [fromKey]: from, [toKey]: to }));
    setError("");
  }

  function selectDomain(domain: ProfessionalSearchDomain) {
    setDraft(createProfessionalSearchDraft(domain, query));
    setError("");
  }

  function updatePatentEntityType(entityType: PatentEntityType) {
    setDraft((current) => ({ ...current, patentEntityType: entityType, patentEntityId: "" }));
    setError("");
  }

  function execute() {
    const validationError = validateProfessionalSearch(draft);
    if (validationError) {
      setError(validationError);
      return;
    }
    onExecute(professionalSearchLocation(draft));
  }

  const selected = domains.find((item) => item.value === draft.domain) ?? domains[0];
  const conditionCount = countProfessionalConditions(draft);
  const pipelineAdvancedConditionCount =
    draft.pipelineProgramTags.length +
    [
      draft.pipelineGlobalPhase,
      draft.pipelineChinaPhase,
      draft.pipelineGlobalPhaseStartedFrom,
      draft.pipelineGlobalPhaseStartedTo,
      draft.pipelineChinaPhaseStartedFrom,
      draft.pipelineChinaPhaseStartedTo,
      draft.pipelineDevelopmentRightsRegion,
      draft.pipelineCommercializationRightsRegion,
      draft.pipelineOrganizationRole,
      draft.pipelineOrganizationType,
      draft.pipelineOrganizationCountryRegion,
      draft.pipelineMilestoneType,
      draft.pipelineMilestoneFrom,
      draft.pipelineMilestoneTo,
    ].filter(Boolean).length;
  const pipelineSignalConditionCount = [
    draft.pipelineHasClinicalResults,
    draft.pipelineClinicalResultEvaluation,
    draft.pipelineHasDeal,
    draft.pipelineDealCurrency,
    draft.pipelineDealTotalPotentialAmountMin,
    draft.pipelineDealTotalPotentialAmountMax,
  ].filter(Boolean).length;
  const trialProfileConditionCount = [
    draft.trialAcronym,
    draft.trialInitiationType,
    draft.trialTherapyLine,
    draft.trialResultEvaluation,
  ].filter(Boolean).length;
  const trialEvidenceConditionCount = [
    draft.trialHasKeyResult,
    draft.trialPublicationId,
    draft.trialConference,
    draft.trialDisclosedFrom,
    draft.trialDisclosedTo,
  ].filter(Boolean).length;
  const pipelineCatalogState: FacetCatalogState = pipelineCatalog.isPending
    ? "loading"
    : pipelineCatalog.isError
      ? "failed"
      : "ready";
  const modalityOptions = facetOptions(pipelineCatalog.data?.facets?.modality, draft.modalities);
  const innovationTypeOptions = facetOptions(
    pipelineCatalog.data?.facets?.innovation_type,
    draft.pipelineInnovationTypes,
  );
  const therapeuticAreaOptions = facetOptions(
    pipelineCatalog.data?.facets?.therapeutic_area,
    draft.pipelineTherapeuticAreas,
  );
  const drugCategoryOptions = facetOptions(pipelineCatalog.data?.facets?.drug_category, draft.pipelineDrugCategories);
  const programStatusOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.program_status,
    [draft.pipelineProgramStatus],
    pipelineProgramStatusLabels,
  );
  const organizationRoleOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.organization_role,
    [draft.pipelineOrganizationRole],
    pipelineOrganizationRoleLabels,
  );
  const organizationTypeOptions = facetOptions(pipelineCatalog.data?.facets?.organization_type, [
    draft.pipelineOrganizationType,
  ]);
  const organizationCountryOptions = facetOptions(pipelineCatalog.data?.facets?.organization_country_region, [
    draft.pipelineOrganizationCountryRegion,
  ]);
  const geographyOptions = facetOptions(pipelineCatalog.data?.facets?.geography, [draft.geography]);
  const developmentRightsOptions = facetOptions(pipelineCatalog.data?.facets?.development_rights_region, [
    draft.pipelineDevelopmentRightsRegion,
  ]);
  const commercializationRightsOptions = facetOptions(pipelineCatalog.data?.facets?.commercialization_rights_region, [
    draft.pipelineCommercializationRightsRegion,
  ]);
  const programTagOptions = facetOptions(pipelineCatalog.data?.facets?.program_tag, draft.pipelineProgramTags);
  const milestoneTypeOptions = facetOptions(pipelineCatalog.data?.facets?.milestone_type, [
    draft.pipelineMilestoneType,
  ]);
  const clinicalResultPresenceOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.has_clinical_results,
    [draft.pipelineHasClinicalResults],
    pipelineBooleanSignalLabels,
  );
  const clinicalResultEvaluationOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.clinical_result_evaluation,
    [draft.pipelineClinicalResultEvaluation],
    pipelineResultEvaluationLabels,
  );
  const dealPresenceOptions = labeledFacetOptions(
    pipelineCatalog.data?.facets?.has_deal,
    [draft.pipelineHasDeal],
    pipelineBooleanSignalLabels,
  );
  const pipelineDealCurrencyOptions = facetOptions(pipelineCatalog.data?.facets?.deal_currency, [
    draft.pipelineDealCurrency,
  ]);
  const patentCatalogState: FacetCatalogState = patentCatalog.isPending
    ? "loading"
    : patentCatalog.isError
      ? "failed"
      : "ready";
  const patentLegalStatusOptions = labeledFacetOptions(
    patentCatalog.data?.facets?.legal_status,
    [draft.legalStatus],
    patentLegalStatusLabels,
  );
  const dealCatalogState: FacetCatalogState = dealCatalog.isPending
    ? "loading"
    : dealCatalog.isError
      ? "failed"
      : "ready";
  const dealTypeOptions = labeledFacetOptions(dealCatalog.data?.facets?.deal_type, [draft.dealType], dealTypeLabels);
  const dealStatusOptions = labeledFacetOptions(dealCatalog.data?.facets?.status, [draft.dealStatus], statusLabels);
  const dealDirectionOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.direction,
    [draft.dealDirection],
    directionLabels,
  );
  const dealTerritoryOptions = facetOptions(dealCatalog.data?.facets?.territory, [draft.dealTerritory]);
  const dealAssetModalityOptions = facetOptions(dealCatalog.data?.facets?.asset_modality, draft.dealAssetModalities);
  const dealAssetProgramTagOptions = facetOptions(
    dealCatalog.data?.facets?.asset_program_tag,
    draft.dealAssetProgramTags,
  );
  const dealPartyRoleOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.party_role,
    [draft.dealPartyRole],
    partyRoleLabels,
  );
  const dealPartyCountryOptions = facetOptions(dealCatalog.data?.facets?.party_country_region, [
    draft.dealPartyCountryRegion,
  ]);
  const dealPartyOrganizationTypeOptions = facetOptions(dealCatalog.data?.facets?.party_organization_type, [
    draft.dealPartyOrganizationType,
  ]);
  const dealTransactionPhaseOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.development_phase_at_transaction,
    [draft.dealDevelopmentPhaseAtTransaction],
    phaseLabels,
  );
  const dealCurrentPhaseOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.current_development_phase,
    [draft.dealCurrentDevelopmentPhase],
    phaseLabels,
  );
  const dealRightTypeOptions = labeledFacetOptions(
    dealCatalog.data?.facets?.right_type,
    [draft.dealRightType],
    rightTypeLabels,
  );
  const dealRightsTerritoryOptions = facetOptions(dealCatalog.data?.facets?.rights_territory, [
    draft.dealRightsTerritory,
  ]);
  const dealCurrencyOptions = facetOptions(dealCatalog.data?.facets?.currency, [draft.dealCurrency]);
  const dealAdvancedConditionCount =
    draft.dealAssetModalities.length +
    draft.dealAssetProgramTags.length +
    [
      draft.dealDirectionReferenceJurisdiction,
      draft.dealTerritory,
      draft.dealPartyRole,
      draft.dealPartyCountryRegion,
      draft.dealPartyOrganizationType,
      draft.dealDevelopmentPhaseAtTransaction,
      draft.dealCurrentDevelopmentPhase,
      draft.dealRightType,
      draft.dealRightsTerritory,
      draft.dealCurrency,
      draft.dealTerminatedFrom,
      draft.dealTerminatedTo,
      draft.dealSourceUpdatedFrom,
      draft.dealSourceUpdatedTo,
      draft.dealUpfrontAmountMin,
      draft.dealUpfrontAmountMax,
      draft.dealTotalPotentialAmountMin,
      draft.dealTotalPotentialAmountMax,
    ].filter(Boolean).length;
  const regulatoryCatalogState: FacetCatalogState = regulatoryCatalog.isPending
    ? "loading"
    : regulatoryCatalog.isError
      ? "failed"
      : "ready";
  const regulatoryAgencyOptions = facetOptions(regulatoryCatalog.data?.facets?.agency, [draft.regulatoryAgency]);
  const regulatoryJurisdictionOptions = facetOptions(regulatoryCatalog.data?.facets?.jurisdiction, [
    draft.regulatoryJurisdiction,
  ]);
  const regulatoryEventTypeOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.event_type,
    [draft.regulatoryEventType],
    eventTypeLabels,
  );
  const regulatoryStatusOptions = facetOptions(regulatoryCatalog.data?.facets?.status, [draft.regulatoryStatus]);
  const regulatoryDesignationOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.designation_type,
    [draft.regulatoryDesignationType],
    designationLabels,
  );
  const regulatoryLabelChangeOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.label_change_type,
    [draft.regulatoryLabelChangeType],
    labelChangeLabels,
  );
  const regulatoryBoxedWarningOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.has_boxed_warning,
    [draft.regulatoryBoxedWarning],
    boxedWarningLabels,
  );
  const regulatorySafetySignalOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.safety_signal_type,
    [draft.regulatorySafetySignalType],
    safetySignalLabels,
  );
  const regulatorySafetySeverityOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.safety_severity,
    [draft.regulatorySafetySeverity],
    severityLabels,
  );
  const regulatorySafetyStatusOptions = labeledFacetOptions(
    regulatoryCatalog.data?.facets?.safety_status,
    [draft.regulatorySafetyStatus],
    safetyStatusLabels,
  );
  const regulatoryAdvancedConditionCount = [
    draft.regulatoryDesignationType,
    draft.regulatoryLabelChangeType,
    draft.regulatoryBoxedWarning,
    draft.regulatorySafetySignalType,
    draft.regulatorySafetySeverity,
    draft.regulatorySafetyStatus,
    draft.regulatorySourceUpdatedFrom,
    draft.regulatorySourceUpdatedTo,
  ].filter(Boolean).length;
  const epidemiologyCatalogState: FacetCatalogState = epidemiologyCatalog.isPending
    ? "loading"
    : epidemiologyCatalog.isError
      ? "failed"
      : "ready";
  const epidemiologyMeasureOptions = labeledFacetOptions(
    epidemiologyCatalog.data?.facets?.measure,
    [draft.epidemiologyMeasure],
    epidemiologyMeasureLabels,
  );
  const epidemiologyGeographyOptions = facetOptions(epidemiologyCatalog.data?.facets?.geography, [
    draft.epidemiologyGeography,
  ]);
  const epidemiologyUnitOptions = facetOptions(epidemiologyCatalog.data?.facets?.unit, [draft.epidemiologyUnit]);
  const epidemiologyPopulationScopeOptions = facetOptions(epidemiologyCatalog.data?.facets?.population_scope, [
    draft.epidemiologyPopulationScope,
  ]);
  const epidemiologyAgeGroupOptions = facetOptions(epidemiologyCatalog.data?.facets?.age_group, [
    draft.epidemiologyAgeGroup,
  ]);
  const epidemiologySexOptions = labeledFacetOptions(
    epidemiologyCatalog.data?.facets?.sex,
    [draft.epidemiologySex],
    epidemiologySexLabels,
  );
  const epidemiologyPatientPopulationOptions = (epidemiologyCatalog.data?.patient_populations ?? [])
    .map((option) => ({ value: option.id, label: option.name, count: option.count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
  if (
    draft.epidemiologyPatientPopulationId &&
    !epidemiologyPatientPopulationOptions.some((option) => option.value === draft.epidemiologyPatientPopulationId)
  ) {
    epidemiologyPatientPopulationOptions.push({
      value: draft.epidemiologyPatientPopulationId,
      label: draft.epidemiologyPatientPopulationId,
      count: 0,
    });
  }
  const newsCatalogState: FacetCatalogState = newsCatalog.isPending
    ? "loading"
    : newsCatalog.isError
      ? "failed"
      : "ready";
  const newsEventTypeOptions = labeledFacetOptions(
    newsCatalog.data?.facets?.event_type,
    [draft.newsEventType],
    newsEventTypeLabels,
  );
  const newsPublisherOptions = facetOptions(newsCatalog.data?.facets?.publisher, [draft.newsPublisher]);
  const newsLanguageOptions = labeledFacetOptions(
    newsCatalog.data?.facets?.language,
    [draft.newsLanguage],
    newsLanguageLabels,
  );
  const newsVenueOptions = facetOptions(newsCatalog.data?.facets?.venue, [draft.newsVenue]);

  return (
    <section className="professional-query-builder" aria-labelledby="professional-query-title">
      <header>
        <div>
          <strong id="professional-query-title">专业条件查询</strong>
          <span>
            {selected.label} · {conditionCount ? `已选 ${conditionCount} 项` : "全部记录"}
          </span>
        </div>
        <button
          type="button"
          className="text-button"
          onClick={() => setDraft(createProfessionalSearchDraft(draft.domain, query))}
          disabled={conditionCount === Number(Boolean(query.trim()))}
        >
          <RotateCcw size={14} />
          清除条件
        </button>
      </header>

      <nav aria-label="专业数据域">
        {domains.map(({ value, label, detail, icon: Icon }) => (
          <button
            type="button"
            key={value}
            className={draft.domain === value ? "selected" : ""}
            onClick={() => selectDomain(value)}
            aria-pressed={draft.domain === value}
            title={detail}
          >
            <Icon size={15} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="professional-query-fields">
        {draft.domain === "pipeline" ? (
          <>
            <div className="professional-entity-row">
              <EntityFilterSelect
                label="药品"
                entityType="drug"
                value={draft.drugEntityId}
                onChange={(value) => update("drugEntityId", value)}
                placeholder="输入规范药品"
              />
              <EntityFilterSelect
                label="靶点"
                entityType="target"
                value={draft.targetEntityId}
                onChange={(value) => update("targetEntityId", value)}
                placeholder="输入规范靶点"
              />
              <EntityFilterSelect
                label="适应症"
                entityType="disease"
                value={draft.diseaseEntityId}
                onChange={(value) => update("diseaseEntityId", value)}
                placeholder="输入疾病或适应症"
              />
              <EntityFilterSelect
                label="研发机构"
                entityType="organization"
                value={draft.organizationEntityId}
                onChange={(value) => update("organizationEntityId", value)}
                placeholder="输入机构名称"
              />
            </div>
            {pipelineCatalog.isPending ? (
              <div className="professional-facet-catalog-state" role="status">
                正在读取管线筛选选项
              </div>
            ) : null}
            {pipelineCatalog.isError ? (
              <div className="professional-facet-catalog-state error" role="alert">
                <span>管线筛选选项暂不可用</span>
                <button type="button" className="text-button" onClick={() => void pipelineCatalog.refetch()}>
                  <RefreshCw size={13} />
                  重试
                </button>
              </div>
            ) : null}
            <GovernedFacetField
              label="药物模态"
              options={modalityOptions}
              selected={draft.modalities}
              state={pipelineCatalogState}
              onChange={(values) => update("modalities", values)}
            />
            <GovernedFacetField
              label="创新类型"
              options={innovationTypeOptions}
              selected={draft.pipelineInnovationTypes}
              state={pipelineCatalogState}
              onChange={(values) => update("pipelineInnovationTypes", values)}
            />
            <GovernedFacetField
              label="治疗领域"
              options={therapeuticAreaOptions}
              selected={draft.pipelineTherapeuticAreas}
              state={pipelineCatalogState}
              onChange={(values) => update("pipelineTherapeuticAreas", values)}
            />
            <GovernedFacetField
              label="药品类别"
              options={drugCategoryOptions}
              selected={draft.pipelineDrugCategories}
              state={pipelineCatalogState}
              onChange={(values) => update("pipelineDrugCategories", values)}
            />
            <label>
              <span>总体最高阶段</span>
              <select value={draft.phase} onChange={(event) => update("phase", event.target.value)}>
                <option value="">全部</option>
                {pipelinePhases.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <GovernedFacetSelect
              label="项目状态"
              options={programStatusOptions}
              value={draft.pipelineProgramStatus}
              state={pipelineCatalogState}
              onChange={(value) => update("pipelineProgramStatus", value)}
            />
            <GovernedFacetSelect
              label="记录地区"
              options={geographyOptions}
              value={draft.geography}
              state={pipelineCatalogState}
              onChange={(value) => update("geography", value)}
            />
            <DateRange
              label="状态日期"
              from={draft.statusDateFrom}
              to={draft.statusDateTo}
              onChange={(from, to) => updateDateRange("statusDateFrom", "statusDateTo", from, to)}
            />
            <details className="professional-more-fields">
              <summary>
                <SlidersHorizontal size={14} />
                <span>更多管线条件</span>
                <small>
                  {pipelineAdvancedConditionCount
                    ? `已选 ${pipelineAdvancedConditionCount} 项`
                    : "区域阶段、机构、权益与里程碑"}
                </small>
              </summary>
              <div className="professional-more-fields-grid">
                <label>
                  <span>全球最高阶段</span>
                  <select
                    value={draft.pipelineGlobalPhase}
                    onChange={(event) => update("pipelineGlobalPhase", event.target.value)}
                  >
                    <option value="">全部</option>
                    {pipelinePhases.map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>中国最高阶段</span>
                  <select
                    value={draft.pipelineChinaPhase}
                    onChange={(event) => update("pipelineChinaPhase", event.target.value)}
                  >
                    <option value="">全部</option>
                    {pipelinePhases.map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <DateRange
                  label="全球阶段开始日期"
                  from={draft.pipelineGlobalPhaseStartedFrom}
                  to={draft.pipelineGlobalPhaseStartedTo}
                  onChange={(from, to) =>
                    updateDateRange("pipelineGlobalPhaseStartedFrom", "pipelineGlobalPhaseStartedTo", from, to)
                  }
                />
                <DateRange
                  label="中国阶段开始日期"
                  from={draft.pipelineChinaPhaseStartedFrom}
                  to={draft.pipelineChinaPhaseStartedTo}
                  onChange={(from, to) =>
                    updateDateRange("pipelineChinaPhaseStartedFrom", "pipelineChinaPhaseStartedTo", from, to)
                  }
                />
                <GovernedFacetSelect
                  label="研发权益地区"
                  options={developmentRightsOptions}
                  value={draft.pipelineDevelopmentRightsRegion}
                  state={pipelineCatalogState}
                  onChange={(value) => update("pipelineDevelopmentRightsRegion", value)}
                />
                <GovernedFacetSelect
                  label="商业化权益地区"
                  options={commercializationRightsOptions}
                  value={draft.pipelineCommercializationRightsRegion}
                  state={pipelineCatalogState}
                  onChange={(value) => update("pipelineCommercializationRightsRegion", value)}
                />
                <GovernedFacetSelect
                  label="机构角色"
                  options={organizationRoleOptions}
                  value={draft.pipelineOrganizationRole}
                  state={pipelineCatalogState}
                  onChange={(value) => update("pipelineOrganizationRole", value)}
                />
                <GovernedFacetSelect
                  label="机构类型"
                  options={organizationTypeOptions}
                  value={draft.pipelineOrganizationType}
                  state={pipelineCatalogState}
                  onChange={(value) => update("pipelineOrganizationType", value)}
                />
                <GovernedFacetSelect
                  label="机构所在地区"
                  options={organizationCountryOptions}
                  value={draft.pipelineOrganizationCountryRegion}
                  state={pipelineCatalogState}
                  onChange={(value) => update("pipelineOrganizationCountryRegion", value)}
                />
                <GovernedFacetField
                  label="项目标签"
                  options={programTagOptions}
                  selected={draft.pipelineProgramTags}
                  state={pipelineCatalogState}
                  onChange={(values) => update("pipelineProgramTags", values)}
                />
                <GovernedFacetSelect
                  label="里程碑类型"
                  options={milestoneTypeOptions}
                  value={draft.pipelineMilestoneType}
                  state={pipelineCatalogState}
                  onChange={(value) => update("pipelineMilestoneType", value)}
                />
                <DateRange
                  label="里程碑日期"
                  from={draft.pipelineMilestoneFrom}
                  to={draft.pipelineMilestoneTo}
                  onChange={(from, to) => updateDateRange("pipelineMilestoneFrom", "pipelineMilestoneTo", from, to)}
                />
              </div>
            </details>
            <details className="professional-more-fields" open={pipelineSignalConditionCount > 0 || undefined}>
              <summary>
                <SlidersHorizontal size={14} />
                <span>临床结果与交易信号</span>
                <small>{pipelineSignalConditionCount ? `已选 ${pipelineSignalConditionCount} 项` : "按需展开"}</small>
              </summary>
              <div className="professional-more-fields-grid">
                <GovernedFacetSelect
                  label="是否已有临床结果"
                  options={clinicalResultPresenceOptions}
                  value={draft.pipelineHasClinicalResults}
                  state={pipelineCatalogState}
                  onChange={(value) => {
                    const next = value as ProfessionalSearchDraft["pipelineHasClinicalResults"];
                    setDraft((current) => ({
                      ...current,
                      pipelineHasClinicalResults: next,
                      pipelineClinicalResultEvaluation:
                        next === "false" ? "" : current.pipelineClinicalResultEvaluation,
                    }));
                    setError("");
                  }}
                />
                <GovernedFacetSelect
                  label="临床结果评价"
                  options={clinicalResultEvaluationOptions}
                  value={draft.pipelineClinicalResultEvaluation}
                  state={pipelineCatalogState}
                  disabled={draft.pipelineHasClinicalResults === "false"}
                  onChange={(value) => update("pipelineClinicalResultEvaluation", value)}
                />
                <GovernedFacetSelect
                  label="是否存在交易记录"
                  options={dealPresenceOptions}
                  value={draft.pipelineHasDeal}
                  state={pipelineCatalogState}
                  onChange={(value) => {
                    const next = value as ProfessionalSearchDraft["pipelineHasDeal"];
                    setDraft((current) => ({
                      ...current,
                      pipelineHasDeal: next,
                      pipelineDealCurrency: next === "false" ? "" : current.pipelineDealCurrency,
                      pipelineDealTotalPotentialAmountMin:
                        next === "false" ? "" : current.pipelineDealTotalPotentialAmountMin,
                      pipelineDealTotalPotentialAmountMax:
                        next === "false" ? "" : current.pipelineDealTotalPotentialAmountMax,
                    }));
                    setError("");
                  }}
                />
                <GovernedFacetSelect
                  label="交易币种"
                  options={pipelineDealCurrencyOptions}
                  value={draft.pipelineDealCurrency}
                  state={pipelineCatalogState}
                  disabled={draft.pipelineHasDeal === "false"}
                  onChange={(value) => update("pipelineDealCurrency", value)}
                />
                <label>
                  <span>潜在总额下限</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    disabled={draft.pipelineHasDeal === "false"}
                    value={draft.pipelineDealTotalPotentialAmountMin}
                    onChange={(event) => update("pipelineDealTotalPotentialAmountMin", event.target.value)}
                    placeholder="例如 100000000"
                  />
                </label>
                <label>
                  <span>潜在总额上限</span>
                  <input
                    type="number"
                    min={draft.pipelineDealTotalPotentialAmountMin || "0"}
                    step="0.01"
                    inputMode="decimal"
                    disabled={draft.pipelineHasDeal === "false"}
                    value={draft.pipelineDealTotalPotentialAmountMax}
                    onChange={(event) => update("pipelineDealTotalPotentialAmountMax", event.target.value)}
                    placeholder="例如 500000000"
                  />
                </label>
              </div>
            </details>
          </>
        ) : null}

        {draft.domain === "trials" ? (
          <>
            <label>
              <span>注册平台</span>
              <select value={draft.registry} onChange={(event) => update("registry", event.target.value)}>
                <option value="">全部</option>
                <option value="ClinicalTrials.gov">ClinicalTrials.gov</option>
                <option value="ChiCTR">ChiCTR</option>
                <option value="EU CTIS">EU CTIS</option>
              </select>
            </label>
            <label>
              <span>招募状态</span>
              <select value={draft.trialStatus} onChange={(event) => update("trialStatus", event.target.value)}>
                <option value="">全部</option>
                <option value="RECRUITING">招募中</option>
                <option value="ACTIVE_NOT_RECRUITING">进行中，停止招募</option>
                <option value="COMPLETED">已完成</option>
                <option value="TERMINATED">终止</option>
              </select>
            </label>
            <label>
              <span>临床分期</span>
              <select value={draft.trialPhase} onChange={(event) => update("trialPhase", event.target.value)}>
                <option value="">全部</option>
                {trialPhases.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>研究类型</span>
              <select value={draft.studyType} onChange={(event) => update("studyType", event.target.value)}>
                <option value="">全部</option>
                <option value="INTERVENTIONAL">干预性研究</option>
                <option value="OBSERVATIONAL">观察性研究</option>
                <option value="EXPANDED_ACCESS">扩大使用</option>
              </select>
            </label>
            <label>
              <span>结果发布</span>
              <select
                aria-label="结果发布"
                value={draft.trialHasResults}
                onChange={(event) => {
                  const value = event.target.value;
                  setDraft((current) => ({
                    ...current,
                    trialHasResults: value,
                    trialResultEvaluation: value === "false" ? "" : current.trialResultEvaluation,
                  }));
                  setError("");
                }}
              >
                <option value="">全部</option>
                <option value="true">已发布</option>
                <option value="false">未发布</option>
              </select>
            </label>
            <DateRange
              label="结果发布日期"
              from={draft.trialResultsPostedFrom}
              to={draft.trialResultsPostedTo}
              onChange={(from, to) => updateDateRange("trialResultsPostedFrom", "trialResultsPostedTo", from, to)}
            />
            <details className="professional-more-fields" open={trialProfileConditionCount > 0 || undefined}>
              <summary>
                <SlidersHorizontal size={14} />
                <span>试验属性与结果评价</span>
                <small>{trialProfileConditionCount ? `已选 ${trialProfileConditionCount} 项` : "按需展开"}</small>
              </summary>
              <div className="professional-more-fields-grid">
                <label>
                  <span>试验简称</span>
                  <input
                    value={draft.trialAcronym}
                    onChange={(event) => update("trialAcronym", event.target.value)}
                    placeholder="如 KEYNOTE、CheckMate"
                    maxLength={240}
                  />
                </label>
                <label>
                  <span>发起类型</span>
                  <select
                    value={draft.trialInitiationType}
                    onChange={(event) => update("trialInitiationType", event.target.value)}
                  >
                    <option value="">全部</option>
                    {Object.entries(trialInitiationTypeLabels).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>治疗线次</span>
                  <select
                    value={draft.trialTherapyLine}
                    onChange={(event) => update("trialTherapyLine", event.target.value)}
                  >
                    <option value="">全部</option>
                    {Object.entries(trialTherapyLineLabels).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>结果最优评价</span>
                  <select
                    value={draft.trialResultEvaluation}
                    disabled={draft.trialHasResults === "false"}
                    onChange={(event) => update("trialResultEvaluation", event.target.value)}
                  >
                    <option value="">全部</option>
                    {Object.entries(trialResultEvaluationLabels).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </details>
            <details className="professional-more-fields" open={trialEvidenceConditionCount > 0 || undefined}>
              <summary>
                <FileBadge size={14} />
                <span>关键结果与发表证据</span>
                <small>{trialEvidenceConditionCount ? `已选 ${trialEvidenceConditionCount} 项` : "按需展开"}</small>
              </summary>
              <div className="professional-more-fields-grid">
                <label>
                  <span>关键结果</span>
                  <select
                    value={draft.trialHasKeyResult}
                    onChange={(event) => update("trialHasKeyResult", event.target.value)}
                  >
                    <option value="">全部</option>
                    {Object.entries(trialKeyResultLabels).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>发表编号</span>
                  <input
                    value={draft.trialPublicationId}
                    onChange={(event) => update("trialPublicationId", event.target.value)}
                    placeholder="PMID、DOI 或会议摘要编号"
                    maxLength={240}
                  />
                </label>
                <label>
                  <span>会议</span>
                  <input
                    value={draft.trialConference}
                    onChange={(event) => update("trialConference", event.target.value)}
                    placeholder="如 ASCO、AACR"
                    maxLength={500}
                  />
                </label>
                <DateRange
                  label="结果披露日期"
                  from={draft.trialDisclosedFrom}
                  to={draft.trialDisclosedTo}
                  onChange={(from, to) => updateDateRange("trialDisclosedFrom", "trialDisclosedTo", from, to)}
                />
              </div>
            </details>
          </>
        ) : null}

        {draft.domain === "patents" ? (
          <>
            <div className="professional-entity-row single">
              <label>
                <span>关联实体类型</span>
                <select
                  value={draft.patentEntityType}
                  onChange={(event) => updatePatentEntityType(event.target.value as PatentEntityType)}
                >
                  <option value="target">靶点</option>
                  <option value="drug">药品</option>
                  <option value="disease">疾病/适应症</option>
                  <option value="organization">机构</option>
                </select>
              </label>
              <EntityFilterSelect
                label="关联实体"
                entityType={draft.patentEntityType}
                value={draft.patentEntityId}
                onChange={(value) => update("patentEntityId", value)}
                placeholder="输入药品、靶点、适应症或机构"
              />
            </div>
            <label>
              <span>申请人</span>
              <input value={draft.applicant} onChange={(event) => update("applicant", event.target.value)} />
            </label>
            {patentCatalog.isPending ? (
              <div className="professional-facet-catalog-state" role="status">
                正在读取专利筛选选项
              </div>
            ) : null}
            {patentCatalog.isError ? (
              <div className="professional-facet-catalog-state error" role="alert">
                <span>专利筛选选项暂不可用</span>
                <button type="button" className="text-button" onClick={() => void patentCatalog.refetch()}>
                  <RefreshCw size={13} />
                  重试
                </button>
              </div>
            ) : null}
            <GovernedFacetSelect
              label="法律状态"
              options={patentLegalStatusOptions}
              value={draft.legalStatus}
              state={patentCatalogState}
              onChange={(value) => update("legalStatus", value)}
            />
            <DateRange
              label="优先权日期"
              from={draft.patentPriorityFrom}
              to={draft.patentPriorityTo}
              onChange={(from, to) => updateDateRange("patentPriorityFrom", "patentPriorityTo", from, to)}
            />
            <DateRange
              label="到期日期"
              from={draft.patentExpirationFrom}
              to={draft.patentExpirationTo}
              onChange={(from, to) => updateDateRange("patentExpirationFrom", "patentExpirationTo", from, to)}
            />
          </>
        ) : null}

        {draft.domain === "deals" ? (
          <>
            <div className="professional-entity-row">
              <EntityFilterSelect
                label="交易药品"
                entityType="drug"
                value={draft.dealAssetEntityId}
                onChange={(value) => update("dealAssetEntityId", value)}
                placeholder="输入规范药品"
              />
              <EntityFilterSelect
                label="关联靶点"
                entityType="target"
                value={draft.dealTargetEntityId}
                onChange={(value) => update("dealTargetEntityId", value)}
                placeholder="输入规范靶点"
              />
              <EntityFilterSelect
                label="关联适应症"
                entityType="disease"
                value={draft.dealDiseaseEntityId}
                onChange={(value) => update("dealDiseaseEntityId", value)}
                placeholder="输入疾病或适应症"
              />
              <EntityFilterSelect
                label="参与机构"
                entityType="organization"
                value={draft.dealPartyEntityId}
                onChange={(value) => update("dealPartyEntityId", value)}
                placeholder="输入规范机构"
              />
            </div>
            {dealCatalog.isPending ? (
              <div className="professional-facet-catalog-state" role="status">
                正在读取交易筛选选项
              </div>
            ) : null}
            {dealCatalog.isError ? (
              <div className="professional-facet-catalog-state error" role="alert">
                <span>交易筛选选项暂不可用</span>
                <button type="button" className="text-button" onClick={() => void dealCatalog.refetch()}>
                  <RefreshCw size={13} />
                  重试
                </button>
              </div>
            ) : null}
            <GovernedFacetSelect
              label="交易类型"
              options={dealTypeOptions}
              value={draft.dealType}
              state={dealCatalogState}
              onChange={(value) => update("dealType", value)}
            />
            <GovernedFacetSelect
              label="交易状态"
              options={dealStatusOptions}
              value={draft.dealStatus}
              state={dealCatalogState}
              onChange={(value) => update("dealStatus", value)}
            />
            <GovernedFacetSelect
              label="交易方向"
              options={dealDirectionOptions}
              value={draft.dealDirection}
              state={dealCatalogState}
              onChange={(value) => update("dealDirection", value)}
            />
            <DateRange
              label="交易披露日期"
              from={draft.dealAnnouncedFrom}
              to={draft.dealAnnouncedTo}
              onChange={(from, to) => updateDateRange("dealAnnouncedFrom", "dealAnnouncedTo", from, to)}
            />
            <details className="professional-more-fields" open={dealAdvancedConditionCount > 0 || undefined}>
              <summary>
                <SlidersHorizontal size={14} />
                <span>更多交易条件</span>
                <small>
                  {dealAdvancedConditionCount ? `已选 ${dealAdvancedConditionCount} 项` : "资产、参与方、权益与金额"}
                </small>
              </summary>
              <div className="professional-more-fields-grid">
                <label>
                  <span>方向参照地区</span>
                  <input
                    value={draft.dealDirectionReferenceJurisdiction}
                    onChange={(event) => update("dealDirectionReferenceJurisdiction", event.target.value)}
                    placeholder="如 CN、US"
                    maxLength={128}
                  />
                </label>
                <GovernedFacetSelect
                  label="交易地域"
                  options={dealTerritoryOptions}
                  value={draft.dealTerritory}
                  state={dealCatalogState}
                  onChange={(value) => update("dealTerritory", value)}
                />
                <GovernedFacetField
                  label="资产模态"
                  options={dealAssetModalityOptions}
                  selected={draft.dealAssetModalities}
                  state={dealCatalogState}
                  onChange={(values) => update("dealAssetModalities", values)}
                />
                <GovernedFacetField
                  label="资产项目标签"
                  options={dealAssetProgramTagOptions}
                  selected={draft.dealAssetProgramTags}
                  state={dealCatalogState}
                  onChange={(values) => update("dealAssetProgramTags", values)}
                />
                <GovernedFacetSelect
                  label="参与角色"
                  options={dealPartyRoleOptions}
                  value={draft.dealPartyRole}
                  state={dealCatalogState}
                  onChange={(value) => update("dealPartyRole", value)}
                />
                <GovernedFacetSelect
                  label="机构所在地区"
                  options={dealPartyCountryOptions}
                  value={draft.dealPartyCountryRegion}
                  state={dealCatalogState}
                  onChange={(value) => update("dealPartyCountryRegion", value)}
                />
                <GovernedFacetSelect
                  label="机构类型"
                  options={dealPartyOrganizationTypeOptions}
                  value={draft.dealPartyOrganizationType}
                  state={dealCatalogState}
                  onChange={(value) => update("dealPartyOrganizationType", value)}
                />
                <GovernedFacetSelect
                  label="交易时阶段"
                  options={dealTransactionPhaseOptions}
                  value={draft.dealDevelopmentPhaseAtTransaction}
                  state={dealCatalogState}
                  onChange={(value) => update("dealDevelopmentPhaseAtTransaction", value)}
                />
                <GovernedFacetSelect
                  label="当前最高阶段"
                  options={dealCurrentPhaseOptions}
                  value={draft.dealCurrentDevelopmentPhase}
                  state={dealCatalogState}
                  onChange={(value) => update("dealCurrentDevelopmentPhase", value)}
                />
                <GovernedFacetSelect
                  label="权益类型"
                  options={dealRightTypeOptions}
                  value={draft.dealRightType}
                  state={dealCatalogState}
                  onChange={(value) => update("dealRightType", value)}
                />
                <GovernedFacetSelect
                  label="权益地区"
                  options={dealRightsTerritoryOptions}
                  value={draft.dealRightsTerritory}
                  state={dealCatalogState}
                  onChange={(value) => update("dealRightsTerritory", value)}
                />
                <GovernedFacetSelect
                  label="币种"
                  options={dealCurrencyOptions}
                  value={draft.dealCurrency}
                  state={dealCatalogState}
                  onChange={(value) => update("dealCurrency", value)}
                />
                <DateRange
                  label="终止日期"
                  from={draft.dealTerminatedFrom}
                  to={draft.dealTerminatedTo}
                  onChange={(from, to) => updateDateRange("dealTerminatedFrom", "dealTerminatedTo", from, to)}
                />
                <DateRange
                  label="信息更新日期"
                  from={draft.dealSourceUpdatedFrom}
                  to={draft.dealSourceUpdatedTo}
                  onChange={(from, to) => updateDateRange("dealSourceUpdatedFrom", "dealSourceUpdatedTo", from, to)}
                />
                <label>
                  <span>首付款下限</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    value={draft.dealUpfrontAmountMin}
                    onChange={(event) => update("dealUpfrontAmountMin", event.target.value)}
                    placeholder="例如 10000000"
                  />
                </label>
                <label>
                  <span>首付款上限</span>
                  <input
                    type="number"
                    min={draft.dealUpfrontAmountMin || "0"}
                    step="0.01"
                    inputMode="decimal"
                    value={draft.dealUpfrontAmountMax}
                    onChange={(event) => update("dealUpfrontAmountMax", event.target.value)}
                    placeholder="例如 30000000"
                  />
                </label>
                <label>
                  <span>潜在总额下限</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    value={draft.dealTotalPotentialAmountMin}
                    onChange={(event) => update("dealTotalPotentialAmountMin", event.target.value)}
                    placeholder="例如 100000000"
                  />
                </label>
                <label>
                  <span>潜在总额上限</span>
                  <input
                    type="number"
                    min={draft.dealTotalPotentialAmountMin || "0"}
                    step="0.01"
                    inputMode="decimal"
                    value={draft.dealTotalPotentialAmountMax}
                    onChange={(event) => update("dealTotalPotentialAmountMax", event.target.value)}
                    placeholder="例如 500000000"
                  />
                </label>
              </div>
            </details>
          </>
        ) : null}

        {draft.domain === "regulatory" ? (
          <>
            {regulatoryCatalog.isPending ? (
              <div className="professional-facet-catalog-state" role="status">
                正在读取监管筛选选项
              </div>
            ) : null}
            {regulatoryCatalog.isError ? (
              <div className="professional-facet-catalog-state error" role="alert">
                <span>监管筛选选项暂不可用</span>
                <button type="button" className="text-button" onClick={() => void regulatoryCatalog.refetch()}>
                  <RefreshCw size={13} />
                  重试
                </button>
              </div>
            ) : null}
            <GovernedFacetSelect
              label="监管机构"
              options={regulatoryAgencyOptions}
              value={draft.regulatoryAgency}
              state={regulatoryCatalogState}
              onChange={(value) => update("regulatoryAgency", value)}
            />
            <GovernedFacetSelect
              label="辖区"
              options={regulatoryJurisdictionOptions}
              value={draft.regulatoryJurisdiction}
              state={regulatoryCatalogState}
              onChange={(value) => update("regulatoryJurisdiction", value)}
            />
            <GovernedFacetSelect
              label="事件类型"
              options={regulatoryEventTypeOptions}
              value={draft.regulatoryEventType}
              state={regulatoryCatalogState}
              onChange={(value) => update("regulatoryEventType", value)}
            />
            <GovernedFacetSelect
              label="事件状态"
              options={regulatoryStatusOptions}
              value={draft.regulatoryStatus}
              state={regulatoryCatalogState}
              onChange={(value) => update("regulatoryStatus", value)}
            />
            <DateRange
              label="监管决定日期"
              from={draft.regulatoryDecisionFrom}
              to={draft.regulatoryDecisionTo}
              onChange={(from, to) => updateDateRange("regulatoryDecisionFrom", "regulatoryDecisionTo", from, to)}
            />
            <details className="professional-more-fields" open={regulatoryAdvancedConditionCount > 0 || undefined}>
              <summary>
                <SlidersHorizontal size={14} />
                <span>更多监管与安全条件</span>
                <small>
                  {regulatoryAdvancedConditionCount
                    ? `已选 ${regulatoryAdvancedConditionCount} 项`
                    : "认定、标签、安全与来源时间"}
                </small>
              </summary>
              <div className="professional-more-fields-grid">
                <GovernedFacetSelect
                  label="认定资格"
                  options={regulatoryDesignationOptions}
                  value={draft.regulatoryDesignationType}
                  state={regulatoryCatalogState}
                  onChange={(value) => update("regulatoryDesignationType", value)}
                />
                <GovernedFacetSelect
                  label="标签变更"
                  options={regulatoryLabelChangeOptions}
                  value={draft.regulatoryLabelChangeType}
                  state={regulatoryCatalogState}
                  onChange={(value) => update("regulatoryLabelChangeType", value)}
                />
                <GovernedFacetSelect
                  label="黑框警告"
                  options={regulatoryBoxedWarningOptions}
                  value={draft.regulatoryBoxedWarning}
                  state={regulatoryCatalogState}
                  onChange={(value) => update("regulatoryBoxedWarning", value as "" | "true" | "false")}
                />
                <GovernedFacetSelect
                  label="安全信号"
                  options={regulatorySafetySignalOptions}
                  value={draft.regulatorySafetySignalType}
                  state={regulatoryCatalogState}
                  onChange={(value) => update("regulatorySafetySignalType", value)}
                />
                <GovernedFacetSelect
                  label="严重程度"
                  options={regulatorySafetySeverityOptions}
                  value={draft.regulatorySafetySeverity}
                  state={regulatoryCatalogState}
                  onChange={(value) => update("regulatorySafetySeverity", value)}
                />
                <GovernedFacetSelect
                  label="信号状态"
                  options={regulatorySafetyStatusOptions}
                  value={draft.regulatorySafetyStatus}
                  state={regulatoryCatalogState}
                  onChange={(value) => update("regulatorySafetyStatus", value)}
                />
                <DateRange
                  label="来源更新日期"
                  from={draft.regulatorySourceUpdatedFrom}
                  to={draft.regulatorySourceUpdatedTo}
                  onChange={(from, to) =>
                    updateDateRange("regulatorySourceUpdatedFrom", "regulatorySourceUpdatedTo", from, to)
                  }
                />
              </div>
            </details>
          </>
        ) : null}

        {draft.domain === "epidemiology" ? (
          <>
            <EntityFilterSelect
              label="疾病"
              entityType="disease"
              value={draft.diseaseEntityId}
              onChange={(value) => update("diseaseEntityId", value)}
              placeholder="输入疾病名称或别名"
            />
            {epidemiologyCatalog.isPending ? (
              <div className="professional-facet-catalog-state" role="status">
                正在读取流行病学筛选选项
              </div>
            ) : null}
            {epidemiologyCatalog.isError ? (
              <div className="professional-facet-catalog-state error" role="alert">
                <span>流行病学筛选选项暂不可用</span>
                <button type="button" className="text-button" onClick={() => void epidemiologyCatalog.refetch()}>
                  <RefreshCw size={13} />
                  重试
                </button>
              </div>
            ) : null}
            <GovernedFacetSelect
              label="统计指标"
              options={epidemiologyMeasureOptions}
              value={draft.epidemiologyMeasure}
              state={epidemiologyCatalogState}
              onChange={(value) => update("epidemiologyMeasure", value)}
            />
            <GovernedFacetSelect
              label="地区"
              options={epidemiologyGeographyOptions}
              value={draft.epidemiologyGeography}
              state={epidemiologyCatalogState}
              onChange={(value) => update("epidemiologyGeography", value)}
            />
            <GovernedFacetSelect
              label="单位"
              options={epidemiologyUnitOptions}
              value={draft.epidemiologyUnit}
              state={epidemiologyCatalogState}
              onChange={(value) => update("epidemiologyUnit", value)}
            />
            <GovernedFacetSelect
              label="标准患者人群"
              options={epidemiologyPatientPopulationOptions}
              value={draft.epidemiologyPatientPopulationId}
              state={epidemiologyCatalogState}
              onChange={(value) => update("epidemiologyPatientPopulationId", value)}
            />
            <GovernedFacetSelect
              label="人群口径"
              options={epidemiologyPopulationScopeOptions}
              value={draft.epidemiologyPopulationScope}
              state={epidemiologyCatalogState}
              onChange={(value) => update("epidemiologyPopulationScope", value)}
            />
            <GovernedFacetSelect
              label="年龄组"
              options={epidemiologyAgeGroupOptions}
              value={draft.epidemiologyAgeGroup}
              state={epidemiologyCatalogState}
              onChange={(value) => update("epidemiologyAgeGroup", value)}
            />
            <GovernedFacetSelect
              label="性别"
              options={epidemiologySexOptions}
              value={draft.epidemiologySex}
              state={epidemiologyCatalogState}
              onChange={(value) => update("epidemiologySex", value)}
            />
            <DateRange
              label="统计周期"
              from={draft.epidemiologyPeriodStartFrom}
              to={draft.epidemiologyPeriodEndTo}
              onChange={(from, to) =>
                updateDateRange("epidemiologyPeriodStartFrom", "epidemiologyPeriodEndTo", from, to)
              }
            />
          </>
        ) : null}

        {draft.domain === "news" ? (
          <>
            <EntityFilterSelect
              label="关联实体"
              entityType={newsEntityTypes}
              value={draft.newsEntityId}
              onChange={(value) => update("newsEntityId", value)}
              placeholder="输入药品、靶点、疾病、机构或技术"
            />
            {newsCatalog.isPending ? (
              <div className="professional-facet-catalog-state" role="status">
                正在读取新闻与会议筛选选项
              </div>
            ) : null}
            {newsCatalog.isError ? (
              <div className="professional-facet-catalog-state error" role="alert">
                <span>新闻与会议筛选选项暂不可用</span>
                <button type="button" className="text-button" onClick={() => void newsCatalog.refetch()}>
                  <RefreshCw size={13} />
                  重试
                </button>
              </div>
            ) : null}
            <GovernedFacetSelect
              label="事件类型"
              options={newsEventTypeOptions}
              value={draft.newsEventType}
              state={newsCatalogState}
              onChange={(value) => update("newsEventType", value)}
            />
            <GovernedFacetSelect
              label="发布方"
              options={newsPublisherOptions}
              value={draft.newsPublisher}
              state={newsCatalogState}
              onChange={(value) => update("newsPublisher", value)}
            />
            <GovernedFacetSelect
              label="语言"
              options={newsLanguageOptions}
              value={draft.newsLanguage}
              state={newsCatalogState}
              onChange={(value) => update("newsLanguage", value)}
            />
            <GovernedFacetSelect
              label="会议 / 场景"
              options={newsVenueOptions}
              value={draft.newsVenue}
              state={newsCatalogState}
              onChange={(value) => update("newsVenue", value)}
            />
            <label>
              <span>内容范围</span>
              <select
                value={draft.newsContentScope}
                onChange={(event) => update("newsContentScope", event.target.value as "" | "research")}
              >
                <option value="">全部资讯</option>
                <option value="research">论文与会议</option>
              </select>
            </label>
            <DateRange
              label="发布日期"
              from={draft.newsPublishedFrom}
              to={draft.newsPublishedTo}
              onChange={(from, to) => updateDateRange("newsPublishedFrom", "newsPublishedTo", from, to)}
            />
          </>
        ) : null}
      </div>

      <footer>
        <div>
          <strong>{selected.label}</strong>
          <span>{query.trim() ? `关键词：${query.trim()}` : "未限定关键词"}</span>
        </div>
        {error ? (
          <p className="inline-error" role="alert">
            {error}
          </p>
        ) : null}
        <button className="primary-button" type="button" onClick={execute}>
          查询 {selected.label}
          <ArrowRight size={15} />
        </button>
      </footer>
    </section>
  );
}
