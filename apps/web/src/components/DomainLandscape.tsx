import { lazy, Suspense } from "react";

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
                  正在绘制分布
                </div>
              }
            >
              <LandscapeBarChart
                buckets={buckets}
                ariaLabel={`${title}${unitLabel}分布`}
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
            <section className="pipeline-analysis-table-wrap" aria-label={`${title}统计表滚动区域`}>
              <table className="pipeline-analysis-table" aria-label={`${title}统计表`}>
                <thead>
                  <tr>
                    <th scope="col">排名</th>
                    <th scope="col">分类</th>
                    <th scope="col">{unitLabel}</th>
                    <th scope="col">占比</th>
                    <th scope="col">操作</th>
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
                          筛选
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </div>
      ) : (
        <p className="landscape-empty" role="status" aria-live="polite" aria-atomic="true">
          当前查询没有可统计的记录。
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
  return (
    <section className="trial-landscape" aria-label={ariaLabel}>
      <header className="trial-landscape-summary">
        <div>
          <span>完整命中集</span>
          <strong>{total.toLocaleString()}</strong>
          <small>{totalUnit}</small>
        </div>
        <p>统计与当前筛选、租户授权和数据时点一致，不受当前分页影响。</p>
        <fieldset className="segmented-control trial-landscape-view-toggle">
          <legend className="sr-only">统计展示方式</legend>
          <button type="button" aria-pressed={view === "chart"} onClick={() => onViewChange("chart")}>
            图示
          </button>
          <button type="button" aria-pressed={view === "table"} onClick={() => onViewChange("table")}>
            列表
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
