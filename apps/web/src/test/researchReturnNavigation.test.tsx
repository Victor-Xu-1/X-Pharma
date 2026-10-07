import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { getSessionEntity } from "../lib/contracts/session";
import { parseWorkbenchLocation, workspaceUrl } from "../lib/workspaceRouting";
import { ResearchReturnControl } from "../workspaces/research/ResearchReturnControl";
import { useResearchNavigation } from "../workspaces/research/useResearchNavigation";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/rum", () => ({ startResearchRum: async () => undefined }));
vi.mock("../lib/contracts/session", async (original) => ({
  ...(await original<typeof import("../lib/contracts/session")>()),
  getSessionEntity: vi.fn(async (id: string) => ({ id, name: "Selected", entity_type: "target" })),
}));

afterEach(() => window.history.replaceState(null, "", "/"));

const entityId = "550e8400-e29b-41d4-a716-446655440000";
const query =
  "/workspace/research?view=explorer&q=EGFR&type=target&sort=name%3Aasc&display=landscape&analysis_view=table&offset=100";

function ReturnHarness() {
  const navigation = useResearchNavigation();
  return (
    <ResearchReturnControl
      context={{
        ...navigation,
        user: { id: "user", tenant_id: "tenant", email: "user@example.test", display_name: "User", role: "viewer" },
        onLogout: vi.fn(),
        onUserUpdated: vi.fn(),
        logoutPending: false,
        logoutError: null,
      }}
    />
  );
}

it.each(["drug", "target", "company", "disease", "entity"])(
  "round-trips the exact source query and preview through a %s dossier",
  (view) => {
    const source = `${query}&entity=${entityId}`;
    const canonicalSource = workspaceUrl(
      parseWorkbenchLocation("research", new URL(source, window.location.origin).search),
    );
    const detail = parseWorkbenchLocation(
      "research",
      `?view=${view}&entity=${entityId}&from=${encodeURIComponent(source)}`,
    );
    expect(detail.returnTo).toBe(canonicalSource);
    expect(
      parseWorkbenchLocation("research", new URL(workspaceUrl(detail), window.location.origin).search).returnTo,
    ).toBe(canonicalSource);
  },
);

it("bounds nested return history without losing the immediate valid source", () => {
  let source = query;
  for (let index = 0; index < 6; index++) {
    source = `/workspace/research?view=target&entity=${entityId}&from=${encodeURIComponent(source)}`;
  }
  const detail = parseWorkbenchLocation("research", `?view=drug&entity=${entityId}&from=${encodeURIComponent(source)}`);
  let path = detail.returnTo;
  let depth = 0;
  while (path) {
    depth++;
    const parsed = parseWorkbenchLocation("research", new URL(path, window.location.origin).search);
    expect(parsed.view).toBe("target");
    path = parsed.returnTo;
  }
  expect(depth).toBe(3);
});

it.each([
  "https://evil.example/workspace/research?view=explorer",
  "//evil.example/workspace/research?view=explorer",
  "/workspace/internal?view=factory",
  "/workspace/research?view=factory",
  "/workspace/research?view=unknown",
  "/workspace/research?view=explorer&view=drug",
  "/workspace/research?view=target&entity=not-an-id",
  "/workspace/research?view=target",
  "/workspace/research?view=explorer#fragment",
  `/workspace/research?view=explorer&q=${"x".repeat(4_096)}`,
])("rejects an unsafe or malformed return path: %s", (source) => {
  const detail = parseWorkbenchLocation("research", `?view=drug&entity=${entityId}&from=${encodeURIComponent(source)}`);
  expect(detail.returnTo).toBeUndefined();
});

it("opens linked records with the applied query as their origin, not the unsaved input or browser referrer", async () => {
  window.history.replaceState(null, "", query);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  const { result } = renderHook(() => useResearchNavigation(), { wrapper: Wrapper });
  const source = workspaceUrl(result.current.location);
  act(() => result.current.openOrganizationById(entityId));
  await waitFor(() => expect(result.current.location.view).toBe("company"));
  expect(result.current.location.returnTo).toBe(source);
  const company = workspaceUrl(result.current.location);
  act(() => result.current.openTargetById(entityId));
  await waitFor(() => expect(result.current.location.view).toBe("target"));
  expect(result.current.location.returnTo).toBe(company);
});

it.each(["company", "drug", "target", "trials", "entity"])(
  "provides one source return outside the %s dossier's loading/error boundary",
  async (view) => {
    const source = `${query}&entity=${entityId}`;
    const canonical = workspaceUrl(parseWorkbenchLocation("research", new URL(source, window.location.origin).search));
    window.history.replaceState(
      null,
      "",
      `/workspace/research?view=${view}&entity=${entityId}&trial=${entityId}&from=${encodeURIComponent(source)}`,
    );
    renderWithQueryClient(<ReturnHarness />);
    fireEvent.click(await screen.findByRole("button", { name: "返回情报检索" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(canonical);
    expect(parseWorkbenchLocation("research", window.location.search).entityTypes).toEqual(["target"]);
    expect(screen.queryByRole("button", { name: "返回情报检索" })).not.toBeInTheDocument();
  },
);

it.each([
  { view: "drug", source: `?view=target&entity=${entityId}&section=pipeline`, label: "返回靶点竞品管线" },
  {
    view: "drug",
    source: "?view=target&entity=550e8400-e29b-41d4-a716-446655440001&section=pipeline",
    label: "返回靶点竞品管线",
  },
  { view: "drug", source: `?view=collections&collection=${entityId}`, label: "返回对比列表" },
  { view: "target", source: `?view=drug&entity=${entityId}&section=pipeline`, label: "返回药物档案" },
])(
  "restores the exact $label origin from $view without requiring its dossier data",
  async ({ view, source, label }) => {
    const canonical = workspaceUrl(parseWorkbenchLocation("research", source));
    window.history.replaceState(
      null,
      "",
      `/workspace/research?view=${view}&entity=${entityId}&from=${encodeURIComponent(canonical)}`,
    );
    renderWithQueryClient(<ReturnHarness />);
    expect(await screen.findAllByRole("button", { name: label })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(canonical);
  },
);

it("preserves the source while resolving a generic entity link into its specialized dossier", async () => {
  window.history.replaceState(null, "", query);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { result } = renderHook(() => useResearchNavigation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
  const source = workspaceUrl(result.current.location);
  act(() => result.current.openEntityById(entityId));
  await waitFor(() => expect(result.current.location.view).toBe("target"));
  expect(result.current.location.returnTo).toBe(source);
  expect(new URLSearchParams(window.location.search).get("from")).toBe(source);
});

it.each(["pipeline", "trials", "patents", "deals", "regulatory", "epidemiology", "news"])(
  "preserves the source for same-view %s filters but clears it for an explicit sidebar reset",
  async (view) => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    window.history.replaceState(null, "", `/workspace/research?view=${view}&from=${encodeURIComponent(query)}`);
    const { result } = renderHook(() => useResearchNavigation(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });
    const origin = result.current.location.returnTo;
    const next = parseWorkbenchLocation("research", `?view=${view}&q=updated&display=landscape&offset=100`);
    act(() => result.current.navigate(next));
    await waitFor(() => expect(result.current.location.query).toBe("updated"));
    expect(result.current.location.returnTo).toBe(origin);
    expect(new URLSearchParams(window.location.search).get("from")).toBe(origin);
    act(() => result.current.navigateToView(next.view));
    expect(result.current.location.returnTo).toBeUndefined();
    expect(new URLSearchParams(window.location.search).get("from")).toBeNull();
  },
);

it("recovers the same entity's failed dossier lookup when explicitly returning to its source preview", async () => {
  const recovered = { ...(await getSessionEntity(entityId)), name: "Recovered source entity" };
  vi.mocked(getSessionEntity).mockClear();
  vi.mocked(getSessionEntity).mockRejectedValueOnce(new Error("Controlled entity lookup failure"));
  vi.mocked(getSessionEntity).mockResolvedValueOnce(recovered);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const source = parseWorkbenchLocation(
    "research",
    new URL(`${query}&entity=${entityId}`, window.location.origin).search,
  );
  window.history.replaceState(
    null,
    "",
    `/workspace/research?view=target&entity=${entityId}&from=${encodeURIComponent(workspaceUrl(source))}`,
  );
  const { result } = renderHook(() => useResearchNavigation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
  await waitFor(() => expect(result.current.routeEntity.isError).toBe(true));
  act(() => result.current.navigate(source, true, true));
  await waitFor(() => expect(result.current.routeEntity.data?.name).toBe("Recovered source entity"));
  expect(getSessionEntity).toHaveBeenCalledTimes(2);
});

it("shares a successful entity read across dossier and preview navigation without another request", async () => {
  vi.mocked(getSessionEntity).mockClear();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  window.history.replaceState(null, "", `/workspace/research?view=target&entity=${entityId}`);
  const { result } = renderHook(() => useResearchNavigation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
  await waitFor(() => expect(result.current.routeEntity.isSuccess).toBe(true));
  const source = parseWorkbenchLocation(
    "research",
    new URL(`${query}&entity=${entityId}`, window.location.origin).search,
  );
  act(() => result.current.navigate(source, true, true));
  await waitFor(() => expect(result.current.location.view).toBe("explorer"));
  expect(result.current.routeEntity.isSuccess).toBe(true);
  expect(getSessionEntity).toHaveBeenCalledTimes(1);
});

it("reads the full preview even when a lightweight search hit with the same ID is selected", async () => {
  vi.mocked(getSessionEntity).mockClear();
  const full = {
    ...(await getSessionEntity(entityId)),
    aliases: Array.from({ length: 30 }, (_, index) => `CODE-${index}`),
  };
  vi.mocked(getSessionEntity).mockClear();
  vi.mocked(getSessionEntity).mockReset().mockResolvedValue(full);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  window.history.replaceState(null, "", "/workspace/research?view=explorer&q=EGFR");
  const { result } = renderHook(() => useResearchNavigation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
  act(() => {
    result.current.setSelectedEntity({ ...full, aliases: full.aliases.slice(0, 20) });
    result.current.navigate({ ...result.current.location, entityId }, true, true);
  });
  await waitFor(() => expect(result.current.routeEntity.data?.aliases).toHaveLength(30));
  expect(getSessionEntity).toHaveBeenCalledTimes(1);
});

it("does not turn an unsuccessful navigation recovery into an automatic retry loop", async () => {
  vi.mocked(getSessionEntity).mockClear();
  vi.mocked(getSessionEntity).mockRejectedValueOnce(new Error("Still unavailable"));
  vi.mocked(getSessionEntity).mockRejectedValueOnce(new Error("Still unavailable"));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  window.history.replaceState(null, "", `/workspace/research?view=target&entity=${entityId}`);
  const { result, rerender } = renderHook(() => useResearchNavigation(), {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
  await waitFor(() => expect(result.current.routeEntity.isError).toBe(true));
  const source = parseWorkbenchLocation(
    "research",
    new URL(`${query}&entity=${entityId}`, window.location.origin).search,
  );
  act(() => result.current.navigate(source, true, true));
  await waitFor(() => expect(getSessionEntity).toHaveBeenCalledTimes(2));
  await waitFor(() => expect(result.current.routeEntity.fetchStatus).toBe("idle"));
  rerender();
  expect(result.current.routeEntity.isError).toBe(true);
  expect(getSessionEntity).toHaveBeenCalledTimes(2);
});
