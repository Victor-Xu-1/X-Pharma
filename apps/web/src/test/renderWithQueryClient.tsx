import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderOptions, type RenderResult, render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { SessionIdentityContext } from "../components/SessionIdentityContext";
import { type SessionSnapshot, sessionKeys } from "../lib/contracts/session";
import { createAppQueryClient } from "../lib/queryClient";

export function renderWithQueryClient(
  element: ReactElement,
  options?: RenderOptions,
  configure?: (queryClient: QueryClient) => void,
): RenderResult & { queryClient: QueryClient } {
  const queryClient = createAppQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } });
  configure?.(queryClient);
  const identity = queryClient.getQueryData<SessionSnapshot>(sessionKeys.current)?.user ?? null;
  return {
    queryClient,
    ...render(element, {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>
          <SessionIdentityContext value={identity}>{children}</SessionIdentityContext>
        </QueryClientProvider>
      ),
      ...options,
    }),
  };
}
