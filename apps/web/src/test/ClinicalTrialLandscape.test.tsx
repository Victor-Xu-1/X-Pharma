import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ClinicalTrialLandscape } from "../components/ClinicalTrialLandscape";

it("renders full-hit-set clinical matrices and applies professional filters", () => {
  const onFilter = vi.fn();
  const onViewChange = vi.fn();
  const landscape = {
    total_trials: 2202,
    publication_year_phase: [
      { key: "2026", total: 223, values: { PHASE1: 43, PHASE2: 118, PHASE3: 33 } },
      { key: "2025", total: 371, values: { PHASE1: 80, PHASE2: 185, PHASE3: 54 } },
    ],
    phase_evaluation: [{ key: "PHASE2", total: 1038, values: { unfavorable: 117, positive: 894, terminated: 24 } }],
  };
  const { rerender } = render(
    <ClinicalTrialLandscape landscape={landscape} onFilter={onFilter} view="chart" onViewChange={onViewChange} />,
  );

  expect(screen.getByLabelText("临床结果可视化")).toHaveTextContent("2,202");
  expect(screen.getByRole("img", { name: "试验数量完整命中集分布" })).toBeVisible();
  fireEvent.click(within(screen.getByRole("group", { name: "试验数量图例" })).getByRole("button", { name: "II 期" }));
  expect(onFilter).toHaveBeenCalledWith("phase", "PHASE2");

  const overallEvaluation = screen.getByRole("heading", { name: "总体评价" }).closest("section");
  expect(overallEvaluation).not.toBeNull();
  // The chart/table toggle is URL-owned controlled state: clicking requests the change
  // and the restored view arrives back through props, so refresh/share/replay keep it.
  fireEvent.click(within(overallEvaluation as HTMLElement).getByRole("button", { name: "列表" }));
  expect(onViewChange).toHaveBeenCalledWith("table");
  rerender(
    <ClinicalTrialLandscape landscape={landscape} onFilter={onFilter} view="table" onViewChange={onViewChange} />,
  );
  expect(screen.getByRole("table", { name: "总体评价统计表" })).toHaveTextContent("1,038");
  fireEvent.click(within(screen.getByRole("group", { name: "总体评价图例" })).getByRole("button", { name: "积极" }));
  expect(onFilter).toHaveBeenCalledWith("result_evaluation", "positive");
});

it("announces empty clinical landscape sections as status updates", () => {
  render(
    <ClinicalTrialLandscape
      landscape={{ total_trials: 0, publication_year_phase: [], phase_evaluation: [] }}
      onFilter={vi.fn()}
      view="chart"
      onViewChange={vi.fn()}
    />,
  );

  const states = screen.getAllByRole("status");
  expect(states).toHaveLength(2);
  for (const state of states) {
    expect(state).toHaveAttribute("aria-live", "polite");
    expect(state).toHaveAttribute("aria-atomic", "true");
    expect(state).toHaveTextContent("当前授权命中集没有可统计的数据");
  }
});
