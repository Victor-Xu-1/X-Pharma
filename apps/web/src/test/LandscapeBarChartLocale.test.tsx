import { act, render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { DomainLandscape } from "../components/DomainLandscape";
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

it("uses the caller's record unit rather than inventing development programs for a domain distribution", () => {
  const buckets = [{ key: "publication", label: "原始论文类型", count: 0, share: 0 }];
  const view = render(<LandscapeBarChart ariaLabel="Updates" buckets={buckets} unitLabel="updates" />);
  let tooltip = chart.setOption.mock.lastCall?.[0].tooltip.formatter({ dataIndex: 0 });
  expect(tooltip).toContain("0 updates");
  expect(tooltip).not.toContain("programs");
  act(() => setLocale("zh-CN"));
  view.rerender(<LandscapeBarChart ariaLabel="Updates" buckets={buckets} unitLabel="条动态" />);
  tooltip = chart.setOption.mock.lastCall?.[0].tooltip.formatter({ dataIndex: 0 });
  expect(tooltip).toContain("0 条动态");
  expect(tooltip).not.toContain("项目");
  view.rerender(
    <LandscapeBarChart ariaLabel="Updates" buckets={buckets} unitLabel={'<img src=x onerror="alert(1)">'} />,
  );
  tooltip = chart.setOption.mock.lastCall?.[0].tooltip.formatter({ dataIndex: 0 });
  expect(tooltip).toContain("&lt;img");
  expect(tooltip).not.toContain("<img");
  expect(buckets[0]).toEqual({ key: "publication", label: "原始论文类型", count: 0, share: 0 });
});

it("passes the domain unit through the lazy statistics chart without rewriting source buckets", async () => {
  const buckets = [{ key: "publication", label: "原始论文类型", count: 1, share: 1 }];
  render(
    <DomainLandscape
      domainId="news"
      ariaLabel="Updates"
      total={1}
      totalUnit="updates"
      unitLabel="updates"
      sections={[{ id: "type", title: "Type", detail: "", buckets, filterField: "type" }]}
      view="chart"
      onViewChange={vi.fn()}
      onFilter={vi.fn()}
    />,
  );
  await screen.findByRole("img", { name: "Type updates distribution" });
  expect(chart.setOption.mock.lastCall?.[0].tooltip.formatter({ dataIndex: 0 })).toContain("1 updates");
  expect(buckets[0]).toEqual({ key: "publication", label: "原始论文类型", count: 1, share: 1 });
});
