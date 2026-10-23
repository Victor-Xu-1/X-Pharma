import type { SortingState } from "@tanstack/react-table";

export function normalizeSortingState(sorting: SortingState): SortingState {
  const seen = new Set<string>();
  return sorting.filter((criterion) => {
    if (!criterion.id || seen.has(criterion.id) || seen.size >= 5) return false;
    seen.add(criterion.id);
    return true;
  });
}
