import { type QueryClient, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useMemo } from "react";

import {
  saveWorkspaceTablePreference,
  type WorkspaceTablePreferenceKey,
  type WorkspaceTablePreferences,
  workspacePreferenceKeys,
} from "../../lib/contracts/workspacePreferences";
import { captureOrganizationSession } from "../../lib/organizationSession";

type PreferenceWrite = { expectedVersion: number; preferences: WorkspaceTablePreferences };
type CapturedWrite = PreferenceWrite & {
  preferenceKey: WorkspaceTablePreferenceKey;
  queryKey: ReturnType<typeof workspacePreferenceKeys.table>;
  queryClient: QueryClient;
  isCurrent: () => boolean;
  sessionCurrent: () => boolean;
};

/** Submission owns the key, client, payload and lifecycle, including queued writes. */
export function useTablePreferenceMutation(ownerScope: string, preferenceKey: WorkspaceTablePreferenceKey) {
  const queryClient = useQueryClient();
  const scope = useMemo(
    () => ({
      mounted: false,
      generation: 0,
      queryClient,
      queryKey: workspacePreferenceKeys.table(ownerScope, preferenceKey),
    }),
    [ownerScope, preferenceKey, queryClient],
  );
  const mutation = useMutation({
    retry: false,
    mutationFn: (intent: CapturedWrite) =>
      saveWorkspaceTablePreference(intent.preferenceKey, intent.preferences, intent.expectedVersion, intent.isCurrent),
    onSuccess: (snapshot, intent) => {
      if (intent.isCurrent()) intent.queryClient.setQueryData(intent.queryKey, snapshot);
    },
    onSettled: (_snapshot, _error, intent) => {
      // The server may have accepted a write before the table was replaced by
      // query loading. Reconcile only its exact active key in the same session.
      if (!intent.isCurrent() && intent.sessionCurrent()) {
        return intent.queryClient.invalidateQueries({ queryKey: intent.queryKey, exact: true, refetchType: "active" });
      }
    },
  });
  const reset = mutation.reset;
  useLayoutEffect(() => {
    scope.mounted = true;
    scope.generation += 1;
    reset();
    return () => {
      scope.mounted = false;
      scope.generation += 1;
    };
  }, [scope, reset]);

  function captureCurrent() {
    const generation = scope.generation;
    const sessionCurrent = captureOrganizationSession();
    return () => scope.mounted && scope.generation === generation && sessionCurrent();
  }
  function capture(write: PreferenceWrite): CapturedWrite {
    return {
      expectedVersion: write.expectedVersion,
      preferences: {
        columnOrder: [...write.preferences.columnOrder],
        columnVisibility: { ...write.preferences.columnVisibility },
        density: write.preferences.density,
      },
      preferenceKey,
      queryKey: scope.queryKey,
      queryClient,
      isCurrent: captureCurrent(),
      sessionCurrent: captureOrganizationSession(),
    };
  }
  return {
    ...mutation,
    captureCurrent,
    mutate: (write: PreferenceWrite) => mutation.mutate(capture(write)),
    mutateAsync: (write: PreferenceWrite) => mutation.mutateAsync(capture(write)),
  };
}
