import { useState } from "react";
import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { EmptyState, formatDate } from "../common";
import { ScrollableTableRegion } from "../ScrollableTableRegion";
import { QualityRawRecord } from "./QualityRawRecord";
import { qualityMetricKeys, qualityMetricLabel, qualityMetricValue } from "./qualityMetricPresentation";
import type { QualityReads } from "./useQualityReads";
export function QualityHistory({ reads }: { reads: QualityReads }) {
  const [all, setAll] = useState(false);
  const data = reads.snapshotData;
  const trend = [...(all ? (data ?? []) : (data ?? []).slice(0, 12))].reverse();
  const metrics = trend.reduce<Record<string, Record<string, unknown>>>(
    (all, snapshot) => ({ ...all, ...snapshot.metrics }),
    {},
  );
  const keys = qualityMetricKeys(metrics);
  const latest = data?.[0];
  return (
    <section className="quality-trend" aria-labelledby="quality-trend-title">
      <header>
        <h3 id="quality-trend-title">{t("最近 {count} 次趋势", { count: all ? (data?.length ?? 0) : 12 })}</h3>
        <small>{latest ? t("最近评估") + " " + formatDate(latest.measured_at, true) : t("等待首个快照")}</small>
      </header>
      {trend.length ? (
        <>
          <ScrollableTableRegion className="quality-table-scroll" ariaLabel={t("数据质量历史趋势滚动区域")}>
            <table aria-label={t("数据质量历史趋势")}>
              <thead>
                <tr>
                  <th>{t("评估时间")}</th>
                  {keys.map((key) => (
                    <th key={key}>{qualityMetricLabel(key, metrics[key])}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {trend.map((snapshot) => (
                  <tr key={snapshot.id}>
                    <td>{formatDate(snapshot.measured_at, true)}</td>
                    {keys.map((key) => (
                      <td key={key}>
                        {snapshot.metrics[key]?.applicable === false
                          ? t("不适用")
                          : qualityMetricValue(key, snapshot.metrics[key]?.value)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          {data && data.length > 12 ? (
            <button type="button" className="secondary-button" onClick={() => setAll(!all)}>
              {all ? t("显示最近12次") : t("显示全部已读取的 {count} 次评估", { count: data.length })}
            </button>
          ) : null}
          <QualityRawRecord title={t("原始快照记录")} value={trend} />
        </>
      ) : reads.snapshots.isSuccess ? (
        <EmptyState title={t("趋势尚未建立")} detail={t("评估后按时间呈现质量变化。")} />
      ) : null}
    </section>
  );
}
