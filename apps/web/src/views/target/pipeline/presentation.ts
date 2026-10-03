import { hasPipelineSearchFilter, type PipelineSearchFilters } from "../../../lib/contracts/pipeline";
import type { CompetitiveProgram } from "../../../lib/contracts/target";
import type { AppliedFilterRead, PipelineLandscapeRead } from "../../../lib/generated";
import { publicProgramTags } from "../../../lib/programDisplay";

export const targetDrugColumnOptions = [
  { key: "organizations", label: "研发机构" },
  { key: "targets", label: "靶点组合" },
  { key: "mechanism", label: "类型 / 机制" },
  { key: "indications", label: "适应症与阶段" },
  { key: "global_phase", label: "全球最高阶段" },
  { key: "china_phase", label: "中国最高阶段" },
  { key: "status", label: "项目状态" },
  { key: "clinical", label: "临床结果" },
  { key: "innovation", label: "创新类型" },
  { key: "updated", label: "最近更新" },
] as const;

export type TargetDrugColumnKey = (typeof targetDrugColumnOptions)[number]["key"];

export function defaultTargetDrugColumns(): Set<TargetDrugColumnKey> {
  return new Set(targetDrugColumnOptions.map((column) => column.key));
}

export function countAdvancedPipelineFilters(filters: PipelineSearchFilters): number {
  return [
    filters.innovationTypes.length,
    filters.drugCategories.length,
    filters.organizationRole,
    filters.organizationEntityId,
    filters.organizationType,
    filters.organizationCountryRegion,
    filters.globalPhase,
    filters.chinaPhase,
    filters.developmentRightsRegion,
    filters.commercializationRightsRegion,
    filters.programTags.length,
    filters.milestoneType,
    filters.globalPhaseStartedFrom,
    filters.globalPhaseStartedTo,
    filters.chinaPhaseStartedFrom,
    filters.chinaPhaseStartedTo,
    filters.statusDateFrom,
    filters.statusDateTo,
    filters.milestoneFrom,
    filters.milestoneTo,
    filters.clinicalResultEvaluation,
    filters.dealCurrency,
    filters.dealTotalPotentialAmountMin,
    filters.dealTotalPotentialAmountMax,
    filters.targetCombinationKey,
    filters.diseaseEntityId,
  ].filter(Boolean).length;
}

export const targetPipelineAppliedFilterLabels: Record<string, string> = {
  query: "药物或机构",
  modality: "药物类型",
  therapeutic_area: "适应症领域",
  innovation_type: "创新类型",
  drug_category: "药品类别",
  program_status: "项目状态",
  organization_role: "机构角色",
  organization_entity: "研发机构",
  organization_type: "机构标签",
  organization_country_region: "机构所在地区",
  target_combination_key: "靶点组合",
  disease_entity: "适应症",
  phase: "最高阶段",
  geography: "地区",
  global_phase: "全球最高阶段",
  china_phase: "中国最高阶段",
  development_rights_region: "研发权益地区",
  commercialization_rights_region: "商业化权益地区",
  program_tag: "项目标签",
  milestone_type: "里程碑类型",
  clinical_result: "临床结果",
  clinical_result_evaluation: "临床结果评价",
  deal: "交易信号",
  deal_currency: "交易币种",
  deal_total_potential_amount: "潜在交易总额",
  global_phase_started_at: "全球阶段开始日期",
  china_phase_started_at: "中国阶段开始日期",
  status_date: "状态更新日期",
  milestone_date: "里程碑日期",
};

function landscapeFilterLabel(
  landscape: PipelineLandscapeRead | undefined,
  field: "target_combinations" | "diseases",
  key: string,
  fallback: string,
) {
  return landscape?.[field]?.find((bucket) => bucket.key === key)?.label ?? fallback;
}

export function targetPipelineAppliedFilters(
  filters: PipelineSearchFilters,
  landscape?: PipelineLandscapeRead,
): AppliedFilterRead[] {
  const applied: AppliedFilterRead[] = [];
  const add = (field: string, operator: AppliedFilterRead["operator"], value: AppliedFilterRead["value"]) => {
    applied.push({ field, operator, value });
  };
  const addMany = (field: string, values: string[]) => {
    if (values.length) add(field, "in", values);
  };
  const addRange = (field: string, from: string, to: string) => {
    if (from) add(field, "gte", from);
    if (to) add(field, "lte", to);
  };

  if (filters.query.trim()) add("query", "contains", filters.query.trim());
  addMany("modality", filters.modalities);
  addMany("therapeutic_area", filters.therapeuticAreas);
  addMany("innovation_type", filters.innovationTypes);
  addMany("drug_category", filters.drugCategories);
  if (filters.programStatus && filters.programStatus !== "active") add("program_status", "eq", filters.programStatus);
  if (filters.organizationRole) add("organization_role", "eq", filters.organizationRole);
  if (filters.organizationEntityId) add("organization_entity", "eq", "已选机构");
  if (filters.organizationType) add("organization_type", "eq", filters.organizationType);
  if (filters.organizationCountryRegion) add("organization_country_region", "eq", filters.organizationCountryRegion);
  if (filters.targetCombinationKey) {
    add(
      "target_combination_key",
      "eq",
      landscapeFilterLabel(landscape, "target_combinations", filters.targetCombinationKey, "已选靶点组合"),
    );
  }
  if (filters.diseaseEntityId) {
    add("disease_entity", "eq", landscapeFilterLabel(landscape, "diseases", filters.diseaseEntityId, "已选适应症"));
  }
  if (filters.phase) add("phase", "eq", filters.phase);
  if (filters.geography) add("geography", "eq", filters.geography);
  if (filters.globalPhase) add("global_phase", "eq", filters.globalPhase);
  if (filters.chinaPhase) add("china_phase", "eq", filters.chinaPhase);
  if (filters.developmentRightsRegion) add("development_rights_region", "eq", filters.developmentRightsRegion);
  if (filters.commercializationRightsRegion) {
    add("commercialization_rights_region", "eq", filters.commercializationRightsRegion);
  }
  addMany("program_tag", publicProgramTags(filters.programTags));
  if (filters.milestoneType) add("milestone_type", "eq", filters.milestoneType);
  if (filters.hasClinicalResults) add("clinical_result", "eq", filters.hasClinicalResults === "true");
  if (filters.clinicalResultEvaluation) add("clinical_result_evaluation", "eq", filters.clinicalResultEvaluation);
  if (filters.hasDeal) add("deal", "eq", filters.hasDeal === "true");
  if (filters.dealCurrency) add("deal_currency", "eq", filters.dealCurrency);
  if (filters.dealTotalPotentialAmountMin || filters.dealTotalPotentialAmountMax) {
    add(
      "deal_total_potential_amount",
      "eq",
      [filters.dealTotalPotentialAmountMin, filters.dealTotalPotentialAmountMax].filter(Boolean).join(" – "),
    );
  }
  addRange("global_phase_started_at", filters.globalPhaseStartedFrom, filters.globalPhaseStartedTo);
  addRange("china_phase_started_at", filters.chinaPhaseStartedFrom, filters.chinaPhaseStartedTo);
  addRange("status_date", filters.statusDateFrom, filters.statusDateTo);
  addRange("milestone_date", filters.milestoneFrom, filters.milestoneTo);
  return applied;
}

export function pipelineLoadingLabel(targetName: string, filters: PipelineSearchFilters): string {
  const query = filters.query.trim();
  if (query) return `正在加载 ${targetName} 中与“${query}”匹配的研发项目`;
  if (filters.programStatus === "active") return `正在加载 ${targetName} 的在研项目`;
  if (filters.programStatus === "inactive") return `正在加载 ${targetName} 的已停止项目`;
  if (filters.programStatus === "unknown") return `正在加载 ${targetName} 的状态未披露项目`;
  if (hasPipelineSearchFilter({ ...filters, targetEntityId: "" })) {
    return `正在加载 ${targetName} 的筛选结果`;
  }
  return `正在加载 ${targetName} 的全部研发项目`;
}
const organizationRoleLabels: Record<string, string> = {
  originator: "原研方",
  collaborator: "合作方",
  licensee: "被许可方",
  licensor: "许可方",
  manufacturer: "生产方",
  other: "其他",
};

export function organizationRoleLabel(value: string): string {
  return organizationRoleLabels[value] ?? "其他";
}

export function programStatusLabel(value: CompetitiveProgram["program_status"] | string | null | undefined): string {
  const normalized = value?.toLowerCase();
  if (normalized === "active") return "在研";
  if (normalized === "inactive") return "已停止";
  return "状态未披露";
}

export function pipelineProgramStatusLabel(
  program: Pick<CompetitiveProgram, "program_status" | "program_status_counts">,
): string {
  const states = Object.entries(program.program_status_counts ?? {}).filter(([, count]) => count > 0);
  return states.length > 1 ? "混合状态" : programStatusLabel(program.program_status);
}

export const developmentPhaseLabels: Record<string, string> = {
  discovery: "药物发现",
  preclinical: "临床前",
  ind: "IND",
  phase_1: "I 期",
  phase_1_2: "I/II 期",
  phase_2: "II 期",
  phase_2_3: "II/III 期",
  phase_3: "III 期",
  filed: "申报上市",
  approved: "已批准",
  discontinued: "已终止",
};

export function developmentPhaseLabel(value: string): string {
  return developmentPhaseLabels[value.toLowerCase()] ?? value;
}

export type TargetFacetKey = "modality" | "therapeutic_area" | "innovation_type" | "drug_category" | "program_tag";

export function targetFacetOptions(values: Record<string, number> | undefined) {
  return Object.entries(values ?? {}).map(([value, count]) => ({ value, label: value, count }));
}

export const geographyLabels: Record<string, string> = {
  global: "全球",
  china: "中国",
  us: "美国",
  europe: "欧洲",
};

export function geographyLabel(value: string): string {
  return geographyLabels[value.toLowerCase()] ?? value;
}
export function pipelineSelectOptions(value: string, values: Record<string, number> | undefined): [string, number][] {
  const options = { ...(values ?? {}) };
  if (value && !(value in options)) options[value] = 0;
  return Object.entries(options);
}

export function isUnavailableFacetOption(count: number, optionValue: string, selectedValue: string): boolean {
  return count <= 0 && optionValue !== selectedValue;
}
