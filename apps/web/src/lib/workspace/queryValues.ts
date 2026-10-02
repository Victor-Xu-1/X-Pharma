import { parseSortTokens, type SortCriterion, type SortDirection } from "../contracts/sorting";
import { entityIdPattern } from "./catalog";
export function boundedEvidenceDocumentId(value: string | null): string | null {
  const normalized = value?.trim() ?? "";
  const hasControlCharacter = Array.from(normalized).some((character) => {
    const codePoint = character.codePointAt(0) ?? 0;
    return codePoint < 32 || codePoint === 127;
  });
  if (!normalized || normalized.length > 240 || hasControlCharacter) return null;
  return normalized;
}

export function boundedTargetCombinationKey(value: string | null | undefined): string {
  if (!value) return "";
  const ids = value
    .split("|")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);
  if (!ids.length || ids.length > 20 || ids.some((item) => !entityIdPattern.test(item))) return "";
  const unique = Array.from(new Set(ids)).sort();
  return unique.length === ids.length ? unique.join("|") : "";
}
export function boundedIsoDate(value: string | null): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "";
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value ? "" : value;
}

export function boundedAmount(value: string | null): string {
  if (!value || !/^\d+(?:\.\d{1,2})?$/.test(value)) return "";
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 && parsed <= 1_000_000_000_000_000 ? value : "";
}

export function boundedEntityIdList(value: string | null, maximum = 4): string[] {
  if (!value) return [];
  return Array.from(
    new Set(
      value
        .split(",")
        .map((item) => item.trim().toLowerCase())
        .filter((item) => entityIdPattern.test(item)),
    ),
  ).slice(0, maximum);
}

export function boundedRepeatedValues(
  params: URLSearchParams,
  name: string,
  maxLength: number,
  maximum = 20,
): string[] {
  return Array.from(
    new Set(
      params
        .getAll(name)
        .map((item) => item.trim())
        .filter((item) => item.length > 0 && item.length <= maxLength),
    ),
  ).slice(0, maximum);
}

export function boundedRepeatedEntityIds(params: URLSearchParams, name: string, maximum = 20): string[] {
  return boundedRepeatedValues(params, name, 36, maximum)
    .map((item) => item.toLowerCase())
    .filter((item) => entityIdPattern.test(item))
    .sort();
}

export function locationSort(
  params: URLSearchParams,
  allowedFields: ReadonlySet<string>,
  defaultField: string,
  defaultDirection: SortDirection = "desc",
): SortCriterion[] {
  const legacyField = params.get("sort_by");
  const fallback = {
    field: legacyField && allowedFields.has(legacyField) ? legacyField : defaultField,
    direction: params.get("sort_direction") === "asc" ? ("asc" as const) : defaultDirection,
  };
  return parseSortTokens(params.getAll("sort"), allowedFields, fallback);
}

export function appendLocationSort(
  params: URLSearchParams,
  sort: readonly SortCriterion[] | undefined,
  allowedFields: ReadonlySet<string>,
  legacyField: string | undefined,
  legacyDirection: SortDirection | undefined,
  defaultField: string,
  defaultDirection: SortDirection = "desc",
) {
  const fallback = {
    field: legacyField && allowedFields.has(legacyField) ? legacyField : defaultField,
    direction: legacyDirection ?? defaultDirection,
  };
  const tokens = (sort ?? []).map((criterion) => `${criterion.field}:${criterion.direction}`);
  const criteria = parseSortTokens(tokens, allowedFields, fallback);
  if (criteria.length === 1 && criteria[0]?.field === defaultField && criteria[0]?.direction === defaultDirection)
    return;
  for (const criterion of criteria) {
    params.append("sort", `${criterion.field}:${criterion.direction}`);
  }
}
