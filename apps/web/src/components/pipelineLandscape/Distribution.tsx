import { ExternalLink } from "lucide-react";
import { lazy, Suspense } from "react";
import type { PipelineAnalysisLimit, PipelineAnalysisView } from "../../lib/contracts/pipeline";
import type { PipelineLandscapeBucketRead } from "../../lib/generated";
import { pipelineLandscapeText as t } from "../../lib/i18n/pipelineLandscape";
import { phaseComposition } from "./presentation";
import type { PipelineLandscapeEntityOpener, PipelineLandscapeFilterField } from "./types";

const LandscapeBarChart = lazy(() =>
  import("../LandscapeBarChart").then((module) => ({ default: module.LandscapeBarChart })),
);
export function Distribution({
  title,
  detail,
  buckets,
  filterField,
  onFilter,
  onOpenEntity,
  view,
  limit,
}: {
  title: string;
  detail: string;
  buckets: PipelineLandscapeBucketRead[];
  filterField: PipelineLandscapeFilterField;
  onFilter: (field: PipelineLandscapeFilterField, value: string, label?: string) => void;
  onOpenEntity?: PipelineLandscapeEntityOpener;
  view: PipelineAnalysisView;
  limit: PipelineAnalysisLimit;
}) {
  const visibleBuckets = buckets.slice(0, limit);
  return (
    <section className="pipeline-landscape-distribution" data-view={view} aria-labelledby={`landscape-${filterField}`}>
      <header>
        <h3 id={`landscape-${filterField}`}>{title}</h3>
        <p>{detail}</p>
      </header>
      {visibleBuckets.length ? (
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
                buckets={visibleBuckets}
                ariaLabel={t("{title}项目数量分布", { title })}
                onSelect={(bucket) => onFilter(filterField, bucket.key, bucket.label)}
              />
            </Suspense>
          ) : null}
          {view === "table" ? (
            <section className="pipeline-analysis-table-wrap" aria-label={t("{title}统计表滚动区域", { title })}>
              <table className="pipeline-analysis-table" aria-label={t("{title}统计表", { title })}>
                <thead>
                  <tr>
                    <th scope="col">{t("排名")}</th>
                    <th scope="col">{t("分类")}</th>
                    <th scope="col">{t("项目数")}</th>
                    <th scope="col">{t("阶段构成")}</th>
                    <th scope="col">{t("占比")}</th>
                    <th scope="col">{t("操作")}</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleBuckets.map((bucket, index) => (
                    <tr key={bucket.key}>
                      <td>{index + 1}</td>
                      <th scope="row">{bucket.label}</th>
                      <td>{bucket.count}</td>
                      <td>{phaseComposition(bucket) || "--"}</td>
                      <td>{(bucket.share * 100).toFixed(1)}%</td>
                      <td>
                        <div className="pipeline-analysis-row-actions">
                          <button
                            type="button"
                            disabled={bucket.key === "__missing__"}
                            onClick={() => onFilter(filterField, bucket.key, bucket.label)}
                          >
                            {t("筛选")}
                          </button>
                          {bucket.entity_id && onOpenEntity ? (
                            <button
                              className="icon-button"
                              type="button"
                              title={t("打开{name}档案", { name: bucket.label })}
                              aria-label={t("打开{name}档案", { name: bucket.label })}
                              onClick={() => onOpenEntity(bucket.entity_id ?? "")}
                            >
                              <ExternalLink size={14} />
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : (
            <ol className="pipeline-landscape-ranking" aria-label={t("{title}排名", { title })}>
              {visibleBuckets.map((bucket) => (
                <li key={bucket.key}>
                  <button
                    type="button"
                    disabled={bucket.key === "__missing__"}
                    onClick={() => onFilter(filterField, bucket.key, bucket.label)}
                    title={t("按{name}筛选", { name: bucket.label })}
                  >
                    <span>{bucket.label}</span>
                    <strong>{bucket.count}</strong>
                    <small>{(bucket.share * 100).toFixed(1)}%</small>
                  </button>
                  {bucket.entity_id && onOpenEntity ? (
                    <button
                      className="icon-button"
                      type="button"
                      title={t("打开{name}档案", { name: bucket.label })}
                      aria-label={t("打开{name}档案", { name: bucket.label })}
                      onClick={() => onOpenEntity(bucket.entity_id ?? "")}
                    >
                      <ExternalLink size={14} />
                    </button>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : (
        <p className="pipeline-landscape-missing" role="status" aria-live="polite" aria-atomic="true">
          {t("当前查询结果中暂无该维度数据。")}
        </p>
      )}
    </section>
  );
}
