import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getKnowledgePage,
  getKnowledgePageCoverage,
  getKnowledgePageVersionDiff,
  listKnowledgePageVersions,
  searchKnowledgePages,
} from "../lib/contracts/knowledge";
import { KnowledgeView } from "../views/KnowledgeView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/knowledge", () => ({
  knowledgeKeys: {
    pages: (filters: unknown) => ["knowledge", "pages", filters],
    detail: (pageId: string) => ["knowledge", "pages", pageId],
    coverage: (pageId: string) => ["knowledge", "pages", pageId, "coverage"],
    versions: (pageId: string) => ["knowledge", "pages", pageId, "versions"],
    diff: (pageId: string, versionNumber: number) => ["knowledge", "pages", pageId, versionNumber, "diff"],
  },
  KNOWLEDGE_PAGE_SIZE: 50,
  searchKnowledgePages: vi.fn(),
  getKnowledgePage: vi.fn(),
  getKnowledgePageCoverage: vi.fn(),
  listKnowledgePageVersions: vi.fn(),
  getKnowledgePageVersionDiff: vi.fn(),
}));

const summary = {
  id: "page-1",
  page_type: "target",
  title: "EGFR landscape",
  updated_at: "2026-07-18T11:00:00Z",
};

describe("compact knowledge reading", () => {
  let previous: PropertyDescriptor | undefined;
  beforeEach(() => {
    previous = Object.getOwnPropertyDescriptor(window, "matchMedia");
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    });
  });
  afterEach(() => {
    if (previous) Object.defineProperty(window, "matchMedia", previous);
    else Reflect.deleteProperty(window, "matchMedia");
  });
  it("prioritizes the selected document while keeping the searchable catalogue and its draft reachable", async () => {
    renderWithQueryClient(<KnowledgeView initialPageId="page-1" />);
    expect(await screen.findByRole("heading", { name: "EGFR landscape" })).toBeVisible();
    expect(screen.getByLabelText("检索知识专题")).not.toBeVisible();
    const opener = screen.getByRole("button", { name: "展开专题目录" });
    expect(opener).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(opener);
    const search = screen.getByLabelText("检索知识专题");
    expect(search).toBeVisible();
    fireEvent.change(search, { target: { value: "retained research draft" } });
    fireEvent.click(screen.getByRole("button", { name: "收起专题目录" }));
    expect(search).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "展开专题目录" }));
    expect(search).toHaveValue("retained research draft");
    expect(getKnowledgePage).toHaveBeenCalledWith("page-1", expect.any(AbortSignal));
  });
  it("keeps an unselected catalogue visible and transfers selection focus to the complete document title", async () => {
    renderWithQueryClient(<KnowledgeView />);
    const selected = await screen.findByRole("button", { name: /EGFR landscape/ });
    expect(screen.getByLabelText("检索知识专题")).toBeVisible();
    selected.focus();
    fireEvent.click(selected);
    const heading = await screen.findByRole("heading", { name: "EGFR landscape" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByLabelText("检索知识专题")).not.toBeVisible();
    expect(screen.getByRole("button", { name: "展开专题目录" })).toBeVisible();
  });
  it("keeps a failed selection recoverable without stranding focus in the hidden catalogue", async () => {
    vi.mocked(getKnowledgePage).mockRejectedValueOnce(new Error("专题暂时无法读取"));
    renderWithQueryClient(<KnowledgeView />);
    const selected = await screen.findByRole("button", { name: /EGFR landscape/ });
    selected.focus();
    fireEvent.click(selected);
    expect(await screen.findByRole("alert")).toHaveTextContent("专题暂时无法读取");
    expect(screen.getByRole("button", { name: "展开专题目录" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    const heading = await screen.findByRole("heading", { name: "EGFR landscape" });
    await waitFor(() => expect(heading).toHaveFocus());
  });
});

it("keeps knowledge document and coverage switching keyboard-operable without losing the selected page", async () => {
  renderWithQueryClient(<KnowledgeView />);
  fireEvent.click(await screen.findByRole("button", { name: /EGFR landscape/ }));
  const documentTab = await screen.findByRole("tab", { name: "专题正文" });
  documentTab.focus();
  fireEvent.keyDown(documentTab, { key: "End" });
  const coverageTab = screen.getByRole("tab", { name: "覆盖与版本" });
  expect(coverageTab).toHaveFocus();
  expect(coverageTab).toHaveAttribute("aria-selected", "true");
  await waitFor(() => expect(screen.getByRole("tabpanel")).toHaveAccessibleName("覆盖与版本"));
  fireEvent.keyDown(coverageTab, { key: "Home" });
  expect(documentTab).toHaveFocus();
  expect(documentTab).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("tabpanel")).toHaveAccessibleName("专题正文");
});

beforeEach(() => {
  vi.mocked(searchKnowledgePages).mockResolvedValue({
    query_schema_version: "pharma.knowledge.search.v1",
    items: [summary],
    total: 1,
    limit: 50,
    offset: 0,
    sort_by: "title",
    sort_direction: "asc",
    facets: { page_type: { target: 1 } },
    as_of: "2026-07-18T11:00:00Z",
  });
  vi.mocked(getKnowledgePage).mockResolvedValue({
    ...summary,
    rendered_markdown: [
      "---",
      'id: "internal-entity-id"',
      'schema_version: "1.0"',
      "---",
      "# EGFR",
      "EGFR knowledge with citations.",
    ].join("\n"),
    source_snapshot_at: "2026-07-18T10:00:00Z",
    version_number: 2,
  });
  vi.mocked(getKnowledgePageCoverage).mockResolvedValue({
    cited_fact_count: 3,
    fact_count: 3,
    linked_entity_count: 2,
    predicates: [
      { cited_fact_count: 2, fact_count: 2, predicate: "has_competitor" },
      { cited_fact_count: 1, fact_count: 1, predicate: "has_target_class" },
    ],
    source_count: 2,
    source_snapshot_at: "2026-07-18T10:00:00Z",
    uncited_fact_count: 0,
    version_number: 2,
  });
  vi.mocked(listKnowledgePageVersions).mockResolvedValue([
    {
      added_fact_count: 1,
      added_source_count: 1,
      is_current: true,
      previous_version_number: 1,
      removed_fact_count: 0,
      removed_source_count: 0,
      source_snapshot_at: "2026-07-18T10:00:00Z",
      version_number: 2,
    },
    {
      added_fact_count: 2,
      added_source_count: 1,
      is_current: false,
      previous_version_number: null,
      removed_fact_count: 0,
      removed_source_count: 0,
      source_snapshot_at: "2026-07-17T10:00:00Z",
      version_number: 1,
    },
  ]);
  vi.mocked(getKnowledgePageVersionDiff).mockImplementation(async (_pageId, versionNumber) => ({
    added_fact_count: versionNumber === 2 ? 1 : 2,
    added_facts: [
      {
        change_key: `change-${versionNumber}`,
        object_entity_name: null,
        predicate: "has_competitor",
        source_locator: "page=4",
        source_title: "Competitive landscape update",
        value: { name: "Drug B" },
      },
    ],
    added_source_count: 1,
    added_sources: [
      {
        locator: "page=4",
        title: "Competitive landscape update",
      },
    ],
    from_version_number: versionNumber === 2 ? 1 : null,
    removed_fact_count: 0,
    removed_facts: [],
    removed_source_count: 0,
    removed_sources: [],
    to_version_number: versionNumber,
    truncated: false,
  }));
});

it("loads a searchable page index and a separately cached immutable version", async () => {
  renderWithQueryClient(<KnowledgeView />);

  fireEvent.click(await screen.findByRole("button", { name: /EGFR landscape/ }));
  expect(await screen.findByRole("heading", { name: "EGFR landscape" })).toBeInTheDocument();
  expect(getKnowledgePage).toHaveBeenCalledWith("page-1", expect.any(AbortSignal));
  expect(screen.getByText(/EGFR knowledge with citations/, { selector: ".knowledge-reading > p" })).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("internal-entity-id");
  expect(document.body).not.toHaveTextContent("schema_version");
  expect(document.body).not.toHaveTextContent("knowledge-compiler-v2");
  expect(document.body).not.toHaveTextContent("aaaaaaaaaaaaaaaa");

  fireEvent.change(screen.getByLabelText("检索知识专题"), { target: { value: " EGFR " } });
  fireEvent.submit(screen.getByLabelText("检索知识专题").closest("form") as HTMLFormElement);
  expect(await screen.findByText("1 个专题")).toBeInTheDocument();
  expect(searchKnowledgePages).toHaveBeenLastCalledWith(
    { query: "EGFR", offset: 0, pageType: "", sortBy: "title", sortDirection: "asc" },
    expect.any(AbortSignal),
  );
});

it("renders readable document structure, traceable references and safe public links instead of raw Markdown", async () => {
  vi.mocked(getKnowledgePage).mockResolvedValue({
    ...summary,
    rendered_markdown: [
      "# EGFR landscape",
      "## 研究摘要",
      "**已记录的证据** [原始来源](https://example.org/public-source).[^1]",
      "",
      "| 指标 | 数值 |",
      "| --- | --- |",
      "| 已记录项目 | 0 |",
      "",
      "[危险链接](javascript:alert(1))",
      "![远程图像](https://invalid.example/tracker.png)",
      "<script>alert('untrusted')</script>",
      "",
      "[^1]: 原始来源 · 定位 page=4",
    ].join("\n"),
    source_snapshot_at: "2026-07-18T10:00:00Z",
    version_number: 2,
  });
  renderWithQueryClient(<KnowledgeView initialPageId="page-1" />);
  const panel = await screen.findByRole("tabpanel", { name: "专题正文" });
  expect(within(panel).getByRole("heading", { name: "研究摘要", level: 3 })).toBeVisible();
  expect(within(panel).getByRole("link", { name: "原始来源" })).toHaveAttribute(
    "href",
    "https://example.org/public-source",
  );
  const table = within(panel).getByRole("table", { name: "专题表格" });
  expect(within(table).getByRole("cell", { name: "已记录项目" })).toBeVisible();
  expect(within(table).getByRole("cell", { name: "0" })).toBeVisible();
  expect(within(panel).getByRole("heading", { name: "引用与来源" })).toBeVisible();
  expect(within(panel).queryByRole("link", { name: "危险链接" })).not.toBeInTheDocument();
  expect(panel.querySelector("script,img,iframe")).toBeNull();
  expect(screen.getAllByRole("heading", { name: "EGFR landscape" })).toHaveLength(1);
});

it("presents a structured alias change without dropping its literal original value or embedded locator", async () => {
  const value = {
    fact_kind: "entity_alias",
    subject: { entity_type: "drug", name: "Reviewed Drug" },
    alias: "AC-0010",
    citation: { locator: "molecule:reviewed:alias:1", quote: "Exact submitted public quote", confidence: 0 },
  };
  vi.mocked(getKnowledgePageVersionDiff).mockResolvedValue({
    added_fact_count: 1,
    added_facts: [
      {
        change_key: "alias-change",
        object_entity_name: null,
        predicate: "has_entity_alias",
        source_title: null,
        source_locator: null,
        value,
      },
    ],
    added_source_count: 0,
    added_sources: [],
    from_version_number: 1,
    to_version_number: 2,
    removed_fact_count: 0,
    removed_facts: [],
    removed_source_count: 0,
    removed_sources: [],
    truncated: false,
  });
  renderWithQueryClient(<KnowledgeView initialPageId="page-1" initialPanel="coverage" />);
  const change = await screen.findByRole("region", { name: "新增要点" });
  expect(within(change).getByText("别名")).toBeVisible();
  expect(within(change).getByText("AC-0010 · Reviewed Drug")).toBeVisible();
  expect(within(change).getByText(/molecule:reviewed:alias:1/, { selector: "small" })).toBeVisible();
  const original = within(change).getByText("原始结构化记录", { selector: "summary" });
  fireEvent.click(original);
  expect(within(change).getByLabelText("完整原始结构化值")).toHaveValue(JSON.stringify(value, null, 2));
  expect(document.body).not.toHaveTextContent("无来源标题");
});

it("shows source coverage and lets the user inspect traceable version differences", async () => {
  renderWithQueryClient(<KnowledgeView />);

  fireEvent.click(await screen.findByRole("button", { name: /EGFR landscape/ }));
  fireEvent.click(await screen.findByRole("tab", { name: "覆盖与版本" }));

  expect(await screen.findByText("3", { selector: ".knowledge-coverage-metrics strong" })).toBeInTheDocument();
  expect(screen.getByText("专题要点")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("治理事实");
  expect(screen.getByRole("cell", { name: "竞品关系" })).toBeInTheDocument();
  expect(await screen.findByRole("heading", { name: "v1 → v2" })).toBeInTheDocument();
  expect(screen.getByText("Competitive landscape update")).toBeInTheDocument();
  expect(screen.getAllByText(/page=4/)).toHaveLength(2);
  expect(getKnowledgePageCoverage).toHaveBeenCalledWith("page-1", expect.any(AbortSignal));
  expect(listKnowledgePageVersions).toHaveBeenCalledWith("page-1", expect.any(AbortSignal));
  expect(getKnowledgePageVersionDiff).toHaveBeenCalledWith("page-1", 2, expect.any(AbortSignal));

  const versionList = screen.getByRole("list", { name: "专题版本" });
  fireEvent.click(within(versionList).getByRole("button", { name: /v1/ }));
  expect(await screen.findByRole("heading", { name: "初始版本 v1" })).toBeInTheDocument();
  expect(getKnowledgePageVersionDiff).toHaveBeenLastCalledWith("page-1", 1, expect.any(AbortSignal));
});

it("emits stable location changes for search, page, panel and immutable version", async () => {
  const onLocationChange = vi.fn();
  const { rerender } = renderWithQueryClient(<KnowledgeView initialQuery="EGFR" onLocationChange={onLocationChange} />);

  fireEvent.click(await screen.findByRole("button", { name: /EGFR landscape/ }));
  expect(onLocationChange).toHaveBeenLastCalledWith({
    query: "EGFR",
    pageId: "page-1",
    panel: "document",
    versionNumber: null,
    offset: 0,
    pageType: "",
    sortBy: "title",
    sortDirection: "asc",
  });

  rerender(<KnowledgeView initialQuery="EGFR" initialPageId="page-1" onLocationChange={onLocationChange} />);
  fireEvent.click(await screen.findByRole("tab", { name: "覆盖与版本" }));
  expect(onLocationChange).toHaveBeenLastCalledWith({
    query: "EGFR",
    pageId: "page-1",
    panel: "coverage",
    versionNumber: null,
    offset: 0,
    pageType: "",
    sortBy: "title",
    sortDirection: "asc",
  });

  rerender(
    <KnowledgeView
      initialQuery="EGFR"
      initialPageId="page-1"
      initialPanel="coverage"
      onLocationChange={onLocationChange}
    />,
  );
  fireEvent.click(
    await screen
      .findByRole("list", { name: "专题版本" })
      .then((list) => within(list).getByRole("button", { name: /v1/ })),
  );
  expect(onLocationChange).toHaveBeenLastCalledWith({
    query: "EGFR",
    pageId: "page-1",
    panel: "coverage",
    versionNumber: 1,
    offset: 0,
    pageType: "",
    sortBy: "title",
    sortDirection: "asc",
  });
});

it("fails closed for an invalid knowledge page deep link", async () => {
  renderWithQueryClient(<KnowledgeView invalidPageId initialPageId={null} />);
  expect(await screen.findByText("知识专题链接无效")).toBeInTheDocument();
  expect(getKnowledgePage).not.toHaveBeenCalled();
});

it.each(["pending", "failed"])("preserves a later-page deep link while the index is %s", async (state) => {
  if (state === "pending") vi.mocked(searchKnowledgePages).mockImplementation(() => new Promise(() => {}));
  else vi.mocked(searchKnowledgePages).mockRejectedValue(new Error("Index unavailable"));
  const onLocationChange = vi.fn();
  renderWithQueryClient(<KnowledgeView initialOffset={500} onLocationChange={onLocationChange} />);
  if (state === "pending") await screen.findByText("正在加载知识专题");
  else await screen.findByRole("alert");
  expect(onLocationChange).not.toHaveBeenCalled();
  expect(screen.getByLabelText("专题类型")).toBeInTheDocument();
});
