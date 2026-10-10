import { governanceQualityText as t } from "../../lib/i18n/governanceQuality";
import { EmptyState, StatusBadge } from "../common";
import { ScrollableTableRegion } from "../ScrollableTableRegion";
import { QualityQueryFeedback } from "./QualityQueryFeedback";
import { QualityRawRecord } from "./QualityRawRecord";
import { qualityPercent, qualityReportedValue } from "./qualityMetricPresentation";
import type { QualityReads } from "./useQualityReads";
export function QualitySourceCoverage({ reads }: { reads: QualityReads }) {
  const data = reads.coverageData;
  return (
    <section className="quality-source-coverage" aria-labelledby="quality-source-coverage-title">
      <header>
        <div>
          <h3 id="quality-source-coverage-title">{t("来源覆盖与授权")}</h3>
          <p>{t("按数据集查看解析缺口、事实发布、冲突、新鲜度、失败 SLA 和责任人。")}</p>
        </div>
        {data ? <small>{t("已读取 {count} 个来源", { count: data.length })}</small> : null}
      </header>
      <QualityQueryFeedback query={reads.coverage} label={t("正在读取来源覆盖")} cached={Boolean(data)} />
      {data?.length ? (
        <ScrollableTableRegion className="quality-table-scroll" ariaLabel={t("来源覆盖与授权滚动区域")}>
          <table aria-label={t("来源覆盖与授权")}>
            <thead>
              <tr>
                <th>{t("来源 / 数据集")}</th>
                <th>{t("解析覆盖")}</th>
                <th>{t("事实发布")}</th>
                <th>{t("新鲜度")}</th>
                <th>{t("授权")}</th>
                <th>{t("失败SLA")}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((source) => (
                <tr key={source.source_id}>
                  <td>
                    <strong>{source.name}</strong>
                    <small>
                      {source.dataset_key} · {source.owner}
                    </small>
                    <QualityRawRecord title={t("来源完整记录")} value={source} />
                  </td>
                  <td>
                    <strong>{qualityPercent(source.parse_coverage)}</strong>
                    <small>
                      {source.parsed_asset_count}/{source.active_asset_count} ·{" "}
                      {t("缺 {count}", { count: source.parse_missing_count })}
                    </small>
                  </td>
                  <td>
                    <strong>{qualityPercent(source.published_fact_coverage)}</strong>
                    <small>
                      {source.published_fact_count}/{source.fact_count} · {t("冲突")}{" "}
                      {qualityPercent(source.conflict_rate)}
                    </small>
                  </td>
                  <td>
                    <StatusBadge value={source.freshness_status} />
                    <small>
                      {source.freshness_age_seconds == null
                        ? t("未上报")
                        : qualityReportedValue(source.freshness_age_seconds) + "s"}
                    </small>
                  </td>
                  <td>
                    <StatusBadge value={source.authorization_status} />
                    <small>
                      {source.authorization_scopes.length ? source.authorization_scopes.join(", ") : t("无授权范围")}
                    </small>
                  </td>
                  <td>
                    <StatusBadge value={source.failure_sla_status} />
                    <small>{t("{count} 次连续失败", { count: source.consecutive_failures })}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : reads.coverage.isSuccess ? (
        <EmptyState title={t("尚无注册来源")} detail={t("来源接入后将在这里显示质量和授权状态。")} />
      ) : null}
    </section>
  );
}
