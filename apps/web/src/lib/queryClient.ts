import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./api";
import { CancelError } from "./generated";

export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2 || error instanceof CancelError) return false;
  if (error instanceof DOMException && error.name === "AbortError") return false;
  if (error instanceof ApiError) return error.status === 408 || error.status === 429 || error.status >= 500;
  return failureCount < 1;
}

export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: shouldRetryQuery,
        retryDelay: (attempt) => Math.min(500 * 2 ** attempt, 4_000),
      },
      mutations: { retry: false },
    },
  });
}

export const appQueryClient = createAppQueryClient();
