import { render } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TrendLineChart } from "../components/TrendLineChart";
import { trendTooltip } from "../components/trendLineChart/tooltip";
import { setLocale } from "../lib/i18n";

const { setOption } = vi.hoisted(() => ({ setOption: vi.fn() }));
vi.mock("echarts/core", () => ({
  use: vi.fn(),
  init: vi.fn(() => ({ setOption, resize: vi.fn(), dispose: vi.fn() })),
}));

it("does not round a sub-milliscale observation to zero in the chart tooltip", () => {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(400);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(240);
  setLocale("en");
  render(
    <TrendLineChart
      points={[{ label: "2025", axisLabel: "01/01/2025\n– 12/31/2025", value: 0.000123456 }]}
      valueLabel="patients"
      ariaLabel="Controlled precision fixture"
    />,
  );
  const options = setOption.mock.calls[0]?.[0] as {
    tooltip: { trigger: string; confine: boolean; formatter: (value: unknown) => HTMLElement };
    xAxis: { data: string[] };
  };
  expect(options.tooltip.trigger).toBe("item");
  expect(options.tooltip.confine).toBe(true);
  expect(options.xAxis.data).toEqual(["01/01/2025\n– 12/31/2025"]);
  const tooltip = options.tooltip.formatter({ dataIndex: 0 });
  expect(tooltip).toHaveTextContent("2025");
  expect(tooltip).toHaveTextContent("0.000123456");
  expect(tooltip).toHaveTextContent("patients");
});

it("keeps source-owned tooltip labels as inert text rather than interpreting HTML", () => {
  const label = '<img src="unrequested" onerror="alert(1)">原始观测';
  const unit = "<script>RAW_UNIT</script>";
  const tooltip = trendTooltip({ label, value: 0 }, unit);
  expect(tooltip).toHaveTextContent(label);
  expect(tooltip).toHaveTextContent(unit);
  expect(tooltip).toHaveTextContent("0");
  expect(tooltip.querySelector("img,script")).toBeNull();
});
