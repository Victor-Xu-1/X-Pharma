import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { searchKnowledgePages } from "../lib/contracts/knowledge";
import { KnowledgeView } from "../views/KnowledgeView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/knowledge", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/contracts/knowledge")>()),
  searchKnowledgePages: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(searchKnowledgePages).mockResolvedValue({
    query_schema_version: "pharma.knowledge.search.v1",
    items: [],
    total: 922,
    limit: 50,
    offset: 500,
    sort_by: "title",
    sort_direction: "asc",
    facets: { page_type: { drug: 922 } },
    as_of: "2026-10-06T14:00:00Z",
  });
});

it("shows the complete count and keeps page navigation in the controlled research location", async () => {
  const onLocationChange = vi.fn();
  renderWithQueryClient(<KnowledgeView initialOffset={500} onLocationChange={onLocationChange} />);
  expect(await screen.findByText("922 个专题")).toBeInTheDocument();
  expect(searchKnowledgePages).toHaveBeenCalledWith(
    { query: "", offset: 500, pageType: "", sortBy: "title", sortDirection: "asc" },
    expect.any(AbortSignal),
  );
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(onLocationChange).toHaveBeenCalledWith(expect.objectContaining({ offset: 550, pageId: null }));
  fireEvent.change(screen.getByLabelText("专题类型"), { target: { value: "drug" } });
  expect(onLocationChange).toHaveBeenCalledWith(expect.objectContaining({ pageType: "drug", offset: 0, pageId: null }));
});
