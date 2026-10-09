import { act, render } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { LandscapeBarChart } from "../components/LandscapeBarChart";
import { setLocale } from "../lib/i18n";

const chart = vi.hoisted(() => ({ setOption: vi.fn(), on: vi.fn(), resize: vi.fn(), dispose: vi.fn() }));
vi.mock("echarts/core", () => ({ init: () => chart, use: vi.fn() }));
beforeEach(() => {
  setLocale("en");
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(480);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(240);
});

it("treats source names and unknown phase keys as text rather than tooltip HTML", () => {
  render(
    <LandscapeBarChart
      ariaLabel="Source distribution"
      buckets={[
        {
          key: "target-1",
          label: '<img src=x onerror="alert(1)">EGFR & 原名',
          count: 1,
          share: 1,
          phase_counts: { '<svg onload="alert(2)">': 1 },
        },
      ]}
    />,
  );
  const option = chart.setOption.mock.lastCall?.[0];
  if (!option) throw new Error("Chart was not configured");
  const tooltip = option.tooltip.formatter({ dataIndex: 0 });
  expect(tooltip).toContain("&lt;img");
  expect(tooltip).toContain("&lt;svg");
  expect(tooltip).toContain("EGFR &amp; 原名");
  expect(tooltip).not.toMatch(/<(img|svg)/);
});

it("updates controlled legend and count captions without changing bucket identity, numbers or click semantics", () => {
  const buckets = [{ key: "target-1", label: "EGFR 原名", count: 1, share: 1, phase_counts: { phase_2: 1 } }];
  const onSelect = vi.fn();
  render(<LandscapeBarChart ariaLabel="Distribution" buckets={buckets} onSelect={onSelect} />);
  const english = chart.setOption.mock.lastCall?.[0];
  expect(english.series[0].name).toBe("Phase II");
  expect(english.tooltip.formatter({ dataIndex: 0 })).toContain("1 programs");
  act(() => setLocale("zh-CN"));
  const chinese = chart.setOption.mock.lastCall?.[0];
  expect(chinese.series[0].name).toBe("II 期");
  expect(chinese.tooltip.formatter({ dataIndex: 0 })).toContain("1 个项目");
  expect(chinese.yAxis.data).toEqual(["EGFR 原名"]);
  chart.on.mock.lastCall?.[1]({ dataIndex: 0 });
  expect(onSelect).toHaveBeenCalledExactlyOnceWith(buckets[0]);
});
