import { ClipboardList, FileBadge, FlaskConical, Handshake, Landmark, Newspaper, TrendingUp } from "lucide-react";
import { professionalEnumLabel } from "../../lib/i18n/professionalEnums";
import type { ProfessionalSearchDomain } from "../../lib/professionalSearch";
import type { FacetMultiSelectOption } from "../FacetMultiSelect";

export const domains: Array<{
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

export const pipelinePhases = [
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

export const trialPhases = [
  ["EARLY_PHASE1", "早期 I 期"],
  ["PHASE1", "I 期"],
  ["PHASE1_PHASE2", "I/II 期"],
  ["PHASE2", "II 期"],
  ["PHASE2_PHASE3", "II/III 期"],
  ["PHASE3", "III 期"],
  ["PHASE4", "IV 期"],
] as const;

export type FacetCatalogState = "loading" | "failed" | "ready";

export const pipelineProgramStatusLabels: Record<string, string> = {
  active: "进行中",
  inactive: "已停止",
  unknown: "状态未披露",
};

export const pipelineOrganizationRoleLabels: Record<string, string> = {
  originator: "原研方",
  collaborator: "合作方",
  licensee: "被许可方",
  licensor: "许可方",
  manufacturer: "生产方",
  other: "其他",
};

export function facetOptions(
  values: Record<string, number> | undefined,
  selected: string[] = [],
): FacetMultiSelectOption[] {
  const catalog = new Map(Object.entries(values ?? {}));
  for (const value of selected) {
    if (value && !catalog.has(value)) catalog.set(value, 0);
  }
  return [...catalog]
    .map(([value, count]) => ({ value, label: value, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

export function labeledFacetOptions(
  values: Record<string, number> | undefined,
  selected: string[],
  labels: Record<string, string>,
): FacetMultiSelectOption[] {
  return facetOptions(values, selected).map((option) => ({
    ...option,
    label: Object.hasOwn(labels, option.value)
      ? professionalEnumLabel(labels[option.value], option.value)
      : option.label,
  }));
}
