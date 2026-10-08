import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfessionalQueryBuilder } from "../components/ProfessionalQueryBuilder";
import { loadPipelineFacetCatalog } from "../lib/contracts/pipeline";
import { setLocale } from "../lib/i18n";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/pipeline", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/contracts/pipeline")>();
  return {
    ...actual,
    loadPipelineFacetCatalog: vi.fn().mockResolvedValue({
      as_of: "2026-08-08T00:00:00Z",
      facets: {},
      warnings: [],
    }),
  };
});

describe("ProfessionalQueryBuilder", () => {
  it("does not turn empty governed catalogs into noisy public filters", async () => {
    renderWithQueryClient(<ProfessionalQueryBuilder query="SEC61G" onExecute={vi.fn()} />);

    await waitFor(() => expect(vi.mocked(loadPipelineFacetCatalog)).toHaveBeenCalledOnce());

    expect(document.querySelectorAll(".professional-facet-state")).toHaveLength(0);
    expect(document.body).not.toHaveTextContent(/暂无可用.*选项/);
  });

  it("switches the professional shell and date fields without clearing unapplied conditions or reading catalogs again", async () => {
    const execute = vi.fn();
    const { rerender } = renderWithQueryClient(<ProfessionalQueryBuilder query="EGFR" onExecute={execute} />);
    await waitFor(() => expect(vi.mocked(loadPipelineFacetCatalog)).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("总体最高阶段"), { target: { value: "phase_2" } });
    fireEvent.change(screen.getByLabelText("状态日期时间范围"), { target: { value: "custom" } });
    fireEvent.change(within(screen.getByRole("group", { name: "状态日期" })).getByLabelText("起"), {
      target: { value: "2026-10-01" },
    });
    const reads = vi.mocked(loadPipelineFacetCatalog).mock.calls.length;
    act(() => setLocale("en"));
    rerender(<ProfessionalQueryBuilder query="EGFR" onExecute={execute} />);
    expect(screen.getByText("Professional query")).toBeVisible();
    expect(screen.getByRole("button", { name: "Drugs and pipelines" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Highest overall phase")).toHaveValue("phase_2");
    expect(screen.getByLabelText("Highest overall phase")).toHaveAttribute("aria-label", "Highest overall phase");
    expect(screen.getByLabelText("Status date range")).toHaveValue("custom");
    expect(within(screen.getByRole("group", { name: "Status date" })).getByLabelText("From")).toHaveValue("2026-10-01");
    expect(loadPipelineFacetCatalog).toHaveBeenCalledTimes(reads);
    expect(execute).not.toHaveBeenCalled();
  });
});
