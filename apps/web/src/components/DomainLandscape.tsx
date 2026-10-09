import { lazy, Suspense } from "react";
import { formattingLocale, useLocale } from "../lib/i18n";
import { domainLandscapeText as t } from "../lib/i18n/domainLandscape";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

const LandscapeBarChart = lazy(() =>
  import("./LandscapeBarChart").then((module) => ({ default: module.LandscapeBarChart })),
);

export type DomainAnalysisView = "chart" | "table";

export interface DomainLandscapeBucket {
  key: string;
  label: string;
  count: number;
  share: number;
}

export interface DomainLandscapeSection<FilterField extends string> {
  id: string;
  title: string;
  detail: string;
  buckets: DomainLandscapeBucket[];
  /** null renders a read-only distribution without drill-down. */
  filterField: FilterField | null;
}

function Distribution<FilterField extends string>({
  section,
  unitLabel,
  domainId,
  view,
  onFilter,
}: {
  section: DomainLandscapeSection<FilterField>;
  unitLabel: string;
  domainId: string;
  view: DomainAnalysisView;
  onFilter: (field: FilterField, value: string) => void;
}) {
  useLocale();
  const { id, title, detail, buckets, filterField } = section;
  return (
    <section
      className="pipeline-landscape-distribution"
      data-view={view}
      aria-labelledby={`${domainId}-landscape-${id}`}
    >
      <header>
        <h3 id={`${domainId}-landscape-${id}`}>{title}</h3>
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
                ariaLabel={t("{title}{unit}分布", { title, unit: unitLabel })}
                onSelect={
                  filterField
                    ? (bucket) => {
                        if (bucket.key !== "__missing__") onFilter(filterField, bucket.key);
                      }
                    : undefined
                }
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
                    <th scope="col">{unitLabel}</th>
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
                          disabled={!filterField || bucket.key === "__missing__"}
                          onClick={() => filterField && onFilter(filterField, bucket.key)}
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
        <p className="landscape-empty" role="status" aria-live="polite" aria-atomic="true">
          {t("当前查询没有可统计的记录。")}
        </p>
      )}
    </section>
  );
}

export function DomainLandscape<FilterField extends string>({
  domainId,
  ariaLabel,
  total,
  totalUnit,
  unitLabel,
  sections,
  view,
  onViewChange,
  onFilter,
}: {
  domainId: string;
  ariaLabel: string;
  total: number;
  totalUnit: string;
  unitLabel: string;
  sections: DomainLandscapeSection<FilterField>[];
  view: DomainAnalysisView;
  onViewChange: (view: DomainAnalysisView) => void;
  onFilter: (field: FilterField, value: string) => void;
}) {
  useLocale();
  return (
    <section className="trial-landscape" aria-label={ariaLabel}>
      <header className="trial-landscape-summary">
        <div>
          <span>{t("完整命中集")}</span>
          <strong>{total.toLocaleString(formattingLocale())}</strong>
          <small>{totalUnit}</small>
        </div>
        <p>{t("统计与当前筛选、租户授权和数据时点一致，不受当前分页影响。")}</p>
        <fieldset className="segmented-control trial-landscape-view-toggle">
          <legend className="sr-only">{t("统计展示方式")}</legend>
          <button type="button" aria-pressed={view === "chart"} onClick={() => onViewChange("chart")}>
            {t("图示")}
          </button>
          <button type="button" aria-pressed={view === "table"} onClick={() => onViewChange("table")}>
            {t("列表")}
          </button>
        </fieldset>
      </header>
      {sections.map((section) => (
        <Distribution
          key={section.id}
          section={section}
          unitLabel={unitLabel}
          domainId={domainId}
          view={view}
          onFilter={onFilter}
        />
      ))}
    </section>
  );
}
