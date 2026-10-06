import { contractRequest } from "../contract";
import type {
  PublicKnowledgePageCoverageRead,
  PublicKnowledgePageDetail,
  PublicKnowledgePageSearchResult,
  PublicKnowledgePageSummary,
  PublicKnowledgeVersionDiffRead,
  PublicKnowledgeVersionSummaryRead,
} from "../generated";
import { KnowledgeService } from "../generated";

export const knowledgeKeys = {
  pages: (filters: KnowledgeSearchFilters) => ["knowledge", "pages", filters] as const,
  detail: (pageId: string) => ["knowledge", "pages", pageId] as const,
  coverage: (pageId: string) => ["knowledge", "pages", pageId, "coverage"] as const,
  versions: (pageId: string) => ["knowledge", "pages", pageId, "versions"] as const,
  diff: (pageId: string, versionNumber: number) =>
    ["knowledge", "pages", pageId, "versions", versionNumber, "diff"] as const,
};

export const KNOWLEDGE_PAGE_SIZE = 50;
export type KnowledgeSearchFilters = {
  query: string;
  offset: number;
  pageType: string;
  sortBy: "title" | "updated_at";
  sortDirection: "asc" | "desc";
};

export function searchKnowledgePages(
  filters: KnowledgeSearchFilters,
  signal?: AbortSignal,
): Promise<PublicKnowledgePageSearchResult> {
  return contractRequest(
    KnowledgeService.searchKnowledgePagesApiV1KnowledgePagesSearchGet({
      q: filters.query.trim() || undefined,
      pageType: filters.pageType || undefined,
      limit: KNOWLEDGE_PAGE_SIZE,
      offset: filters.offset,
      sortBy: filters.sortBy,
      sortDirection: filters.sortDirection,
    }),
    signal,
  );
}

export function getKnowledgePage(pageId: string, signal?: AbortSignal): Promise<PublicKnowledgePageDetail> {
  return contractRequest(KnowledgeService.getKnowledgePageApiV1KnowledgePagesPageIdGet({ pageId }), signal);
}

export function getKnowledgePageCoverage(
  pageId: string,
  signal?: AbortSignal,
): Promise<PublicKnowledgePageCoverageRead> {
  return contractRequest(
    KnowledgeService.getKnowledgePageCoverageApiV1KnowledgePagesPageIdCoverageGet({ pageId }),
    signal,
  );
}

export function listKnowledgePageVersions(
  pageId: string,
  signal?: AbortSignal,
): Promise<PublicKnowledgeVersionSummaryRead[]> {
  return contractRequest(
    KnowledgeService.listKnowledgePageVersionsApiV1KnowledgePagesPageIdVersionsGet({ pageId, limit: 50 }),
    signal,
  );
}

export function getKnowledgePageVersionDiff(
  pageId: string,
  versionNumber: number,
  signal?: AbortSignal,
): Promise<PublicKnowledgeVersionDiffRead> {
  return contractRequest(
    KnowledgeService.getKnowledgePageVersionDiffApiV1KnowledgePagesPageIdVersionsVersionNumberDiffGet({
      pageId,
      versionNumber,
    }),
    signal,
  );
}

export type KnowledgePage = PublicKnowledgePageSummary;
export type KnowledgeSearchResult = PublicKnowledgePageSearchResult;
export type KnowledgeDetail = PublicKnowledgePageDetail;
export type KnowledgeCoverage = PublicKnowledgePageCoverageRead;
export type KnowledgeVersion = PublicKnowledgeVersionSummaryRead;
export type KnowledgeVersionDiff = PublicKnowledgeVersionDiffRead;
