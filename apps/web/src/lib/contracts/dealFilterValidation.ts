import type { DealDirection, DealPartyRole, DealRightType, DealStatus } from "../generated";
import { developmentPhases } from "../phasePresentation";
import type { DealSearchFilters, DealSortField } from "./deals";
import { effectiveSort } from "./sorting";

export const dealStatuses = new Set<DealStatus>([
  "announced",
  "active",
  "completed",
  "terminated",
  "withdrawn",
  "superseded",
  "unknown",
]);
export const dealDirections = new Set<DealDirection>([
  "domestic",
  "inbound",
  "outbound",
  "cross_border",
  "global",
  "undisclosed",
]);
export const partyRoles = new Set<DealPartyRole>([
  "licensor",
  "licensee",
  "seller",
  "buyer",
  "acquirer",
  "target",
  "partner",
  "investor",
  "investee",
  "other",
]);
export const rightTypes = new Set<DealRightType>([
  "research",
  "development",
  "manufacturing",
  "commercialization",
  "co_development",
  "co_promotion",
  "distribution",
  "option",
  "other",
]);
export const amountSortFields = new Set<DealSortField>(["upfront_amount", "total_potential_amount"]);

function validCalendarDay(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

export function validDealAmount(value: string): boolean {
  const text = value.trim();
  return (
    text.length <= 120 &&
    /^(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text) &&
    Number.isFinite(Number(text)) &&
    Number(text) >= 0 &&
    !(Number(text) === 0 && /[1-9]/.test(text.split(/[eE]/)[0] ?? ""))
  );
}

/** Keep an API-representable decimal draft verbatim across URL/locale changes. */
export function boundedDealAmount(value: string | null): string {
  const text = value?.trim() ?? "";
  return text.length <= 120 && validDealAmount(text) ? text : "";
}

export function validateDealSearchFilters(filters: DealSearchFilters): string | null {
  if (filters.currency && !/^[A-Z]{3}$/.test(filters.currency)) return "币种必须是三位大写字母代码";
  const dateRanges: Array<[string, string, string]> = [
    [filters.announcedFrom, filters.announcedTo, "初始披露日期"],
    [filters.terminatedFrom, filters.terminatedTo, "终止日期"],
    [filters.sourceUpdatedFrom, filters.sourceUpdatedTo, "信息更新日期"],
  ];
  for (const [minimum, maximum, label] of dateRanges) {
    if ([minimum, maximum].some((value) => value && !validCalendarDay(value))) return `${label}必须是有效的日历日期`;
    if (minimum && maximum && minimum > maximum) return `${label}起始日期不能晚于结束日期`;
  }
  const amountRanges: Array<[string, string, string]> = [
    [filters.upfrontAmountMin, filters.upfrontAmountMax, "首付款"],
    [filters.totalPotentialAmountMin, filters.totalPotentialAmountMax, "潜在总额"],
  ];
  for (const [minimum, maximum, label] of amountRanges) {
    if ([minimum, maximum].some((value) => value.trim() && !validDealAmount(value)))
      return `${label}必须是有限的非负十进制金额`;
    if (minimum.trim() && maximum.trim() && Number(minimum) > Number(maximum)) return `${label}下限不能高于上限`;
  }
  if (amountRanges.some(([minimum, maximum]) => minimum.trim() || maximum.trim()) && !filters.currency.trim())
    return "按交易金额查询时必须选择币种";
  if (
    effectiveSort(filters.sort, filters.sortBy, filters.sortDirection).some((criterion) =>
      amountSortFields.has(criterion.field),
    ) &&
    !filters.currency.trim()
  )
    return "按交易金额排序时必须选择币种";
  const enumFilters: Array<[string, ReadonlySet<string>, string]> = [
    [filters.status, dealStatuses, "交易状态"],
    [filters.direction, dealDirections, "交易方向"],
    [filters.partyRole, partyRoles, "参与角色"],
    [filters.rightType, rightTypes, "权益类型"],
    [filters.developmentPhaseAtTransaction, developmentPhases, "交易时阶段"],
    [filters.currentDevelopmentPhase, developmentPhases, "当前最高阶段"],
  ];
  for (const [value, allowed, label] of enumFilters) {
    if (value && !allowed.has(value)) return `${label}包含不支持的筛选值`;
  }
  if (["inbound", "outbound"].includes(filters.direction) && !filters.directionReferenceJurisdiction.trim())
    return "引进或对外许可必须选择方向参照地区";
  return null;
}

export function assertValidDealSearchFilters(filters: DealSearchFilters): void {
  const error = validateDealSearchFilters(filters);
  if (error) throw new DealSearchValidationError(error);
}

/** Application-owned validation only; source/transport error prose stays literal. */
export class DealSearchValidationError extends Error {
  readonly name = "DealSearchValidationError";
}
