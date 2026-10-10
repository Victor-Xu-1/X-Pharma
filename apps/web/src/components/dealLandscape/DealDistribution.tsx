import { lazy, Suspense } from "react";
import type { DealAnalysisView } from "../../lib/contracts/deals";
import type { DealLandscapeBucketRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";
import { domainLandscapeText } from "../../lib/i18n/domainLandscape";
import type { DealLandscapeFilterField } from "../DealLandscape";
import { ScrollableTableRegion } from "../ScrollableTableRegion";

const LandscapeBarChart = lazy(() =>
  import("../LandscapeBarChart").then((module) => ({ default: module.LandscapeBarChart })),
);
export function DealDistribution({
  title,
  detail,
  buckets,
  filterField,
  view,
  onFilter,
}: {
  title: string;
  detail: string;
  buckets: DealLandscapeBucketRead[];
  filterField: DealLandscapeFilterField;
  view: DealAnalysisView;
  onFilter: (field: DealLandscapeFilterField, value: string) => void;
}) {
  useLocale();
  return (
    <section
      className="pipeline-landscape-distribution"
      data-view={view}
      aria-labelledby={`deal-landscape-${filterField}`}
    >
      <header>
        <h3 id={`deal-landscape-${filterField}`}>{title}</h3>
        <p>{detail}</p>
      </header>
      {buckets.length ? (
        <div className="pipeline-landscape-distribution-body">
          {view === "chart" ? (
            <Suspense
              fallback={
                <div className="landscape-chart-loading" role="status" aria-live="polite" aria-atomic="true">
                  {t("正在绘制分布")}
                </div>
              }
            >
              <LandscapeBarChart
                buckets={buckets}
                unitLabel={domainLandscapeText("笔交易")}
                ariaLabel={t("{title}交易数量分布", { title })}
                onSelect={(bucket) => onFilter(filterField, bucket.key)}
              />
            </Suspense>
          ) : (
            <ScrollableTableRegion
              className="pipeline-analysis-table-wrap"
              ariaLabel={t("{title}统计表滚动区域", { title })}
            >
              <table className="pipeline-analysis-table" aria-label={t("{title}统计表", { title })}>
                <thead>
                  <tr>
                    <th scope="col">{t("排名")}</th>
                    <th scope="col">{t("分类")}</th>
                    <th scope="col">{t("交易数")}</th>
                    <th scope="col">{t("占比")}</th>
                    <th scope="col">{t("操作")}</th>
                  </tr>
                </thead>
                <tbody>
                  {buckets.map((bucket, index) => (
                    <tr key={bucket.key}>
                      <td>{index + 1}</td>
                      <th scope="row">{bucket.label}</th>
                      <td>{bucket.count}</td>
                      <td>{(bucket.share * 100).toFixed(1)}%</td>
                      <td>
                        <button
                          type="button"
                          disabled={bucket.key === "__missing__"}
                          onClick={() => onFilter(filterField, bucket.key)}
                        >
                          {t("筛选")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollableTableRegion>
          )}
        </div>
      ) : (
        <p className="pipeline-landscape-missing" role="status" aria-live="polite" aria-atomic="true">
          {t("当前授权命中集没有可统计的该维度数据。")}
        </p>
      )}
    </section>
  );
}
