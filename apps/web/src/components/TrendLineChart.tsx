import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { type EChartsType, init, use } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

import { chartPalette } from "./chartPalette";

use([LineChart, GridComponent, TooltipComponent, SVGRenderer]);

export interface TrendLinePoint {
  label: string;
  value: number;
  lowerBound?: number | null;
  upperBound?: number | null;
}

export function TrendLineChart({
  points,
  valueLabel,
  ariaLabel,
}: {
  points: TrendLinePoint[];
  valueLabel: string;
  ariaLabel: string;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || points.length === 0 || container.clientWidth === 0 || container.clientHeight === 0) return;

    const chart: EChartsType = init(container, undefined, { renderer: "svg" });
    chart.setOption({
      animation: false,
      grid: { left: 56, right: 18, top: 20, bottom: 42, containLabel: false },
      tooltip: {
        trigger: "axis",
        valueFormatter: (value: unknown) =>
          typeof value === "number" ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value) : "--",
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: points.map((point) => point.label),
        axisLabel: { color: chartPalette.axis, hideOverlap: true },
        axisLine: { lineStyle: { color: chartPalette.axisLine } },
      },
      yAxis: {
        type: "value",
        name: valueLabel,
        nameTextStyle: { color: chartPalette.axis },
        axisLabel: { color: chartPalette.axis },
        splitLine: { lineStyle: { color: chartPalette.grid } },
        scale: true,
      },
      series: [
        {
          name: valueLabel,
          type: "line",
          data: points.map((point) => ({
            value: point.value,
            lowerBound: point.lowerBound,
            upperBound: point.upperBound,
          })),
          symbolSize: 7,
          lineStyle: { color: chartPalette.primary, width: 2 },
          itemStyle: {
            color: chartPalette.primary,
            borderColor: chartPalette.surface,
            borderWidth: 2,
          },
          areaStyle: { color: chartPalette.trendArea },
        },
      ],
    });

    const resize = () => chart.resize();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(container);
    window.addEventListener("resize", resize);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [points, valueLabel]);

  return <div className="trend-line-chart" ref={containerRef} role="img" aria-label={ariaLabel} />;
}
