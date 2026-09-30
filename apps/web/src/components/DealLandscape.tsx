import { BarChart3, CircleDollarSign, Flag, List, Network, Route } from "lucide-react";
import { lazy, Suspense } from "react";

import type { DealAnalysisDimension, DealAnalysisLimit, DealAnalysisView } from "../lib/contracts/deals";
import type { DealLandscapeBucketRead, DealLandscapeRead } from "../lib/generated";

const LandscapeBarChart = lazy(() =>
  import("./LandscapeBarChart").then((module) => ({ default: module.LandscapeBarChart })),
);

export type DealLandscapeFilterField =
  | "dealType"
  | "status"
  | "direction"
  | "territory"
  | "currency"
  | "assetModality"
  | "developmentPhaseAtTransaction"
  | "currentDevelopmentPhase"
  | "partyCountryRegion"
  | "rightsTerritory";

const dimensionOptions: Array<{ value: DealAnalysisDimension; label: string }> = [
  { value: "all", label: "全部维度" },
  { value: "deal_type", label: "交易类型" },
  { value: "status", label: "交易状态" },
  { value: "direction", label: "交易方向" },
  { value: "territory", label: "交易地区" },
  { value: "currency", label: "披露币种" },
  { value: "asset_modality", label: "资产模态" },
  { value: "transaction_phase", label: "交易时阶段" },
  { value: "current_phase", label: "当前最高阶段" },
  { value: "party_country", label: "参与方地区" },
  { value: "rights_territory", label: "权益地区" },
];

const statusLabels: Record<string, string> = {
  announced: "已披露",
  active: "进行中",
  completed: "已完成",
  terminated: "已终止",
  withdrawn: "已撤回",
  superseded: "已替代",
  unknown: "未知",
};
const directionLabels: Record<string, string> = {
  domestic: "境内",
  inbound: "引进",
  outbound: "对外授权",
  cross_border: "跨境",
  global: "全球",
  undisclosed: "未披露",
};
const phaseLabels: Record<string, string> = {
  discovery: "发现",
  preclinical: "临床前",
  ind: "IND",
  phase_1: "I 期",
  phase_1_2: "I/II 期",
  phase_2: "II 期",
  phase_2_3: "II/III 期",
  phase_3: "III 期",
  filed: "申报",
  approved: "已批准",
  discontinued: "终止",
};

function labeledBuckets(buckets: DealLandscapeBucketRead[], labels?: Record<string, string>) {
  return buckets.map((bucket) => ({
    ...bucket,
    label: bucket.key === "__missing__" ? "未披露" : (labels?.[bucket.key] ?? bucket.label),
  }));
}

function Distribution({
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
                  正在绘制分布
                </div>
              }
            >
              <LandscapeBarChart
                buckets={buckets}
                ariaLabel={`${title}交易数量分布`}
                onSelect={(bucket) => onFilter(filterField, bucket.key)}
              />
            </Suspense>
          ) : (
            <section className="pipeline-analysis-table-wrap" aria-label={`${title}统计表滚动区域`}>
              <table className="pipeline-analysis-table" aria-label={`${title}统计表`}>
                <thead>
                  <tr>
                    <th scope="col">排名</th>
                    <th scope="col">分类</th>
                    <th scope="col">交易数</th>
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
                          disabled={bucket.key === "__missing__"}
                          onClick={() => onFilter(filterField, bucket.key)}
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
        <p className="pipeline-landscape-missing" role="status" aria-live="polite" aria-atomic="true">
          当前授权命中集没有可统计的该维度数据。
        </p>
      )}
    </section>
  );
}

export function DealLandscape({
  landscape,
  dimension,
  view,
  limit,
  onFilter,
  onAnalysisChange,
}: {
  landscape: DealLandscapeRead;
  dimension: DealAnalysisDimension;
  view: DealAnalysisView;
  limit: DealAnalysisLimit;
  onFilter: (field: DealLandscapeFilterField, value: string) => void;
  onAnalysisChange: (next: {
    dimension: DealAnalysisDimension;
    view: DealAnalysisView;
    limit: DealAnalysisLimit;
  }) => void;
}) {
  const distributions = [
    {
      dimension: "deal_type" as const,
      title: "交易类型",
      detail: "按当前授权命中集中的受治理交易类型聚合",
      buckets: labeledBuckets(landscape.deal_type ?? []),
      filterField: "dealType" as const,
    },
    {
      dimension: "status" as const,
      title: "交易状态",
      detail: "按当前交易生命周期状态聚合",
      buckets: labeledBuckets(landscape.status ?? [], statusLabels),
      filterField: "status" as const,
    },
    {
      dimension: "direction" as const,
      title: "交易方向",
      detail: "方向基于治理后的参照地区口径",
      buckets: labeledBuckets(landscape.direction ?? [], directionLabels),
      filterField: "direction" as const,
    },
    {
      dimension: "territory" as const,
      title: "交易地区",
      detail: "交易地区与权益地区保持不同口径",
      buckets: labeledBuckets(landscape.territory ?? []),
      filterField: "territory" as const,
    },
    {
      dimension: "currency" as const,
      title: "披露币种",
      detail: "仅统计来源披露币种，不换算未披露金额",
      buckets: labeledBuckets(landscape.currency ?? []),
      filterField: "currency" as const,
    },
    {
      dimension: "asset_modality" as const,
      title: "资产模态",
      detail: "同一交易可关联多个资产模态，占比可能重叠",
      buckets: labeledBuckets(landscape.asset_modality ?? []),
      filterField: "assetModality" as const,
    },
    {
      dimension: "transaction_phase" as const,
      title: "交易时阶段",
      detail: "按交易发生时的结构化资产阶段聚合",
      buckets: labeledBuckets(landscape.transaction_phase ?? [], phaseLabels),
      filterField: "developmentPhaseAtTransaction" as const,
    },
    {
      dimension: "current_phase" as const,
      title: "当前最高阶段",
      detail: "按当前数据时点的权威管线阶段聚合",
      buckets: labeledBuckets(landscape.current_phase ?? [], phaseLabels),
      filterField: "currentDevelopmentPhase" as const,
    },
    {
      dimension: "party_country" as const,
      title: "参与方地区",
      detail: "同一交易可包含多个参与方地区，占比可能重叠",
      buckets: labeledBuckets(landscape.party_country ?? []),
      filterField: "partyCountryRegion" as const,
    },
    {
      dimension: "rights_territory" as const,
      title: "权益地区",
      detail: "按结构化交易权益记录聚合，不从摘要推断",
      buckets: labeledBuckets(landscape.rights_territory ?? []),
      filterField: "rightsTerritory" as const,
    },
  ];
  const visible = dimension === "all" ? distributions : distributions.filter((item) => item.dimension === dimension);

  return (
    <section className="pipeline-landscape deal-landscape" aria-label="交易数据统计">
      <dl className="pipeline-landscape-kpis">
        <div>
          <BarChart3 size={17} />
          <dt>交易</dt>
          <dd>{landscape.total_deals}</dd>
        </div>
        <div>
          <Network size={17} />
          <dt>交易类型</dt>
          <dd>{(landscape.deal_type ?? []).filter((bucket) => bucket.key !== "__missing__").length}</dd>
        </div>
        <div>
          <Route size={17} />
          <dt>交易方向</dt>
          <dd>{(landscape.direction ?? []).filter((bucket) => bucket.key !== "__missing__").length}</dd>
        </div>
        <div>
          <Flag size={17} />
          <dt>参与方地区</dt>
          <dd>{(landscape.party_country ?? []).length}</dd>
        </div>
        <div>
          <CircleDollarSign size={17} />
          <dt>披露币种</dt>
          <dd>{(landscape.currency ?? []).filter((bucket) => bucket.key !== "__missing__").length}</dd>
        </div>
      </dl>

      <fieldset className="pipeline-analysis-toolbar">
        <legend className="sr-only">交易统计分析控制</legend>
        <label>
          <span>分析维度</span>
          <select
            aria-label="交易分析维度"
            value={dimension}
            onChange={(event) =>
              onAnalysisChange({ dimension: event.target.value as DealAnalysisDimension, view, limit })
            }
          >
            {dimensionOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="segmented-control">
          <legend className="sr-only">交易分析展示方式</legend>
          <button
            type="button"
            aria-pressed={view === "chart"}
            onClick={() => onAnalysisChange({ dimension, view: "chart", limit })}
          >
            <BarChart3 size={14} />
            图表
          </button>
          <button
            type="button"
            aria-pressed={view === "table"}
            onClick={() => onAnalysisChange({ dimension, view: "table", limit })}
          >
            <List size={14} />
            表格
          </button>
        </fieldset>
        <label>
          <span>显示范围</span>
          <select
            aria-label="交易分析显示范围"
            value={limit}
            onChange={(event) =>
              onAnalysisChange({ dimension, view, limit: Number(event.target.value) as DealAnalysisLimit })
            }
          >
            <option value={5}>Top 5</option>
            <option value={8}>Top 8</option>
            <option value={20}>Top 20</option>
            <option value={50}>Top 50</option>
          </select>
        </label>
        <output aria-live="polite">
          {dimensionOptions.find((option) => option.value === dimension)?.label} · {view === "chart" ? "图表" : "表格"}
          {" · "}Top {limit}
        </output>
      </fieldset>

      <div className={`pipeline-landscape-grid${dimension !== "all" ? " pipeline-landscape-grid-focused" : ""}`}>
        {visible.map((distribution) => (
          <Distribution
            key={distribution.dimension}
            title={distribution.title}
            detail={distribution.detail}
            buckets={distribution.buckets}
            filterField={distribution.filterField}
            view={view}
            onFilter={onFilter}
          />
        ))}
      </div>
      <footer className="pipeline-landscape-note">
        <BarChart3 size={15} />
        <span>统计基于当前授权查询的完整命中集；多资产和多参与方维度可重叠，未披露不会推断。</span>
      </footer>
    </section>
  );
}
