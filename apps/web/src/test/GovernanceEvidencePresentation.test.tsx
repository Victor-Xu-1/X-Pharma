import { useQuery } from "@tanstack/react-query";
import { act, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { FactQualityFindings } from "../components/FactQualityFindings";
import { FactReviewComparison, FieldDifferences } from "../components/FactReviewComparison";
import type { StagedFact } from "../lib/contracts/governance";
import { governanceKeys, loadFactComparison } from "../lib/contracts/governance";
import { setLocale } from "../lib/i18n";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/governance", async (original) => ({
  ...(await original<typeof import("../lib/contracts/governance")>()),
  loadFactComparison: vi.fn(),
}));
const fact: StagedFact = {
  id: "requested-fact",
  fact_kind: "claim",
  payload: { value: "原始报告值" },
  raw_payload: { value: "原始报告值" },
  normalization_version: null,
  source_document_id: "original-document",
  source_locator: "page 3",
  source_quote: "原始引文 remains literal",
  confidence: 0.9,
  status: "review_pending",
  quality_findings: [],
  conflict_with_ids: [],
  created_at: "2026-10-10T00:00:00Z",
};
function ComparisonReader() {
  const comparison = useQuery({
    queryKey: governanceKeys.factComparison(fact.id),
    queryFn: ({ signal }) => loadFactComparison(fact.id, signal),
  });
  return <FactReviewComparison fact={fact} comparison={comparison} onRetry={() => void comparison.refetch()} />;
}
it("localizes field framing without translating scientific values or changing zero and missingness", () => {
  setLocale("en");
  renderWithQueryClient(
    <FieldDifferences
      before={{ subject: { name: "原始研究对象" }, value: null }}
      after={{ subject: { name: "原始研究对象 B" }, value: 0, added: "0.000000" }}
      beforeTitle="Original"
      afterTitle="Normalized"
    />,
  );
  expect(screen.getByRole("columnheader", { name: "Field" })).toBeInTheDocument();
  expect(screen.getByText("Subject / Name")).toBeInTheDocument();
  expect(screen.getByText("Not disclosed")).toBeInTheDocument();
  expect(screen.getByText("Field absent")).toBeInTheDocument();
  expect(screen.getByText("原始研究对象 B")).toBeInTheDocument();
  expect(screen.getByText("0")).toBeInTheDocument();
  expect(screen.getByText("0.000000")).toBeInTheDocument();
});
it("keeps unknown quality codes and provider messages literal without prototype lookup", () => {
  setLocale("en");
  renderWithQueryClient(
    <FactQualityFindings
      findings={[
        { code: "conflicting_fact", field: "subject.name", model_value: "原始值" },
        { code: "constructor", message: "RAW_UNKNOWN_PROVIDER_MESSAGE" },
      ]}
    />,
  );
  expect(screen.getByRole("heading", { name: "Quality findings" })).toBeInTheDocument();
  expect(screen.getByText("Historical and candidate facts contain different field values")).toBeInTheDocument();
  expect(screen.getByText("RAW_UNKNOWN_PROVIDER_MESSAGE")).toBeInTheDocument();
  expect(screen.getByText("Reported value: 原始值")).toBeInTheDocument();
});
it("rejects comparison data for a different fact instead of displaying its evidence", async () => {
  setLocale("en");
  vi.mocked(loadFactComparison).mockResolvedValue({
    fact: { ...fact, id: "other-fact" },
    origin: null,
    conflicts: [],
    conflict_total: 0,
    unavailable_conflicts: 0,
    truncated: false,
  });
  renderWithQueryClient(<ComparisonReader />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Comparison data does not match the requested fact");
  expect(screen.queryByRole("heading", { name: "Source and parsing method" })).not.toBeInTheDocument();
});
it("preserves open technical evidence and uses no additional read when the interface language changes", async () => {
  setLocale("en");
  vi.mocked(loadFactComparison).mockReset().mockResolvedValue({
    fact,
    origin: null,
    conflicts: [],
    conflict_total: 0,
    unavailable_conflicts: 0,
    truncated: false,
  });
  renderWithQueryClient(<ComparisonReader />);
  const summary = await screen.findByText("Technical details and complete original records");
  const disclosure = summary.closest("details");
  if (!disclosure) throw new Error("Technical evidence disclosure is missing");
  disclosure.open = true;
  await act(() => setLocale("zh-CN"));
  expect(screen.getByText("技术详情与完整原始记录").closest("details")).toBe(disclosure);
  expect(disclosure.open).toBe(true);
  expect(loadFactComparison).toHaveBeenCalledTimes(1);
  expect(screen.getAllByText(/原始报告值/).length).toBeGreaterThan(0);
});
