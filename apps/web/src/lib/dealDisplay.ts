export const dealTypeLabels: Record<string, string> = {
  license: "许可",
  collaboration: "合作",
  acquisition: "收购",
  merger: "合并",
  option: "选择权",
  co_development: "共同开发",
  commercialization: "商业化",
};

export const statusLabels: Record<string, string> = {
  announced: "已披露",
  active: "进行中",
  completed: "已完成",
  terminated: "已终止",
  withdrawn: "已撤回",
  superseded: "已替代",
  unknown: "未披露",
};

export const directionLabels: Record<string, string> = {
  domestic: "境内",
  inbound: "引进",
  outbound: "对外许可",
  cross_border: "跨境",
  global: "全球",
  undisclosed: "未披露",
};

export const partyRoleLabels: Record<string, string> = {
  licensor: "许可方",
  licensee: "被许可方",
  seller: "转让方",
  buyer: "受让方",
  acquirer: "收购方",
  target: "被收购方",
  partner: "合作方",
  investor: "投资方",
  investee: "被投方",
  other: "角色未披露",
};

export const rightTypeLabels: Record<string, string> = {
  research: "研究",
  development: "开发",
  manufacturing: "生产",
  commercialization: "商业化",
  co_development: "共同开发",
  co_promotion: "共同推广",
  distribution: "分销",
  option: "选择权",
  other: "其他",
};

export { compactPhaseLabels as phaseLabels } from "./phasePresentation";

/** Only controlled project captions are localized; source codes and labels remain literal. */
export function dealLabel(
  value: string | null | undefined,
  labels: Readonly<Record<string, string>>,
  sourceLabel?: string,
): string {
  if (!value) return professionalEnumLabel("未披露");
  return Object.hasOwn(labels, value) ? professionalEnumLabel(labels[value], value) : (sourceLabel ?? value);
}

export function localizedDealLabels(labels: Readonly<Record<string, string>>): Record<string, string> {
  return Object.fromEntries(Object.keys(labels).map((key) => [key, dealLabel(key, labels)]));
}

export function formatAmount(value: number | null, currency: string | null) {
  if (value === null) return professionalEnumLabel("未披露");
  if (!Number.isFinite(value)) return "--";
  const prefix = currency ? `${currency} ` : "";
  return `${prefix}${new Intl.NumberFormat(formattingLocale(), { maximumSignificantDigits: 21 }).format(value)}`;
}

export function displayTerms(terms: Record<string, unknown>) {
  const entries = Object.entries(terms);
  if (!entries.length) return "--";
  return entries
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(" · ");
}

import { formattingLocale } from "./i18n";
import { professionalEnumLabel } from "./i18n/professionalEnums";
