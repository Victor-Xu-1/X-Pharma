import { act, fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { PublicResearchResults } from "../components/PublicResearchResults";
import type { PublicResearchResponse } from "../lib/generated";
import { setLocale } from "../lib/i18n";

const response: PublicResearchResponse = {
  query: "中文研究 EGFR",
  observed_at: "2026-10-08T10:00:00Z",
  persisted: false,
  results: [
    {
      topic: "literature",
      provider: "Europe PMC",
      status: "available",
      total: 1234,
      scope_note: "来源范围原文",
      license_notice: "来源许可原文",
      source_query_url: "https://europepmc.org/search",
      records: [
        {
          record_id: "PMID:123",
          category: "literature",
          title: "中文文章 EGFR",
          published_on: "2026-10-01",
          url: "https://europepmc.org/article/MED/123",
          fields: { 来源字段: "原始值" },
        },
      ],
    },
  ],
};

it("localizes result status and dates without rewriting source metadata or reopening disclosures", () => {
  const { rerender } = render(<PublicResearchResults response={response} />);
  fireEvent.click(screen.getByText(/Europe PMC/, { selector: "summary" }));
  act(() => setLocale("en"));
  rerender(<PublicResearchResults response={response} />);
  expect(screen.getByRole("region", { name: "Public research results" })).toBeVisible();
  expect(screen.getByText("Available")).toBeVisible();
  expect(screen.getByText("1,234 source matches")).toBeVisible();
  expect(screen.getByText(/Public metadata only; not automatically stored or verified as facts/)).toHaveTextContent(
    "中文研究 EGFR",
  );
  expect(screen.getByText(/Europe PMC/, { selector: "summary" }).closest("details")).not.toHaveAttribute("open");
  fireEvent.click(screen.getByText(/Europe PMC/, { selector: "summary" }));
  expect(screen.getByRole("link", { name: "中文文章 EGFR" })).toBeVisible();
  expect(screen.getByText("来源范围原文")).toBeVisible();
  expect(screen.getByText("来源字段：原始值")).toBeVisible();
  expect(screen.getByText("Source date: 2026-10-01 · PMID:123")).toBeVisible();
  expect(screen.getByText("来源许可原文")).toBeVisible();
});

it.each(["empty", "unavailable"] as const)("keeps %s distinct from available scientific records", (status) => {
  setLocale("en");
  render(
    <PublicResearchResults
      response={{
        ...response,
        results: [{ ...response.results[0], status, total: status === "empty" ? 0 : null, records: [] }],
      }}
    />,
  );
  expect(screen.getByText(status === "empty" ? "No matches in this scope" : "Temporarily unavailable")).toBeVisible();
  expect(screen.queryByRole("link", { name: "中文文章 EGFR" })).not.toBeInTheDocument();
});
