import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ClinicalTrialLandscape } from "../components/ClinicalTrialLandscape";
import { setLocale } from "../lib/i18n";

// Synthetic-only boundary records; they are never written to the clinical datastore.
const landscape = {
  total_trials: 1,
  publication_year_phase: [{ key: "2026", total: 2, values: { PHASE2: 1, RAW_PHASE_CODE: 1 } }],
  phase_evaluation: [{ key: "RAW_PHASE_CODE", total: 1, values: { RAW_EVALUATION_CODE: 1 } }],
};

it("localizes controls and distinguishes phase assignments from distinct studies without changing controlled state", () => {
  setLocale("en");
  const onViewChange = vi.fn();
  const onFilter = vi.fn();
  render(<ClinicalTrialLandscape landscape={landscape} onFilter={onFilter} view="table" onViewChange={onViewChange} />);
  expect(screen.getByLabelText("Clinical result visualization")).toHaveTextContent("1");
  const table = screen.getByRole("table", { name: "Trial phase assignments statistics" });
  expect(table).toHaveTextContent("Phase II");
  expect(screen.getByText(/Phase assignments are not the number of distinct studies/)).toBeVisible();
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "试验数量统计表" })).toHaveTextContent("II 期");
  expect(onViewChange).not.toHaveBeenCalled();
  expect(onFilter).not.toHaveBeenCalled();
});

it("retains unknown source phase and evaluation columns and their counts", () => {
  const onFilter = vi.fn();
  render(<ClinicalTrialLandscape landscape={landscape} onFilter={onFilter} view="table" onViewChange={vi.fn()} />);
  const table = screen.getByRole("table", { name: "试验数量统计表" });
  expect(within(table).getByRole("columnheader", { name: "RAW_PHASE_CODE" })).toBeVisible();
  expect(
    within(table)
      .getAllByRole("cell")
      .map((cell) => cell.textContent),
  ).toContain("1");
  const evaluation = screen.getByRole("table", { name: "总体评价统计表" });
  expect(within(evaluation).getByRole("columnheader", { name: "RAW_EVALUATION_CODE" })).toBeVisible();
  fireEvent.click(
    within(screen.getByRole("group", { name: "试验数量图例" })).getByRole("button", { name: "RAW_PHASE_CODE" }),
  );
  expect(onFilter).toHaveBeenCalledWith("phase", "RAW_PHASE_CODE");
});
