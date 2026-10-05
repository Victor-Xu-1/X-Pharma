import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { PublicResearchPanel } from "../components/PublicResearchPanel";
import { loadPublicCoverage, searchPublicResearch } from "../lib/contracts/publicResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/publicResearch", () => ({ loadPublicCoverage: vi.fn(), searchPublicResearch: vi.fn() }));

beforeEach(() => {
  vi.mocked(loadPublicCoverage).mockResolvedValue({
    observed_at: "2026-10-05T01:00:00Z",
    entity_counts: { drug: 76, target: 1, patent: 0, transaction: 0 },
    public_source_names: ["ChEMBL"],
    scope_note: "当前组织本地覆盖",
  });
  vi.mocked(searchPublicResearch).mockResolvedValue({
    query: "EGFR",
    observed_at: "2026-10-05T01:00:00Z",
    persisted: false,
    results: [
      {
        topic: "patents",
        provider: "Europe PMC",
        status: "available",
        total: 2046,
        scope_note: "历史专利著录，不代表法律状态。",
        license_notice: "来源条款适用",
        source_query_url: "https://europepmc.org/search",
        records: [
          {
            record_id: "PAT:US2012041070",
            category: "patent_bibliography",
            title: "EGFR inhibitors",
            published_on: "2011-09-30",
            url: "https://europepmc.org/article/PAT/US2012041070",
            fields: { 来源标识: "US2012041070" },
          },
        ],
      },
    ],
  });
  vi.clearAllMocks();
});

it("does not send a draft or restored keyword to public providers without explicit execution", async () => {
  renderWithQueryClient(<PublicResearchPanel defaultQuery="EGFR" defaultTopic="patents" />);
  expect(searchPublicResearch).not.toHaveBeenCalled();
  fireEvent.click(within(screen.getByTestId("public-research-panel")).getByText("公开来源调研"));
  await screen.findByText("当前组织本地覆盖");
  expect(searchPublicResearch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "查询公开来源" }));
  await screen.findByRole("link", { name: "EGFR inhibitors" });
  expect(searchPublicResearch).toHaveBeenCalledTimes(1);
  expect(searchPublicResearch).toHaveBeenCalledWith(
    { q: "EGFR", topic: "patents", limit: 10 },
    expect.any(AbortSignal),
  );
  expect(screen.getByText(/未自动入库/)).toBeInTheDocument();
});

it("keeps provider failure separate from zero results and supports explicit retry", async () => {
  vi.mocked(searchPublicResearch).mockResolvedValue({
    query: "EGFR",
    observed_at: "2026-10-05T01:00:00Z",
    persisted: false,
    results: [
      {
        topic: "targets",
        provider: "ChEMBL",
        status: "unavailable",
        records: [],
        total: null,
        source_query_url: "https://www.ebi.ac.uk/chembl/",
        scope_note: "来源暂不可读取",
        license_notice: "来源条款适用",
        error_code: "upstream_unavailable",
      },
    ],
  });
  renderWithQueryClient(<PublicResearchPanel defaultQuery="EGFR" defaultTopic="targets" />);
  fireEvent.click(within(screen.getByTestId("public-research-panel")).getByText("公开来源调研"));
  fireEvent.click(screen.getByRole("button", { name: "查询公开来源" }));
  await screen.findByText("来源暂不可读取");
  expect(screen.getByText("暂不可用")).toBeInTheDocument();
  expect(screen.queryByText("没有相关研究")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "查询公开来源" }));
  await waitFor(() => expect(searchPublicResearch).toHaveBeenCalledTimes(2));
});
