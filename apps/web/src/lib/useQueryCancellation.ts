import { hashKey, type QueryKey, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

export function useQueryCancellation(queryKey: QueryKey): {
  cancel: () => void;
  isCancelled: boolean;
  reset: () => void;
} {
  const queryClient = useQueryClient();
  const [cancelledQueryHash, setCancelledQueryHash] = useState<string | null>(null);
  const queryHash = hashKey(queryKey);

  const cancel = useCallback(() => {
    setCancelledQueryHash(queryHash);
    void queryClient.cancelQueries({ queryKey, exact: true });
  }, [queryClient, queryHash, queryKey]);
  const reset = useCallback(() => setCancelledQueryHash(null), []);
  return { cancel, isCancelled: cancelledQueryHash === queryHash, reset };
}
