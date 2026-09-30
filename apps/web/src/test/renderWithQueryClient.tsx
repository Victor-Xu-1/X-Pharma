import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderOptions, type RenderResult, render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";

import { createAppQueryClient } from "../lib/queryClient";

export function renderWithQueryClient(
  element: ReactElement,
  options?: RenderOptions,
  configure?: (queryClient: QueryClient) => void,
): RenderResult & { queryClient: QueryClient } {
  const queryClient = createAppQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } });
  configure?.(queryClient);
  return {
    queryClient,
    ...render(element, {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
      ...options,
    }),
  };
}
