import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { InternalApp } from "../InternalApp";
import { emptyPipelineSearchFilters, type PipelineSearchFilters } from "../lib/contracts/pipeline";
import { ResearchApp } from "../ResearchApp";
import { renderWithQueryClient } from "./renderWithQueryClient";

const targetViewHarness = vi.hoisted(() => ({
  onPipelineSearchChange: null as ((filters: PipelineSearchFilters) => void) | null,
  onOpenTrial: null as ((trialId: string) => void) | null,
}));

const pipelineViewHarness = vi.hoisted(() => ({
  onOpenDrug: null as ((entityId: string) => void) | null,
}));

vi.mock("../views/TargetView", () => ({
  TargetView: ({
    onPipelineSearchChange,
    onOpenTrial,
  }: {
    onPipelineSearchChange?: (filters: PipelineSearchFilters) => void;
    onOpenTrial?: (trialId: string) => void;
  }) => {
    targetViewHarness.onPipelineSearchChange = onPipelineSearchChange ?? null;
    targetViewHarness.onOpenTrial = onOpenTrial ?? null;
    return <div data-testid="target-view-harness" />;
  },
}));

vi.mock("../views/PipelineView", () => ({
  PipelineView: ({ onOpenDrug }: { onOpenDrug: (entityId: string) => void }) => {
    pipelineViewHarness.onOpenDrug = onOpenDrug;
    return (
      <button type="button" onClick={() => onOpenDrug("660e8400-e29b-41d4-a716-446655440000")}>
        打开测试药物档案
      </button>
    );
  },
}));

vi.mock("../views/DrugView", () => ({
  DrugView: () => <div>测试药物档案</div>,
}));

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

function unauthenticatedResponse(input: RequestInfo | URL, mode: "local" | "oidc" = "local") {
  return String(input).endsWith("/api/v1/auth/config")
    ? new Response(JSON.stringify({ mode }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    : new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
}

function mockAuthenticated(
  role: "admin" | "analyst" | "viewer" = "admin",
  savedSearches: unknown[] = [],
  sessionState: { valid: boolean } = { valid: true },
) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = String(input);
    const appliedFilters = [...new URL(path, "http://localhost").searchParams.entries()]
      .filter(([field]) => !["limit", "offset", "sort"].includes(field))
      .map(([field, value]) => ({ field, operator: "eq", value }));
    if (path.endsWith("/api/v1/auth/config")) {
      return new Response(JSON.stringify({ mode: "local" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (path.endsWith("/api/v1/auth/me")) {
      if (!sessionState.valid) return unauthenticatedResponse(input);
      return new Response(
        JSON.stringify({
          id: `${role}-1`,
          tenant_id: "tenant-1",
          email: `${role}@example.test`,
          display_name: role === "admin" ? "Admin" : role === "analyst" ? "Analyst" : "Viewer",
          role,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.endsWith("/api/v1/monitoring/saved-searches")) {
      return new Response(JSON.stringify(savedSearches), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (path.endsWith("/api/v1/admin/ingestion-capabilities")) {
      return new Response(
        JSON.stringify({
          automatic_scheduling_enabled: true,
          durable_workflows_enabled: true,
          isolated_parser_enabled: true,
          malware_scanning_enabled: true,
          ai_governance_enabled: false,
          ai_model_configured: false,
          ai_model: null,
          ai_auto_publish_threshold: 0.95,
          allowed_folder_roots: ["/sources/knowledge"],
          parseable_extensions: [".pdf"],
          asset_only_extensions: [".cdx"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.includes("/api/v1/entities?")) {
      return new Response(
        JSON.stringify({ items: [], total: 0, limit: 1, offset: 0, facets: {}, suggestions: [], engine: "opensearch" }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.includes("/api/v1/trials")) {
      return new Response(
        JSON.stringify({
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          facets: {},
          as_of: "2026-07-22T10:00:00Z",
          applied_filters: appliedFilters,
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.includes("/api/v1/patent-families")) {
      return new Response(
        JSON.stringify({
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          facets: {},
          as_of: "2026-07-22T10:00:00Z",
          applied_filters: appliedFilters,
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.includes("/api/v1/deal-transactions")) {
      return new Response(
        JSON.stringify({
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          facets: {},
          as_of: "2026-07-22T10:00:00Z",
          applied_filters: appliedFilters,
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.includes("/api/v1/regulatory-event-timeline")) {
      return new Response(
        JSON.stringify({
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          facets: {},
          as_of: "2026-07-22T10:00:00Z",
          applied_filters: appliedFilters,
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.includes("/api/v1/epidemiology-observations")) {
      return new Response(
        JSON.stringify({
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          facets: {},
          as_of: "2026-07-22T10:00:00Z",
          applied_filters: appliedFilters,
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.includes("/api/v1/news-events")) {
      return new Response(
        JSON.stringify({
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          facets: {},
          as_of: "2026-07-22T10:00:00Z",
          applied_filters: appliedFilters,
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

it("renders the external research login from the research application only", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => unauthenticatedResponse(input));
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "医药情报工作台" })).toBeInTheDocument();
  expect(screen.getByLabelText("X-Pharma")).toBeInTheDocument();
  expect(screen.queryByLabelText("X-Pharma Operations")).not.toBeInTheDocument();
});

it("renders the internal login from the internal application only", async () => {
  window.history.replaceState(null, "", "/workspace/internal");
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => unauthenticatedResponse(input));
  renderWithQueryClient(<InternalApp />);

  expect(await screen.findByRole("heading", { name: "内部管理工作台" })).toBeInTheDocument();
  expect(screen.getByLabelText("内部管理平台")).toBeInTheDocument();
  expect(screen.queryByLabelText("X-Pharma")).not.toBeInTheDocument();
});

it("shows only the enterprise identity action in OIDC mode", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => unauthenticatedResponse(input, "oidc"));
  renderWithQueryClient(<ResearchApp />);

  const login = await screen.findByRole("link", { name: "使用企业身份登录" });
  expect(login).toHaveAttribute("href", "/api/v1/auth/oidc/login");
  expect(screen.queryByLabelText("密码")).not.toBeInTheDocument();
});

it("shows a recoverable session failure", async () => {
  let recovered = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    if (String(input).endsWith("/api/v1/auth/config")) {
      return recovered
        ? new Response(JSON.stringify({ mode: "local" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify({ detail: "Identity service unavailable" }), {
            status: 503,
            headers: { "Content-Type": "application/json" },
          });
    }
    return new Response(JSON.stringify({ detail: "Authentication required" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  });

  renderWithQueryClient(<ResearchApp />);
  expect(await screen.findByText("Identity service unavailable", {}, { timeout: 4_000 })).toBeInTheDocument();
  recovered = true;
  screen.getByRole("button", { name: "重试" }).click();
  expect(await screen.findByRole("heading", { name: "账户登录" })).toBeInTheDocument();
});

it("rejects a viewer at the internal application boundary without protected API calls", async () => {
  window.history.replaceState(null, "", "/workspace/internal?view=governance");
  const fetchMock = mockAuthenticated("viewer");
  renderWithQueryClient(<InternalApp />);

  expect(await screen.findByText("无权访问该工作区")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "退出账号" })).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/admin/"))).toBe(false);
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/governance/"))).toBe(false);
});

it("clears tenant-scoped query data when the authenticated session is rejected", async () => {
  const sessionState = { valid: true };
  mockAuthenticated("admin", [], sessionState);
  const { queryClient } = renderWithQueryClient(<ResearchApp />);
  expect(await screen.findByRole("heading", { name: "全局情报检索" })).toBeInTheDocument();
  queryClient.setQueryData(["tenant-sensitive", "tenant-1"], { secret: "cached" });
  sessionState.valid = false;

  act(() => window.dispatchEvent(new CustomEvent("pharma:unauthorized")));

  expect(await screen.findByRole("heading", { name: "医药情报工作台" })).toBeInTheDocument();
  expect(queryClient.getQueryData(["tenant-sensitive", "tenant-1"])).toBeUndefined();
  expect(queryClient.getQueryData(["session", "current"])).toEqual({ mode: "local", user: null });
});

it("keeps the authenticated workspace when a stale unauthorized response is disproved", async () => {
  const fetchMock = mockAuthenticated("admin");
  const { queryClient } = renderWithQueryClient(<ResearchApp />);
  expect(await screen.findByRole("heading", { name: "全局情报检索" })).toBeInTheDocument();
  queryClient.setQueryData(["tenant-sensitive", "tenant-1"], { secret: "cached" });

  act(() => window.dispatchEvent(new CustomEvent("pharma:unauthorized")));

  await waitFor(() => {
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/api/v1/auth/me")).length).toBeGreaterThan(
      1,
    );
  });
  expect(screen.getByRole("heading", { name: "全局情报检索" })).toBeInTheDocument();
  expect(queryClient.getQueryData(["tenant-sensitive", "tenant-1"])).toEqual({ secret: "cached" });
});

it("fails closed when an entry receives a view owned by the other workbench", async () => {
  window.history.replaceState(null, "", "/?view=factory");
  mockAuthenticated("admin");
  const research = renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "全局情报检索" })).toBeInTheDocument();
  await waitFor(() => expect(window.location.pathname).toBe("/workspace/research"));
  expect(screen.queryByRole("button", { name: "数据工厂" })).not.toBeInTheDocument();
  research.unmount();

  window.history.replaceState(null, "", "/workspace/internal?view=explorer");
  renderWithQueryClient(<InternalApp />);
  expect(await screen.findByRole("heading", { name: "自动数据工厂" })).toBeInTheDocument();
  await waitFor(() => expect(window.location.pathname).toBe("/workspace/internal"));
  expect(screen.queryByRole("button", { name: "情报检索" })).not.toBeInTheDocument();
});

it("commits cross-domain navigation before rendering the new research domain", async () => {
  window.history.replaceState(null, "", "/workspace/research?view=overview");
  mockAuthenticated("admin");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "用户中心" })).toBeInTheDocument();
  const searchButton = screen.getByRole("button", { name: "情报检索" });
  act(() => searchButton.click());

  expect(searchButton).toHaveAttribute("aria-current", "page");
  expect(await screen.findByRole("heading", { name: "全局情报检索" })).toBeInTheDocument();
});

it("commits same-view navigation before accepting a new draft query", async () => {
  window.history.replaceState(null, "", "/workspace/research?view=explorer&q=EGFR");
  mockAuthenticated("admin");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "全局情报检索" })).toBeInTheDocument();
  act(() => screen.getByRole("button", { name: "情报检索" }).click());

  const input = await screen.findByLabelText("情报检索词");
  fireEvent.change(input, { target: { value: "BRAF" } });
  expect(screen.getByRole("button", { name: "检索" })).toBeEnabled();
});

it("replaces target pipeline filter history while keeping the final filter shareable", async () => {
  const targetId = "7316322c-e7a6-4514-9704-ff15b1e8a922";
  window.history.replaceState(null, "", `/workspace/research?view=target&entity=${targetId}&section=pipeline`);
  mockAuthenticated("viewer");
  const pushState = vi.spyOn(window.history, "pushState");
  const replaceState = vi.spyOn(window.history, "replaceState");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByTestId("target-view-harness")).toBeInTheDocument();
  pushState.mockClear();
  replaceState.mockClear();

  for (const query of ["D", "DA", "DAC"]) {
    act(() => {
      targetViewHarness.onPipelineSearchChange?.({
        ...emptyPipelineSearchFilters(),
        targetEntityId: targetId,
        query,
      });
    });
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("q")).toBe(query));
  }

  expect(pushState).not.toHaveBeenCalled();
  expect(replaceState).toHaveBeenCalledTimes(3);
  expect(window.location.search).toContain("q=DAC");
});

it("returns a drug dossier to the exact originating pipeline query", async () => {
  const targetId = "550e8400-e29b-41d4-a716-446655440000";
  const pipelinePath = `/workspace/research?view=pipeline&q=EGFR&target_entity_id=${targetId}&offset=20`;
  window.history.replaceState(null, "", pipelinePath);
  mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  fireEvent.click(await screen.findByRole("button", { name: "打开测试药物档案" }));
  await waitFor(() => expect(new URLSearchParams(window.location.search).get("view")).toBe("drug"));
  expect(new URLSearchParams(window.location.search).get("from")).toBe(pipelinePath);

  const returnButton = await screen.findByRole("button", { name: "返回管线查询" });
  expect(screen.getAllByRole("button", { name: "返回管线查询" })).toHaveLength(1);
  fireEvent.click(returnButton);
  await waitFor(() => expect(window.location.pathname + window.location.search).toBe(pipelinePath));
});

it("returns a target deep link to its originating drug dossier", async () => {
  const targetId = "7316322c-e7a6-4514-9704-ff15b1e8a922";
  const drugPath = "/workspace/research?view=drug&entity=17049b10-c0c8-403b-ad4f-089ab6f48e43&section=relationships";
  window.history.replaceState(
    null,
    "",
    `/workspace/research?view=target&entity=${targetId}&from=${encodeURIComponent(drugPath)}`,
  );
  mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByTestId("target-view-harness")).toBeInTheDocument();
  const returnButton = screen.getByRole("button", { name: "返回药物档案" });
  expect(screen.getAllByRole("button", { name: "返回药物档案" })).toHaveLength(1);
  expect(screen.getByTestId("target-view-harness")).not.toContainElement(returnButton);
  fireEvent.click(returnButton);

  await waitFor(() => expect(window.location.pathname + window.location.search).toBe(drugPath));
});

it("keeps the originating target dossier when opening an associated trial", async () => {
  const targetId = "7316322c-e7a6-4514-9704-ff15b1e8a922";
  const trialId = "1c9bef8a-7733-4470-a85f-ff8b72d1eff1";
  const targetPath = `/workspace/research?view=target&q=EGFR&entity=${targetId}&section=trials`;
  window.history.replaceState(null, "", targetPath);
  mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByTestId("target-view-harness")).toBeInTheDocument();
  act(() => targetViewHarness.onOpenTrial?.(trialId));

  await waitFor(() => expect(new URLSearchParams(window.location.search).get("trial")).toBe(trialId));
  expect(new URLSearchParams(window.location.search).get("from")).toBe(targetPath);
});

it("loads the clinical-trial workbench directly from its stable research URL", async () => {
  window.history.replaceState(null, "", "/workspace/research?view=trials&q=EGFR&phase=PHASE2");
  const fetchMock = mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "临床试验与结果", level: 1 })).toBeInTheDocument();
  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/trials"))).toBe(true);
  expect(window.location.search).toBe("?view=trials&q=EGFR&phase=PHASE2");
});

it("loads the patent workbench directly from its stable research URL", async () => {
  window.history.replaceState(
    null,
    "",
    "/workspace/research?view=patents&q=EGFR&applicant=Victor%20Therapeutics&legal_status=ACTIVE",
  );
  const fetchMock = mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "专利族与资产关联", level: 1 })).toBeInTheDocument();
  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/patent-families"))).toBe(true);
  expect(window.location.search).toBe("?view=patents&q=EGFR&applicant=Victor+Therapeutics&legal_status=ACTIVE");
});

it("loads the deals workbench directly from its stable research URL", async () => {
  window.history.replaceState(
    null,
    "",
    "/workspace/research?view=deals&q=VX-101&deal_type=license&territory=global&party=Acme%20Pharma",
  );
  const fetchMock = mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "交易、参与方与资产关联", level: 1 })).toBeInTheDocument();
  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/deal-transactions"))).toBe(true);
  expect(window.location.search).toBe("?view=deals&q=VX-101&deal_type=license&territory=global&party=Acme+Pharma");
});

it("loads the regulatory workbench directly from its stable research URL", async () => {
  window.history.replaceState(
    null,
    "",
    "/workspace/research?view=regulatory&q=VX-101&agency=FDA&jurisdiction=US&event_type=approval&status=approved",
  );
  const fetchMock = mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "监管事件与安全时间线", level: 1 })).toBeInTheDocument();
  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/regulatory-event-timeline"))).toBe(
    true,
  );
  expect(window.location.search).toBe(
    "?view=regulatory&q=VX-101&agency=FDA&jurisdiction=US&event_type=approval&status=approved",
  );
});

it("loads the epidemiology workbench directly from its stable research URL", async () => {
  window.history.replaceState(
    null,
    "",
    "/workspace/research?view=epidemiology&q=NSCLC&measure=prevalence&geography=China&unit=patients" +
      "&population_scope=adults&age_group=18%2B&sex=all" +
      "&period_start_from=2024-01-01&period_end_to=2025-12-31",
  );
  const fetchMock = mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "流行病学与疾病负担", level: 1 })).toBeInTheDocument();
  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/epidemiology-observations"))).toBe(
    true,
  );
  expect(window.location.search).toBe(
    "?view=epidemiology&q=NSCLC&measure=prevalence&geography=China&unit=patients" +
      "&population_scope=adults&age_group=18%2B&sex=all" +
      "&period_start_from=2024-01-01&period_end_to=2025-12-31",
  );
});

it("loads the news workbench directly from its stable research URL", async () => {
  window.history.replaceState(
    null,
    "",
    "/workspace/research?view=news&q=Compound%20A&event_type=corporate_announcement&publisher=Acme%20Pharma" +
      "&language=en&venue=ASCO%202026&published_from=2026-01-01&published_to=2026-12-31",
  );
  const fetchMock = mockAuthenticated("viewer");
  renderWithQueryClient(<ResearchApp />);

  expect(await screen.findByRole("heading", { name: "新闻、公告与会议动态", level: 1 })).toBeInTheDocument();
  expect(await screen.findByText("未找到匹配记录")).toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/api/v1/news-events"))).toBe(true);
  expect(window.location.search).toBe(
    "?view=news&q=Compound+A&event_type=corporate_announcement&publisher=Acme+Pharma" +
      "&language=en&venue=ASCO+2026&published_from=2026-01-01&published_to=2026-12-31",
  );
});

it("replays ordered multi-sort from a saved search into the stable URL and domain request", async () => {
  window.history.replaceState(null, "", "/workspace/research?view=monitoring");
  const fetchMock = mockAuthenticated("viewer", [
    {
      id: "saved-news-multi-sort",
      owner_user_id: "viewer-1",
      name: "EGFR event priority",
      description: "Event type then title",
      query_type: "news_search",
      query_version: 2,
      query_json: {
        q: "EGFR",
        sort_by: "event_type",
        sort_direction: "asc",
        sort: ["event_type:asc", "title:desc"],
      },
      visibility: "private",
      created_at: "2026-07-28T00:00:00Z",
      updated_at: "2026-07-28T00:00:00Z",
    },
  ]);
  renderWithQueryClient(<ResearchApp />);

  (await screen.findByRole("tab", { name: "已保存检索" })).click();
  (await screen.findByRole("button", { name: "运行 EGFR event priority" })).click();

  expect(await screen.findByRole("heading", { name: "新闻、公告与会议动态", level: 1 })).toBeInTheDocument();
  await waitFor(() => {
    const params = new URLSearchParams(window.location.search);
    expect(params.get("view")).toBe("news");
    expect(params.get("q")).toBe("EGFR");
    expect(params.getAll("sort")).toEqual(["event_type:asc", "title:desc"]);
  });
  const newsRequest = fetchMock.mock.calls.find(([input]) => String(input).includes("/api/v1/news-events?"));
  expect(newsRequest).toBeDefined();
  const requestUrl = new URL(String(newsRequest?.[0]), window.location.origin);
  expect(requestUrl.searchParams.getAll("sort")).toEqual(["event_type:asc", "title:desc"]);
});
