import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { DealLandscape } from "../components/DealLandscape";
import type { DealLandscapeRead } from "../lib/generated";

const emptyLandscape: DealLandscapeRead = {
  total_deals: 0,
  limit: 5,
};

it("announces empty deal distributions as status updates", () => {
  render(
    <DealLandscape
      landscape={emptyLandscape}
      dimension="all"
      view="chart"
      limit={5}
      onFilter={vi.fn()}
      onAnalysisChange={vi.fn()}
    />,
  );

  const states = screen
    .getAllByRole("status")
    .filter((state) => state.classList.contains("pipeline-landscape-missing"));
  expect(states).toHaveLength(10);
  for (const state of states) {
    expect(state).toHaveAttribute("aria-live", "polite");
    expect(state).toHaveAttribute("aria-atomic", "true");
    expect(state).toHaveTextContent("当前授权命中集没有可统计的该维度数据");
  }
});
