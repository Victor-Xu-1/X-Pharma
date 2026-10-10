import { useSyncExternalStore } from "react";
import { hasPendingSessionWrites, subscribeSessionWrites } from "../../lib/organizationSession";

/** Observes the existing session write counter, not a second request authority. */
export function useSessionWritePending() {
  return useSyncExternalStore(subscribeSessionWrites, hasPendingSessionWrites, () => false);
}
