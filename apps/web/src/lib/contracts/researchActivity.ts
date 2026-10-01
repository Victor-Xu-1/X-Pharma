import { contractRequest } from "../contract";
import { type RecentEntityVisitRead, WorkspaceService } from "../generated";

export const researchActivityKeys = { recent: ["research", "recent-entities"] as const };

export function loadRecentResearch(signal?: AbortSignal): Promise<RecentEntityVisitRead[]> {
  return contractRequest(WorkspaceService.listRecentEntitiesApiV1WorkspaceRecentEntitiesGet({ limit: 8 }), signal);
}
