import { BarChart } from "echarts/charts";
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { type EChartsType, init, use } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef } from "react";

import type { PipelineLandscapeBucketRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { localizedDevelopmentPhase } from "../lib/i18n/programVocabulary";
import { phaseDisplayOrder as phaseOrder } from "../lib/phasePresentation";
import { chartPalette } from "./chartPalette";
import { landscapeTooltip } from "./pipelineLandscape/tooltip";

use([BarChart, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, SVGRenderer]);

const phaseColors: Record<string, string> = {
  approved: chartPalette.phase.approved,
  filed: chartPalette.phase.filed,
  phase_3: chartPalette.phase.phase3,
  phase_2_3: chartPalette.phase.phase23,
  phase_2: chartPalette.phase.phase2,
  phase_1_2: chartPalette.phase.phase12,
  phase_1: chartPalette.phase.phase1,
  early_phase_1: chartPalette.trialPhase.earlyPhase1,
  unknown: chartPalette.phase.missing,
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
  const { locale } = useLocale();
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
          return bucket ? landscapeTooltip(bucket, locale) : "";
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
            name: localizedDevelopmentPhase(phase, true),
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
  }, [buckets, onSelect, locale]);

  return <div className="landscape-bar-chart" ref={containerRef} role="img" aria-label={ariaLabel} />;
}
