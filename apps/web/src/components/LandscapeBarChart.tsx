import { BarChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { type EChartsType, init, use } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

import type { PipelineLandscapeBucketRead } from "../lib/generated";
import { chartPalette } from "./chartPalette";

use([BarChart, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, SVGRenderer]);

const phaseOrder = [
  "approved",
  "filed",
  "phase_3",
  "phase_2_3",
  "phase_2",
  "phase_1_2",
  "phase_1",
  "ind",
  "preclinical",
  "discovery",
  "discontinued",
  "__missing__",
] as const;
const phaseLabels: Record<string, string> = {
  approved: "已批准",
  filed: "申报",
  phase_3: "III 期",
  phase_2_3: "II/III 期",
  phase_2: "II 期",
  phase_1_2: "I/II 期",
  phase_1: "I 期",
  ind: "IND",
  preclinical: "临床前",
  discovery: "发现",
  discontinued: "终止",
  __missing__: "未披露",
};
const phaseColors: Record<string, string> = {
  approved: chartPalette.phase.approved,
  filed: chartPalette.phase.filed,
  phase_3: chartPalette.phase.phase3,
  phase_2_3: chartPalette.phase.phase23,
  phase_2: chartPalette.phase.phase2,
  phase_1_2: chartPalette.phase.phase12,
  phase_1: chartPalette.phase.phase1,
  ind: chartPalette.phase.ind,
  preclinical: chartPalette.phase.preclinical,
  discovery: chartPalette.phase.discovery,
  discontinued: chartPalette.phase.discontinued,
  __missing__: chartPalette.phase.missing,
};

export function LandscapeBarChart({
  buckets,
  ariaLabel,
  onSelect,
}: {
  buckets: PipelineLandscapeBucketRead[];
  ariaLabel: string;
  onSelect?: (bucket: PipelineLandscapeBucketRead) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || buckets.length === 0 || container.clientWidth === 0 || container.clientHeight === 0) return;

    const chart: EChartsType = init(container, undefined, { renderer: "svg" });
    const visible = [...buckets];
    const phases = phaseOrder.filter((phase) => visible.some((bucket) => (bucket.phase_counts?.[phase] ?? 0) > 0));
    const stacked = phases.length > 0;
    const endPercent = visible.length > 15 ? Math.max(4, (15 / visible.length) * 100) : 100;
    chart.setOption({
      animation: false,
      grid: { left: 112, right: visible.length > 15 ? 42 : 20, top: stacked ? 38 : 8, bottom: 26 },
      legend: stacked
        ? {
            top: 0,
            type: "scroll",
            textStyle: { color: chartPalette.axis, fontSize: 10 },
            itemWidth: 10,
            itemHeight: 7,
          }
        : undefined,
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const item = params as { name?: string; value?: number; dataIndex?: number };
          const bucket = visible[item.dataIndex ?? -1];
          const phaseDetails = bucket
            ? Object.entries(bucket.phase_counts ?? {})
                .filter(([, count]) => count > 0)
                .map(([phase, count]) => `${phaseLabels[phase] ?? phase}: ${count}`)
                .join("<br/>")
            : "";
          return bucket
            ? [
                `${bucket.label}<br/>${bucket.count} 个项目 · ${(bucket.share * 100).toFixed(1)}%`,
                phaseDetails ? `<br/>${phaseDetails}` : "",
              ].join("")
            : `${item.name ?? ""}: ${item.value ?? 0}`;
        },
      },
      xAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { color: chartPalette.axis },
        splitLine: { lineStyle: { color: chartPalette.grid } },
      },
      yAxis: {
        type: "category",
        data: visible.map((bucket) => bucket.label),
        inverse: true,
        axisLabel: { color: chartPalette.axisLabel, overflow: "truncate", width: 100 },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      dataZoom:
        visible.length > 15
          ? [{ type: "slider", yAxisIndex: 0, start: 0, end: endPercent, right: 3, width: 12 }]
          : undefined,
      series: stacked
        ? phases.map((phase) => ({
            name: phaseLabels[phase],
            type: "bar",
            stack: "phase",
            data: visible.map((bucket) => bucket.phase_counts?.[phase] ?? 0),
            barMaxWidth: 18,
            itemStyle: { color: phaseColors[phase] },
          }))
        : [
            {
              type: "bar",
              data: visible.map((bucket) => bucket.count),
              barMaxWidth: 18,
              itemStyle: { color: chartPalette.primary, borderRadius: [0, 2, 2, 0] },
              emphasis: { itemStyle: { color: chartPalette.primaryEmphasis } },
            },
          ],
    });

    if (onSelect) {
      chart.on("click", (params: { dataIndex?: number }) => {
        const bucket = visible[params.dataIndex ?? -1];
        if (bucket && bucket.key !== "__missing__") onSelect(bucket);
      });
    }
    const resize = () => chart.resize();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(container);
    window.addEventListener("resize", resize);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [buckets, onSelect]);

  return <div className="landscape-bar-chart" ref={containerRef} role="img" aria-label={ariaLabel} />;
}
