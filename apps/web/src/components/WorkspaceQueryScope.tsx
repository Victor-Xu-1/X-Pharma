import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useLayoutEffect, useState } from "react";

import { createAppQueryClient } from "../lib/queryClient";

export function WorkspaceQueryScope({
  parent,
  onClient,
  children,
}: {
  parent: QueryClient;
  onClient: (client: QueryClient | null) => void;
  children: ReactNode;
}) {
  const [client] = useState(() => {
    const scoped = createAppQueryClient();
    scoped.setDefaultOptions(parent.getDefaultOptions());
    return scoped;
  });
  useLayoutEffect(() => {
    onClient(client);
    return () => {
      onClient(null);
      void client.cancelQueries();
      client.clear();
    };
  }, [client, onClient]);
  // Late callbacks from an old organization can mutate only the old client.
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
