import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import {
  getKnowledgePage,
  getKnowledgePageCoverage,
  getKnowledgePageVersionDiff,
  listKnowledgePages,
  listKnowledgePageVersions,
} from "../lib/contracts/knowledge";
import { KnowledgeView } from "../views/KnowledgeView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/knowledge", () => ({
  knowledgeKeys: {
    pages: (query: string) => ["knowledge", "pages", { query }],
    detail: (pageId: string) => ["knowledge", "pages", pageId],
    coverage: (pageId: string) => ["knowledge", "pages", pageId, "coverage"],
    versions: (pageId: string) => ["knowledge", "pages", pageId, "versions"],
    diff: (pageId: string, versionNumber: number) => ["knowledge", "pages", pageId, versionNumber, "diff"],
  },
  listKnowledgePages: vi.fn(),
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

beforeEach(() => {
  vi.mocked(listKnowledgePages).mockResolvedValue([summary]);
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
  expect(screen.getByText(/EGFR knowledge with citations/)).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("internal-entity-id");
  expect(document.body).not.toHaveTextContent("schema_version");
  expect(document.body).not.toHaveTextContent("knowledge-compiler-v2");
  expect(document.body).not.toHaveTextContent("aaaaaaaaaaaaaaaa");

  fireEvent.change(screen.getByLabelText("检索知识专题"), { target: { value: " EGFR " } });
  fireEvent.submit(screen.getByLabelText("检索知识专题").closest("form") as HTMLFormElement);
  expect(await screen.findByText("1 个专题")).toBeInTheDocument();
  expect(listKnowledgePages).toHaveBeenLastCalledWith("EGFR", expect.any(AbortSignal));
});

it("shows source coverage and lets the user inspect traceable version differences", async () => {
  renderWithQueryClient(<KnowledgeView />);

  fireEvent.click(await screen.findByRole("button", { name: /EGFR landscape/ }));
  fireEvent.click(await screen.findByRole("tab", { name: "覆盖与版本" }));

  expect(await screen.findByText("3", { selector: ".knowledge-coverage-metrics strong" })).toBeInTheDocument();
  expect(screen.getByText("专题要点")).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("治理事实");
  expect(screen.getByRole("cell", { name: "has_competitor" })).toBeInTheDocument();
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
  });

  rerender(<KnowledgeView initialQuery="EGFR" initialPageId="page-1" onLocationChange={onLocationChange} />);
  fireEvent.click(await screen.findByRole("tab", { name: "覆盖与版本" }));
  expect(onLocationChange).toHaveBeenLastCalledWith({
    query: "EGFR",
    pageId: "page-1",
    panel: "coverage",
    versionNumber: null,
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
  });
});

it("fails closed for an invalid knowledge page deep link", async () => {
  renderWithQueryClient(<KnowledgeView invalidPageId initialPageId={null} />);
  expect(await screen.findByText("知识专题链接无效")).toBeInTheDocument();
  expect(getKnowledgePage).not.toHaveBeenCalled();
});
