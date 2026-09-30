import { contractRequest } from "../contract";
import type {
  ChemistrySavedSearchQuery,
  ChemistrySearchHitRead,
  ChemistrySearchRead,
  ChemistrySearchRequest,
  SavedSearchRead,
} from "../generated";
import { MonitoringService, StructuresService } from "../generated";

export const chemistryKeys = {
  search: (request: ChemistrySearchRequest | null) => ["chemistry", "search", request] as const,
};

export function searchChemistry(request: ChemistrySearchRequest, signal?: AbortSignal): Promise<ChemistrySearchRead> {
  return contractRequest(
    StructuresService.searchChemistryApiV1ChemistrySearchPost({
      requestBody: { ...request, query: request.query.trim() },
    }),
    signal,
  );
}

export type ChemistrySearchMode = ChemistrySearchRequest["mode"];
export type ChemistrySearchResult = ChemistrySearchRead;
export type ChemistrySearchHit = ChemistrySearchHitRead;
export type ChemistrySearchInput = ChemistrySavedSearchQuery;

export function saveChemistrySearch({
  name,
  input,
  shared,
}: {
  name: string;
  input: ChemistrySearchInput;
  shared: boolean;
}): Promise<SavedSearchRead> {
  return contractRequest(
    MonitoringService.createSavedSearchApiV1MonitoringSavedSearchesPost({
      requestBody: {
        name: name.trim(),
        query_type: "chemistry_search",
        query: input,
        visibility: shared ? "tenant" : "private",
      },
    }),
  );
}
