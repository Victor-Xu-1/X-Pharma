import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { DomainLandscape } from "../components/DomainLandscape";

it("announces empty domain distributions as status updates", () => {
  render(
    <DomainLandscape
      domainId="pipeline"
      ariaLabel="研发格局"
      total={0}
      totalUnit="个项目"
      unitLabel="项目"
      sections={[
        { id: "phase", title: "研发阶段", detail: "按阶段统计", buckets: [], filterField: "phase" },
        { id: "modality", title: "模态", detail: "按模态统计", buckets: [], filterField: null },
      ]}
      view="chart"
      onViewChange={vi.fn()}
      onFilter={vi.fn()}
    />,
  );

  const states = screen.getAllByRole("status");
  expect(states).toHaveLength(2);
  for (const state of states) {
    expect(state).toHaveAttribute("aria-live", "polite");
    expect(state).toHaveAttribute("aria-atomic", "true");
    expect(state).toHaveTextContent("当前查询没有可统计的记录");
  }
});
