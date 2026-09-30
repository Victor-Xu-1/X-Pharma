export const MAX_SORT_CRITERIA = 5;

export type SortDirection = "asc" | "desc";

export type SortCriterion<Field extends string = string> = {
  field: Field;
  direction: SortDirection;
};

export function effectiveSort<Field extends string>(
  sort: readonly SortCriterion<Field>[] | undefined,
  sortBy: Field,
  sortDirection: SortDirection,
): SortCriterion<Field>[] {
  if (!sort?.length) return [{ field: sortBy, direction: sortDirection }];
  if (sort[0]?.field !== sortBy || sort[0]?.direction !== sortDirection) {
    return [{ field: sortBy, direction: sortDirection }];
  }
  const bounded = sort.slice(0, MAX_SORT_CRITERIA);
  const fields = new Set<Field>();
  const normalized: SortCriterion<Field>[] = [];
  for (const criterion of bounded) {
    if (fields.has(criterion.field)) continue;
    fields.add(criterion.field);
    normalized.push({ field: criterion.field, direction: criterion.direction });
  }
  return normalized.length ? normalized : [{ field: sortBy, direction: sortDirection }];
}

export function appendSortParams<Field extends string>(
  params: URLSearchParams,
  sort: readonly SortCriterion<Field>[] | undefined,
  sortBy: Field,
  sortDirection: SortDirection,
) {
  for (const criterion of effectiveSort(sort, sortBy, sortDirection)) {
    params.append("sort", `${criterion.field}:${criterion.direction}`);
  }
}

export function sortCriteriaFromTable<Field extends string>(
  sorting: readonly { id: string; desc: boolean }[],
  fallback: SortCriterion<Field>,
): SortCriterion<Field>[] {
  const criteria = sorting.slice(0, MAX_SORT_CRITERIA).map((criterion) => ({
    field: criterion.id as Field,
    direction: criterion.desc ? ("desc" as const) : ("asc" as const),
  }));
  return criteria.length ? criteria : [fallback];
}

export function tableSortingFromCriteria<Field extends string>(
  sort: readonly SortCriterion<Field>[] | undefined,
  sortBy: Field,
  sortDirection: SortDirection,
) {
  return effectiveSort(sort, sortBy, sortDirection).map((criterion) => ({
    id: criterion.field,
    desc: criterion.direction === "desc",
  }));
}

export function parseSortTokens<Field extends string>(
  tokens: readonly string[],
  allowedFields: ReadonlySet<Field>,
  fallback: SortCriterion<Field>,
): SortCriterion<Field>[] {
  if (!tokens.length || tokens.length > MAX_SORT_CRITERIA) return [fallback];
  const fields = new Set<Field>();
  const parsed: SortCriterion<Field>[] = [];
  for (const token of tokens) {
    const match = /^([a-z][a-z0-9_]{0,63}):(asc|desc)$/.exec(token);
    const field = match?.[1] as Field | undefined;
    if (!match || !field || !allowedFields.has(field) || fields.has(field)) return [fallback];
    fields.add(field);
    parsed.push({ field, direction: match[2] as SortDirection });
  }
  return parsed;
}
