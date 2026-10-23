import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { loadCollectionCatalog } from "../lib/contracts/collections";
import { useCollectionCatalog } from "../lib/useCollectionCatalog";

vi.mock("../lib/contracts/collections", () => ({
  collectionsKeys: { catalog: (q: string, offset: number) => ["collections", "catalog", q, offset] },
  loadCollectionCatalog: vi.fn(),
}));

type CatalogPage = Awaited<ReturnType<typeof loadCollectionCatalog>>;
let client: QueryClient | undefined;
afterEach(() => client?.clear());

it.each([0, 25])(
  "recovers a deferred out-of-range page only after its authoritative total %i arrives",
  async (total) => {
    let release!: (page: CatalogPage) => void;
    const deferred = new Promise<CatalogPage>((resolve) => {
      release = resolve;
    });
    let currentTotal = 70;
    vi.mocked(loadCollectionCatalog).mockImplementation(async (_q, offset) =>
      offset === 25 ? deferred : { items: [], total: currentTotal, limit: 25, offset },
    );
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const activeClient = client;
    const { result } = renderHook(() => useCollectionCatalog(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={activeClient}>{children}</QueryClientProvider>
      ),
    });
    await waitFor(() => expect(result.current.query.data?.total).toBe(70));
    act(() => result.current.changePage(25));
    await waitFor(() => expect(loadCollectionCatalog).toHaveBeenLastCalledWith("", 25, expect.any(AbortSignal)));
    expect(result.current.filter.offset).toBe(25);
    expect(result.current.query.isPending).toBe(true);
    expect(loadCollectionCatalog).toHaveBeenCalledTimes(2);

    // This response is explicitly controlled; no timeout, sleep, retry or business write.
    currentTotal = total;
    await act(async () => release({ items: [], total, limit: 25, offset: 25 }));
    await waitFor(() => expect(loadCollectionCatalog).toHaveBeenLastCalledWith("", 0, expect.any(AbortSignal)));
    await waitFor(() => expect(result.current.query.data).toEqual({ items: [], total, limit: 25, offset: 0 }));
    expect(result.current.filter).toEqual({ q: "", offset: 0 });
    expect(result.current.query.isFetching).toBe(false);
    expect(loadCollectionCatalog).toHaveBeenCalledTimes(3);
  },
);
