import { contractRequest } from "../contract";
import type {
  EntitySearchQuery,
  MonitoringAlertRead,
  MonitoringTopicCreate,
  MonitoringTopicRead,
  SavedSearchRead,
} from "../generated";
import { MonitoringService } from "../generated";

export const monitoringKeys = {
  all: (unreadOnly: boolean) => ["monitoring", { unreadOnly }] as const,
  saved: (savedSearchId: string) => ["monitoring", "saved", savedSearchId] as const,
};

export type MonitoringSnapshot = {
  searches: SavedSearchRead[];
  topics: MonitoringTopicRead[];
  alerts: MonitoringAlertRead[];
};

export async function loadMonitoring(unreadOnly: boolean, signal?: AbortSignal): Promise<MonitoringSnapshot> {
  const [searches, topics, alerts] = await Promise.all([
    contractRequest(MonitoringService.listSavedSearchesApiV1MonitoringSavedSearchesGet(), signal),
    contractRequest(MonitoringService.listMonitoringTopicsApiV1MonitoringTopicsGet(), signal),
    contractRequest(MonitoringService.listMonitoringAlertsApiV1MonitoringAlertsGet({ unreadOnly }), signal),
  ]);
  return { searches, topics, alerts };
}

export function loadSavedSearch(savedSearchId: string, signal?: AbortSignal): Promise<SavedSearchRead> {
  return contractRequest(
    MonitoringService.getSavedSearchApiV1MonitoringSavedSearchesSavedSearchIdGet({ savedSearchId }),
    signal,
  );
}

export function createMonitoringTopic(requestBody: MonitoringTopicCreate): Promise<MonitoringTopicRead> {
  return contractRequest(MonitoringService.createMonitoringTopicApiV1MonitoringTopicsPost({ requestBody }));
}

export function setSavedSearchVisibility(
  savedSearchId: string,
  visibility: "private" | "tenant",
): Promise<SavedSearchRead> {
  return contractRequest(
    MonitoringService.updateSavedSearchApiV1MonitoringSavedSearchesSavedSearchIdPatch({
      savedSearchId,
      requestBody: { visibility },
    }),
  );
}

export function updateSavedSearchMetadata(
  savedSearchId: string,
  metadata: { name: string; description: string },
): Promise<SavedSearchRead> {
  return contractRequest(
    MonitoringService.updateSavedSearchApiV1MonitoringSavedSearchesSavedSearchIdPatch({
      savedSearchId,
      requestBody: metadata,
    }),
  );
}

export function setMonitoringTopicActive(topicId: string, active: boolean): Promise<MonitoringTopicRead> {
  return contractRequest(
    MonitoringService.updateMonitoringTopicApiV1MonitoringTopicsTopicIdPatch({ topicId, requestBody: { active } }),
  );
}

export function setMonitoringTopicQueryVersion(topicId: string, queryVersion: number): Promise<MonitoringTopicRead> {
  return contractRequest(
    MonitoringService.updateMonitoringTopicApiV1MonitoringTopicsTopicIdPatch({
      topicId,
      requestBody: { query_version: queryVersion },
    }),
  );
}

export function markMonitoringAlertRead(alertId: string): Promise<void> {
  return contractRequest(MonitoringService.markMonitoringAlertReadApiV1MonitoringAlertsAlertIdReadPost({ alertId }));
}

export type SavedSearch = SavedSearchRead;
export type MonitoringTopic = MonitoringTopicRead;
export type MonitoringAlert = MonitoringAlertRead;
export type SavedEntitySearch = EntitySearchQuery;
