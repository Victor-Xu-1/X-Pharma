import { contractRequest } from "../contract";
import type { PublicKnowledgePageSummary, RecentEntityVisitRead } from "../generated";
import { EntitiesService, KnowledgeService, WorkspaceService } from "../generated";

export const overviewKeys = {
  snapshot: ["overview", "research"] as const,
};

export type OverviewSnapshot = {
  entityTotal: number;
  entityTypeCounts: Record<string, number>;
  reviewStatusCounts: Record<string, number>;
  pages: PublicKnowledgePageSummary[];
  recentEntities: RecentEntityVisitRead[];
};

export async function loadOverview(signal?: AbortSignal): Promise<OverviewSnapshot> {
  const [entities, pages, recentEntities] = await Promise.allSettled([
    contractRequest(EntitiesService.searchEntitiesApiV1EntitiesGet({ limit: 1 }), signal),
    contractRequest(KnowledgeService.listKnowledgePagesApiV1KnowledgePagesGet({ limit: 1000 }), signal),
    contractRequest(WorkspaceService.listRecentEntitiesApiV1WorkspaceRecentEntitiesGet({ limit: 8 }), signal),
  ]);
  if (entities.status === "rejected" || pages.status === "rejected" || recentEntities.status === "rejected") {
    throw new Error("核心情报指标暂不可用");
  }
  return {
    entityTotal: entities.value.total,
    entityTypeCounts: entities.value.facets?.entity_type ?? {},
    reviewStatusCounts: entities.value.facets?.review_status ?? {},
    pages: pages.value,
    recentEntities: recentEntities.value,
  };
}
