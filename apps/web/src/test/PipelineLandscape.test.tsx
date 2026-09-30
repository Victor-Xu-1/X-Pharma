import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { PipelineLandscape } from "../components/PipelineLandscape";
import type { PipelineLandscapeRead } from "../lib/generated";

const emptyLandscape: PipelineLandscapeRead = {
  total_programs: 0,
  distinct_drugs: 0,
  distinct_diseases: 0,
  distinct_organizations: 0,
  distinct_targets: 0,
  limit: 5,
  stage_scope: "overall",
  target_aggregation: "all",
};

it("announces empty pipeline distributions as status updates", () => {
  render(
    <PipelineLandscape
      landscape={emptyLandscape}
      dimension="all"
      view="chart"
      limit={5}
      stageScope="overall"
      targetAggregation="all"
      onFilter={vi.fn()}
      onOpenEntity={vi.fn()}
      onAnalysisChange={vi.fn()}
    />,
  );

  const states = screen
    .getAllByRole("status")
    .filter((state) => state.classList.contains("pipeline-landscape-missing"));
  expect(states).toHaveLength(8);
  for (const state of states) {
    expect(state).toHaveAttribute("aria-live", "polite");
    expect(state).toHaveAttribute("aria-atomic", "true");
    expect(state).toHaveTextContent("当前查询结果中暂无该维度数据");
  }
  expect(document.body).not.toHaveTextContent(/授权命中|规范靶点|规范疾病|规范机构|受治理模态/);
});

it("uses canonical target-combination labels and keys without client-side renumbering", () => {
  const onFilter = vi.fn();
  render(
    <PipelineLandscape
      landscape={{
        ...emptyLandscape,
        total_programs: 4,
        target_combinations: [
          { key: "target-a", label: "EGFR", count: 3, share: 0.75 },
          { key: "target-a|target-b", label: "EGFR + ERBB2", count: 1, share: 0.25 },
        ],
      }}
      dimension="target_combinations"
      view="chart"
      limit={20}
      stageScope="overall"
      targetAggregation="all"
      onFilter={onFilter}
      onOpenEntity={vi.fn()}
      onAnalysisChange={vi.fn()}
    />,
  );

  const region = screen.getByRole("region", { name: "靶点组合" });
  expect(within(region).getByTitle("按EGFR筛选")).toHaveTextContent("EGFR375.0%");
  expect(within(region).getByTitle("按EGFR + ERBB2筛选")).toHaveTextContent("EGFR + ERBB2125.0%");
  expect(within(region).queryByText(/单靶点 \d|组合 \d/)).not.toBeInTheDocument();
  expect(within(region).getAllByRole("button")).toHaveLength(2);

  fireEvent.click(within(region).getByTitle("按EGFR + ERBB2筛选"));
  expect(onFilter).toHaveBeenCalledWith("targetCombinationKey", "target-a|target-b", "EGFR + ERBB2");
});

it("localizes governed modality labels without changing the filter value", () => {
  const onFilter = vi.fn();
  render(
    <PipelineLandscape
      landscape={{
        ...emptyLandscape,
        total_programs: 6,
        modality: [{ key: "small molecule", label: "small molecule", count: 6, share: 1 }],
      }}
      dimension="modality"
      view="chart"
      limit={20}
      stageScope="overall"
      targetAggregation="all"
      onFilter={onFilter}
      onOpenEntity={vi.fn()}
      onAnalysisChange={vi.fn()}
    />,
  );

  const region = screen.getByRole("region", { name: "药物类型" });
  const filterButton = within(region).getByTitle("按小分子筛选");
  expect(filterButton).toHaveTextContent("小分子6100.0%");
  expect(within(region).queryByText("small molecule")).not.toBeInTheDocument();

  fireEvent.click(filterButton);
  expect(onFilter).toHaveBeenCalledWith("modality", "small molecule", "小分子");
});
