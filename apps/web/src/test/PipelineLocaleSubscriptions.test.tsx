import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { emptyPipelineSearchFilters } from "../lib/contracts/pipeline";
import { setLocale } from "../lib/i18n";
import { PipelineAdvancedFilters } from "../views/pipeline/PipelineAdvancedFilters";
import { PipelineDateRange } from "../views/pipeline/PipelineDateRange";
import { PipelineSignalFilters } from "../views/pipeline/PipelineSignalFilters";

it.each(["advanced", "signals"] as const)(
  "subscribes the standalone %s UI without requiring a parent rerender",
  (variant) => {
    setLocale("en");
    const filters = {
      ...emptyPipelineSearchFilters(),
      organizationCountryRegion: "原始地区",
      dealTotalPotentialAmountMin: "0",
    };
    const updateFilter = vi.fn();
    render(
      variant === "advanced" ? (
        <PipelineAdvancedFilters filters={filters} updateFilter={updateFilter} />
      ) : (
        <PipelineSignalFilters filters={filters} updateFilter={updateFilter} onSignalsChange={vi.fn()} />
      ),
    );
    expect(
      screen.getByText(
        variant === "advanced"
          ? "Organizations, regional phases, rights and milestones"
          : "Clinical results and deal signals",
      ),
    ).toBeInTheDocument();
    act(() => setLocale("zh-CN"));
    expect(
      screen.getByText(variant === "advanced" ? "机构、区域阶段、权益与里程碑" : "临床结果与交易信号"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(variant === "advanced" ? "机构所在地区" : "潜在总额下限")).toHaveValue(
      variant === "advanced" ? "原始地区" : 0,
    );
    expect(updateFilter).not.toHaveBeenCalled();
  },
);

it("subscribes date control labels while preserving the supplied group name and literal dates", () => {
  setLocale("en");
  const onFromChange = vi.fn(),
    onToChange = vi.fn();
  render(
    <PipelineDateRange
      label="原始 source group"
      from="2026-01-02"
      to="2026-02-03"
      onFromChange={onFromChange}
      onToChange={onToChange}
    />,
  );
  expect(screen.getByLabelText("From")).toHaveValue("2026-01-02");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("group", { name: "原始 source group" })).toBeInTheDocument();
  expect(screen.getByLabelText("起")).toHaveValue("2026-01-02");
  expect(screen.getByLabelText("止")).toHaveValue("2026-02-03");
  expect(onFromChange).not.toHaveBeenCalled();
  expect(onToChange).not.toHaveBeenCalled();
});
