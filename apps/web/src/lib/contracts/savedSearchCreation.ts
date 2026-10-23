import { contractRequest } from "../contract";
import type { SavedSearchCreate } from "../generated";
import { MonitoringService } from "../generated";

export type SavedSearchCreationOutcome =
  | { kind: "saved"; monitoring: boolean }
  | { kind: "monitor_failed"; reason: string | null };

/** Shared two-step ownership: a failed subscription never causes a second save. */
export async function saveAndSubscribeSearch(
  requestBody: SavedSearchCreate,
  monitor: boolean,
): Promise<SavedSearchCreationOutcome> {
  const saved = await contractRequest(
    MonitoringService.createSavedSearchApiV1MonitoringSavedSearchesPost({ requestBody }),
  );
  if (monitor) {
    try {
      await contractRequest(
        MonitoringService.createMonitoringTopicApiV1MonitoringTopicsPost({
          requestBody: { name: requestBody.name, saved_search_id: saved.id },
        }),
      );
    } catch (error) {
      return { kind: "monitor_failed", reason: error instanceof Error ? error.message : null };
    }
  }
  return { kind: "saved", monitoring: monitor };
}
