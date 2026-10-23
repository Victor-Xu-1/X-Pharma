import type { PipelineSearchFilters } from "../../lib/contracts/pipeline";
import type { PipelineSearchResult } from "../../lib/generated";
export type UpdatePipelineFilter = <Key extends keyof PipelineSearchFilters>(
  key: Key,
  value: PipelineSearchFilters[Key],
) => void;
export interface PipelineFilterProps {
  filters: PipelineSearchFilters;
  updateFilter: UpdatePipelineFilter;
  data?: PipelineSearchResult;
}
