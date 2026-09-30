import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { loadNewsEventDetail, type NewsSearchFilters, saveNewsSearch, searchNewsEvents } from "../lib/contracts/news";
import { loadRecordProvenance } from "../lib/contracts/provenance";
import { NewsView } from "../views/NewsView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/news", async () => {
  const actual = await vi.importActual<typeof import("../lib/contracts/news")>("../lib/contracts/news");
  return {
    ...actual,
    newsKeys: {
      search: (filters: NewsSearchFilters, offset: number) => ["news", filters, offset],
      detail: (eventId: string) => ["news", "detail", eventId],
    },
    loadNewsEventDetail: vi.fn(),
    searchNewsEvents: vi.fn(),
    saveNewsSearch: vi.fn(),
  };
});

vi.mock("../lib/contracts/provenance", async (importOriginal) => {
  const original = await importOriginal<typeof import("../lib/contracts/provenance")>();
  return { ...original, loadRecordProvenance: vi.fn() };
});

const initialFilters: NewsSearchFilters = {
  query: "Compound A",
  entityId: "",
  eventType: "",
  publisher: "",
  language: "",
  venue: "",
  publishedFrom: "",
  publishedTo: "",
  contentScope: "",
  displayMode: "list",
  analysisView: "chart",
  sortBy: "published_at",
  sortDirection: "desc",
};

const newsResult = {
  items: [
    {
      id: "news-1",
      event_identifier: "ACME-ASCO-2026",
      event_type: "corporate_announcement",
      title: "Acme reports positive Phase 2 data for Compound A",
      summary: "The study met its primary endpoint.",
      published_at: "2026-06-05T08:00:00Z",
      language: "en",
      publisher_entity_id: "550e8400-e29b-41d4-a716-446655440001",
      related_entity_ids: ["550e8400-e29b-41d4-a716-446655440002"],
      canonical_url: "https://example.test/acme/compound-a",
      venue: "ASCO 2026",
      details: { data_type: "clinical_update" },
      source_document_id: "document-1",
      publisher_entity: {
        id: "550e8400-e29b-41d4-a716-446655440001",
        name: "Acme Pharma",
        entity_type: "organization" as const,
      },
      related_entities: [
        {
          id: "550e8400-e29b-41d4-a716-446655440002",
          name: "Compound A",
          entity_type: "drug" as const,
        },
      ],
    },
  ],
  total: 101,
  limit: 100,
  offset: 0,
  query_schema_version: "pharma.news.search.v2",
  applied_filters: [],
  sort_by: "published_at" as const,
  sort_direction: "desc" as const,
  facets: {
    event_type: { corporate_announcement: 101 },
    publisher: { "Acme Pharma": 101 },
    language: { en: 101 },
    venue: { "ASCO 2026": 101 },
  },
  landscape: {
    total_events: 1,
    event_type: [{ key: "publication", label: "publication", count: 1, share: 1 }],
    venue: [{ key: "ASCO", label: "ASCO", count: 1, share: 1 }],
    published_year: [{ key: "2026", label: "2026", count: 1, share: 1 }],
  },
  as_of: "2026-07-22T10:00:00Z",
  warnings: ["未观察到动态不代表不存在；结果受数据授权、发布时效和治理状态限制。"],
};

beforeEach(() => {
  vi.mocked(searchNewsEvents).mockResolvedValue(newsResult);
  vi.mocked(loadNewsEventDetail).mockResolvedValue(newsResult.items[0]);
  vi.mocked(loadRecordProvenance).mockResolvedValue({
    resource_type: "news_event",
    resource_id: "news-1",
    items: [],
    license_scopes: [],
    warnings: [],
  });
  vi.mocked(saveNewsSearch).mockResolvedValue({ message: "新闻与会议检索已保存并启用监控" });
});

it("renders governed news, applies server filters and opens linked records", async () => {
  const onSearchChange = vi.fn();
  const onOpenEntity = vi.fn();
  const onOpenDrug = vi.fn();
  const onOpenTarget = vi.fn();
  const onOpenDisease = vi.fn();
  const onOpenOrganization = vi.fn();
  const onNewsEventChange = vi.fn();
  renderWithQueryClient(
    <NewsView
      initialFilters={initialFilters}
      initialOffset={0}
      selectedNewsEventId={null}
      onSearchChange={onSearchChange}
      onNewsEventChange={onNewsEventChange}
      onOpenEntity={onOpenEntity}
      onOpenDrug={onOpenDrug}
      onOpenTarget={onOpenTarget}
      onOpenDisease={onOpenDisease}
      onOpenOrganization={onOpenOrganization}
    />,
  );

  expect(await screen.findByRole("table", { name: "新闻与会议结果" })).toBeInTheDocument();
  expect(screen.getByText("项最新动态")).toBeInTheDocument();
  expect(screen.getByText("结果可能受数据覆盖范围和来源更新时间影响。")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent(/治理|授权来源/);
  expect(screen.getByText(/全部结果按发布日期降序/)).toBeInTheDocument();
  expect(searchNewsEvents).toHaveBeenCalledWith(initialFilters, 0, expect.any(AbortSignal));
  expect(screen.getByText("Acme reports positive Phase 2 data for Compound A")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /打开新闻事件详情/ }));
  expect(onNewsEventChange).toHaveBeenCalledWith("news-1");
  expect(screen.getByRole("link", { name: /打开 .* 原始发布页/ })).toHaveAttribute(
    "href",
    "https://example.test/acme/compound-a",
  );

  fireEvent.click(screen.getByRole("button", { name: "Acme Pharma" }));
  expect(onOpenOrganization).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440001");
  fireEvent.click(screen.getByRole("button", { name: "Compound A" }));
  expect(onOpenDrug).toHaveBeenCalledWith("550e8400-e29b-41d4-a716-446655440002");
  expect(onOpenEntity).not.toHaveBeenCalled();

  fireEvent.click(within(screen.getByRole("columnheader", { name: /标题与摘要/ })).getByRole("button"));
  expect(onSearchChange.mock.calls.at(-1)).toEqual([
    {
      ...initialFilters,
      sortBy: "title",
      sortDirection: "asc",
      sort: [{ field: "title", direction: "asc" }],
    },
    0,
  ]);

  fireEvent.change(screen.getByLabelText("事件类型"), { target: { value: "corporate_announcement" } });
  fireEvent.change(screen.getByLabelText("发布方"), { target: { value: "Acme Pharma" } });
  fireEvent.change(screen.getByLabelText("语言"), { target: { value: "en" } });
  fireEvent.change(screen.getByLabelText("会议 / 场景"), { target: { value: "ASCO 2026" } });
  fireEvent.change(screen.getByLabelText("发布起始"), { target: { value: "2026-01-01" } });
  fireEvent.change(screen.getByLabelText("发布截止"), { target: { value: "2026-12-31" } });
  fireEvent.click(screen.getByRole("button", { name: "查询" }));
  expect(onSearchChange).toHaveBeenCalledWith(
    {
      ...initialFilters,
      eventType: "corporate_announcement",
      publisher: "Acme Pharma",
      language: "en",
      venue: "ASCO 2026",
      publishedFrom: "2026-01-01",
      publishedTo: "2026-12-31",
    },
    0,
  );

  fireEvent.click(screen.getByRole("button", { name: /查看 .* 的原始证据/ }));
  expect(await screen.findByRole("dialog", { name: "原始证据" })).toBeInTheDocument();
  expect(loadRecordProvenance).toHaveBeenCalledWith(
    { resourceType: "news_event", resourceId: "news-1", label: newsResult.items[0].title },
    expect.any(AbortSignal),
  );

  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onSearchChange).toHaveBeenCalledWith(initialFilters, 100);
});

it("renders the explicit empty state, clears filters and recovers from errors", async () => {
  vi.mocked(searchNewsEvents).mockResolvedValueOnce({ ...newsResult, items: [], total: 0, facets: {} });
  const onSearchChange = vi.fn();
  const rendered = renderWithQueryClient(
    <NewsView
      initialFilters={{ ...initialFilters, publisher: "Acme Pharma" }}
      initialOffset={0}
      selectedNewsEventId={null}
      onSearchChange={onSearchChange}
      onNewsEventChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );

  expect(await screen.findByText("未观察到匹配动态")).toBeInTheDocument();
  expect(screen.getByText("可调整关键词、公司、药物、靶点、事件类型或日期条件后重试。")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  await waitFor(() =>
    expect(onSearchChange).toHaveBeenCalledWith(
      {
        query: "",
        entityId: "",
        eventType: "",
        publisher: "",
        language: "",
        venue: "",
        publishedFrom: "",
        publishedTo: "",
        contentScope: "",
        displayMode: "list",
        analysisView: "chart",
        sortBy: "published_at",
        sortDirection: "desc",
      },
      0,
    ),
  );
  rendered.unmount();

  vi.mocked(searchNewsEvents).mockRejectedValueOnce(new Error("News source unavailable"));
  renderWithQueryClient(
    <NewsView
      initialFilters={initialFilters}
      initialOffset={0}
      selectedNewsEventId={null}
      onSearchChange={vi.fn()}
      onNewsEventChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );
  expect(await screen.findByText("News source unavailable")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();
});

it("switches to a server-scoped research publication timeline and keeps provenance actions", async () => {
  vi.mocked(searchNewsEvents).mockResolvedValueOnce({
    ...newsResult,
    items: [{ ...newsResult.items[0], event_type: "poster", title: "ASCO 2026 EGFR poster" }],
    total: 1,
    facets: { ...newsResult.facets, event_type: { poster: 1 } },
  });
  const onSearchChange = vi.fn();
  const onOpenEntity = vi.fn();
  const timelineFilters: NewsSearchFilters = {
    ...initialFilters,
    contentScope: "research",
    displayMode: "timeline",
  };
  renderWithQueryClient(
    <NewsView
      initialFilters={timelineFilters}
      initialOffset={0}
      selectedNewsEventId={null}
      onSearchChange={onSearchChange}
      onNewsEventChange={vi.fn()}
      onOpenEntity={onOpenEntity}
    />,
  );

  expect(await screen.findByLabelText("研究发布时间线")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "ASCO 2026 EGFR poster" })).toBeInTheDocument();
  expect(screen.getByText("会议海报")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /查看 .* 的原始证据/ })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "动态列表" }));
  expect(onSearchChange).toHaveBeenCalledWith({ ...timelineFilters, contentScope: "", displayMode: "list" }, 0);
});

it("loads a stable news-event detail and closes it through controlled URL state", async () => {
  vi.mocked(loadNewsEventDetail).mockResolvedValueOnce({
    ...newsResult.items[0],
    publisher_entity: null,
    related_entities: [],
  });
  const onNewsEventChange = vi.fn();
  renderWithQueryClient(
    <NewsView
      initialFilters={initialFilters}
      initialOffset={0}
      selectedNewsEventId="news-1"
      onSearchChange={vi.fn()}
      onNewsEventChange={onNewsEventChange}
      onOpenEntity={vi.fn()}
    />,
  );

  const dialog = await screen.findByRole("dialog", { name: newsResult.items[0].title });
  expect(loadNewsEventDetail).toHaveBeenCalledWith("news-1", expect.any(AbortSignal));
  expect(within(dialog).getByText("The study met its primary endpoint.")).toBeInTheDocument();
  expect(within(dialog).getByText("暂无关联实体信息")).toBeInTheDocument();
  expect(dialog).not.toHaveTextContent(/治理|授权来源/);
  fireEvent.click(within(dialog).getByRole("button", { name: "关闭新闻事件详情" }));
  expect(onNewsEventChange).toHaveBeenCalledWith(null);
});

it("saves and subscribes the authoritative applied research-news query", async () => {
  const filters: NewsSearchFilters = {
    ...initialFilters,
    eventType: "poster",
    publisher: "ASCO",
    language: "en",
    venue: "ASCO 2026",
    publishedFrom: "2026-01-01",
    publishedTo: "2026-12-31",
    contentScope: "research",
    displayMode: "timeline",
    sortBy: "venue",
    sortDirection: "asc",
  };
  renderWithQueryClient(
    <NewsView
      initialFilters={filters}
      initialOffset={0}
      selectedNewsEventId={null}
      onSearchChange={vi.fn()}
      onNewsEventChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );
  await screen.findByLabelText("研究发布时间线");

  fireEvent.click(screen.getByRole("button", { name: "保存/订阅" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "ASCO research watch" } });
  fireEvent.click(screen.getByLabelText("企业内共享该检索"));
  fireEvent.click(screen.getByRole("button", { name: "确认保存" }));

  await waitFor(() =>
    expect(saveNewsSearch).toHaveBeenCalledWith(
      { name: "ASCO research watch", filters, shared: true, monitor: true },
      expect.anything(),
    ),
  );
  expect(await screen.findByRole("status")).toHaveTextContent("新闻与会议检索已保存并启用监控");
});

it("does not save a news query that only contains display and sorting defaults", async () => {
  const emptyNewsFilters = { ...initialFilters, query: "" };
  renderWithQueryClient(
    <NewsView
      initialFilters={emptyNewsFilters}
      initialOffset={0}
      selectedNewsEventId={null}
      onSearchChange={vi.fn()}
      onNewsEventChange={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );
  await screen.findByRole("table", { name: "新闻与会议结果" });
  expect(screen.getByRole("button", { name: "保存/订阅" })).toBeDisabled();
});
