import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { getSessionEntity, sessionKeys } from "../../lib/contracts/session";
import type { WorkspaceLocation } from "../../lib/workspaceRouting";

const entityViews = new Set(["explorer", "target", "drug", "company", "disease", "entity"]);

export function useRouteEntity(location: WorkspaceLocation, selectedEntityId?: string) {
  const enabled = Boolean(
    entityViews.has(location.view) &&
      !location.invalidEntityId &&
      location.entityId &&
      (location.view === "explorer" || selectedEntityId !== location.entityId),
  );
  const navigationKey = `${location.view}:${location.entityId ?? ""}`;
  const previousNavigation = useRef(navigationKey);
  const query = useQuery({
    queryKey: sessionKeys.entity(location.entityId ?? ""),
    queryFn: ({ signal }) => getSessionEntity(location.entityId ?? "", signal),
    enabled,
  });

  useEffect(() => {
    const changed = previousNavigation.current !== navigationKey;
    previousNavigation.current = navigationKey;
    // Changing consumers does not remount this observer. Recover a failed read
    // once per explicit navigation, while keeping successful data shared.
    if (changed && enabled && query.isError && query.fetchStatus === "idle") void query.refetch();
  }, [enabled, navigationKey, query.fetchStatus, query.isError, query.refetch]);

  return query;
}
