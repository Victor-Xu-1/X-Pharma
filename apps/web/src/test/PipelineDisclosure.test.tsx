import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { emptyPipelineSearchFilters, type PipelineSearchFilters } from "../lib/contracts/pipeline";
import { setLocale, useLocale } from "../lib/i18n";
import { PipelineAdvancedFilters } from "../views/pipeline/PipelineAdvancedFilters";
import { PipelineSignalFilters } from "../views/pipeline/PipelineSignalFilters";

it.each(["advanced", "signals"] as const)(
  "retains the %s disclosure when its last selected condition is cleared",
  async (variant) => {
    function Harness() {
      useLocale();
      const [filters, setFilters] = useState(emptyPipelineSearchFilters);
      function updateFilter<Key extends keyof PipelineSearchFilters>(key: Key, value: PipelineSearchFilters[Key]) {
        setFilters((current) => ({ ...current, [key]: value }));
      }
      return variant === "advanced" ? (
        <PipelineAdvancedFilters filters={filters} updateFilter={updateFilter} />
      ) : (
        <PipelineSignalFilters
          filters={filters}
          updateFilter={updateFilter}
          onSignalsChange={(changes) => setFilters((current) => ({ ...current, ...changes }))}
        />
      );
    }
    render(<Harness />);
    const label = variant === "advanced" ? "机构、区域阶段、权益与里程碑" : "临床结果与交易信号";
    const panel = screen.getByText(label).closest("details");
    if (!panel) throw new Error("Complete pipeline disclosure required");
    expect(panel).not.toHaveAttribute("open");
    await act(async () => {
      panel.open = true;
      fireEvent(panel, new Event("toggle"));
    });
    const input =
      variant === "advanced"
        ? within(screen.getByRole("group", { name: "全球阶段起始日期" })).getByLabelText("起")
        : screen.getByLabelText("是否存在交易记录");
    fireEvent.change(input, { target: { value: variant === "advanced" ? "2026-01-02" : "false" } });
    expect(panel).toHaveAttribute("open");
    act(() => setLocale("en"));
    expect(input).toHaveValue(variant === "advanced" ? "2026-01-02" : "false");
    fireEvent.change(input, { target: { value: "" } });
    expect(panel).toHaveAttribute("open");
    expect(input).toHaveValue("");
    expect(panel.querySelector(".pipeline-advanced-grid")).not.toBeNull();
    expect(panel).toHaveAttribute("data-active-count", "0");
  },
);
