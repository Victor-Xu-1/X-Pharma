import { BarChart3, Building2, Crosshair, ExternalLink, FlaskConical, Globe2, List, Pill } from "lucide-react";
import { lazy, Suspense } from "react";
import type {
  PipelineAnalysisDimension,
  PipelineAnalysisLimit,
  PipelineAnalysisStageScope,
  PipelineAnalysisView,
  PipelineTargetAggregation,
} from "../lib/contracts/pipeline";
import type { PipelineLandscapeBucketRead, PipelineLandscapeRead } from "../lib/generated";
import { phaseDisplayOrder, spacedPhaseLabels as phaseLabels } from "../lib/phasePresentation";
import { programModalityLabel } from "../lib/programDisplay";

const LandscapeBarChart = lazy(() =>
  import("./LandscapeBarChart").then((module) => ({ default: module.LandscapeBarChart })),
);

export type PipelineLandscapeFilterField =
  | "phase"
  | "globalPhase"
  | "chinaPhase"
  | "targetEntityId"
  | "targetCombinationKey"
  | "diseaseEntityId"
  | "modality"
  | "geography"
  | "organizationEntityId";

type PipelineLandscapeEntityOpener = (entityId: string) => void;

const dimensionOptions: Array<{ value: PipelineAnalysisDimension; label: string }> = [
  { value: "all", label: "全部维度" },
  { value: "global_phase", label: "全球研发阶段" },
  { value: "china_phase", label: "中国研发阶段" },
  { value: "targets", label: "靶点" },
  { value: "target_combinations", label: "靶点组合" },
  { value: "diseases", label: "适应症" },
  { value: "organizations", label: "研发机构" },
  { value: "modality", label: "药物类型" },
  { value: "geography", label: "地区分布" },
];

function labeledPhases(buckets: PipelineLandscapeBucketRead[]) {
  return buckets.map((bucket) => ({ ...bucket, label: phaseLabels[bucket.key] ?? bucket.label }));
}

function labeledModalities(buckets: PipelineLandscapeBucketRead[]) {
  return buckets.map((bucket) => ({ ...bucket, label: programModalityLabel(bucket.label || bucket.key) }));
}

function phaseComposition(bucket: PipelineLandscapeBucketRead) {
  return Object.entries(bucket.phase_counts ?? {})
    .sort(([left], [right]) => phaseDisplayOrder.indexOf(left) - phaseDisplayOrder.indexOf(right))
    .map(([phase, count]) => `${phaseLabels[phase] ?? (phase === "__missing__" ? "未披露" : phase)} ${count}`)
    .join(" · ");
}

function Distribution({
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
                  正在绘制分布
                </div>
              }
            >
              <LandscapeBarChart
                buckets={visibleBuckets}
                ariaLabel={`${title}项目数量分布`}
                onSelect={(bucket) => onFilter(filterField, bucket.key, bucket.label)}
              />
            </Suspense>
          ) : null}
          {view === "table" ? (
            <section className="pipeline-analysis-table-wrap" aria-label={`${title}统计表滚动区域`}>
              <table className="pipeline-analysis-table" aria-label={`${title}统计表`}>
                <thead>
                  <tr>
                    <th scope="col">排名</th>
                    <th scope="col">分类</th>
                    <th scope="col">项目数</th>
                    <th scope="col">阶段构成</th>
                    <th scope="col">占比</th>
                    <th scope="col">操作</th>
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
                            筛选
                          </button>
                          {bucket.entity_id && onOpenEntity ? (
                            <button
                              className="icon-button"
                              type="button"
                              title={`打开${bucket.label}档案`}
                              aria-label={`打开${bucket.label}档案`}
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
            <ol className="pipeline-landscape-ranking" aria-label={`${title}排名`}>
              {visibleBuckets.map((bucket) => (
                <li key={bucket.key}>
                  <button
                    type="button"
                    disabled={bucket.key === "__missing__"}
                    onClick={() => onFilter(filterField, bucket.key, bucket.label)}
                    title={`按${bucket.label}筛选`}
                  >
                    <span>{bucket.label}</span>
                    <strong>{bucket.count}</strong>
                    <small>{(bucket.share * 100).toFixed(1)}%</small>
                  </button>
                  {bucket.entity_id && onOpenEntity ? (
                    <button
                      className="icon-button"
                      type="button"
                      title={`打开${bucket.label}档案`}
                      aria-label={`打开${bucket.label}档案`}
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
          当前查询结果中暂无该维度数据。
        </p>
      )}
    </section>
  );
}

export function PipelineLandscape({
  landscape,
  dimension,
  view,
  limit,
  stageScope,
  targetAggregation,
  onFilter,
  onOpenEntity,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
  onAnalysisChange,
}: {
  landscape: PipelineLandscapeRead;
  dimension: PipelineAnalysisDimension;
  view: PipelineAnalysisView;
  limit: PipelineAnalysisLimit;
  stageScope: PipelineAnalysisStageScope;
  targetAggregation: PipelineTargetAggregation;
  onFilter: (field: PipelineLandscapeFilterField, value: string, label?: string) => void;
  onOpenEntity: PipelineLandscapeEntityOpener;
  onOpenTarget?: PipelineLandscapeEntityOpener;
  onOpenDisease?: PipelineLandscapeEntityOpener;
  onOpenOrganization?: PipelineLandscapeEntityOpener;
  onAnalysisChange: (next: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  }) => void;
}) {
  const targetOpener = onOpenTarget ?? onOpenEntity;
  const diseaseOpener = onOpenDisease ?? onOpenEntity;
  const organizationOpener = onOpenOrganization ?? onOpenEntity;
  const distributions = [
    {
      dimension: "global_phase" as const,
      title: "全球研发阶段",
      detail: "同一筛选条件下各项目的全球最高阶段",
      buckets: labeledPhases(
        (landscape.global_phase ?? []).length ? (landscape.global_phase ?? []) : (landscape.overall_phase ?? []),
      ),
      filterField: (landscape.global_phase ?? []).length ? ("globalPhase" as const) : ("phase" as const),
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "china_phase" as const,
      title: "中国研发阶段",
      detail: "中国阶段独立统计，未披露不会推断",
      buckets: labeledPhases(landscape.china_phase ?? []),
      filterField: "chinaPhase" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "targets" as const,
      title: "靶点",
      detail: "按靶点汇总，可继续筛选或查看靶点详情",
      buckets: landscape.targets ?? [],
      filterField: "targetEntityId" as const,
      openEntity: true,
      entityOpener: targetOpener,
    },
    {
      dimension: "target_combinations" as const,
      title: "靶点组合",
      detail: "按已确认的靶点组合汇总，未明确披露的关系不会自动推断",
      buckets: landscape.target_combinations ?? [],
      filterField: "targetCombinationKey" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "diseases" as const,
      title: "适应症",
      detail: "按适应症汇总，未明确披露的适应症不会自动推断",
      buckets: landscape.diseases ?? [],
      filterField: "diseaseEntityId" as const,
      openEntity: true,
      entityOpener: diseaseOpener,
    },
    {
      dimension: "modality" as const,
      title: "药物类型",
      detail: "按药物类型汇总",
      buckets: labeledModalities(landscape.modality ?? []),
      filterField: "modality" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "geography" as const,
      title: "地区分布",
      detail: "记录地区与权益地区保持不同口径",
      buckets: landscape.geography ?? [],
      filterField: "geography" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "organizations" as const,
      title: "研发机构",
      detail: "按研发机构汇总，可继续筛选或查看公司详情",
      buckets: landscape.organizations ?? [],
      filterField: "organizationEntityId" as const,
      openEntity: true,
      entityOpener: organizationOpener,
    },
  ];
  const visibleDistributions =
    dimension === "all" ? distributions : distributions.filter((item) => item.dimension === dimension);

  return (
    <section className="pipeline-landscape" aria-label="管线竞争格局">
      <dl className="pipeline-landscape-kpis">
        <div>
          <BarChart3 size={17} />
          <dt>研发项目</dt>
          <dd>{landscape.total_programs}</dd>
        </div>
        <div>
          <Pill size={17} />
          <dt>药物</dt>
          <dd>{landscape.distinct_drugs}</dd>
        </div>
        <div>
          <Crosshair size={17} />
          <dt>靶点</dt>
          <dd>{landscape.distinct_targets}</dd>
        </div>
        <div>
          <FlaskConical size={17} />
          <dt>适应症</dt>
          <dd>{landscape.distinct_diseases}</dd>
        </div>
        <div>
          <Building2 size={17} />
          <dt>研发机构</dt>
          <dd>{landscape.distinct_organizations}</dd>
        </div>
      </dl>

      <fieldset className="pipeline-analysis-toolbar">
        <legend className="sr-only">竞争格局分析控制</legend>
        <label>
          <span>分析维度</span>
          <select
            aria-label="分析维度"
            value={dimension}
            onChange={(event) =>
              onAnalysisChange({
                dimension: event.target.value as PipelineAnalysisDimension,
                view,
                limit,
                stageScope,
                targetAggregation,
              })
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
          <legend className="sr-only">分析展示方式</legend>
          <button
            type="button"
            aria-pressed={view === "chart"}
            onClick={() => onAnalysisChange({ dimension, view: "chart", limit, stageScope, targetAggregation })}
          >
            <BarChart3 size={14} />
            图表
          </button>
          <button
            type="button"
            aria-pressed={view === "table"}
            onClick={() => onAnalysisChange({ dimension, view: "table", limit, stageScope, targetAggregation })}
          >
            <List size={14} />
            表格
          </button>
        </fieldset>
        <label>
          <span>显示范围</span>
          <select
            aria-label="分析显示范围"
            value={limit}
            onChange={(event) =>
              onAnalysisChange({
                dimension,
                view,
                limit: Number(event.target.value) as PipelineAnalysisLimit,
                stageScope,
                targetAggregation,
              })
            }
          >
            <option value={5}>Top 5</option>
            <option value={8}>Top 8</option>
            <option value={20}>Top 20</option>
            <option value={50}>Top 50</option>
            <option value={100}>Top 100</option>
            <option value={200}>Top 200</option>
          </select>
        </label>
        <label>
          <span>阶段口径</span>
          <select
            aria-label="阶段分析口径"
            value={stageScope}
            onChange={(event) =>
              onAnalysisChange({
                dimension,
                view,
                limit,
                stageScope: event.target.value as PipelineAnalysisStageScope,
                targetAggregation,
              })
            }
          >
            <option value="overall">总体最高阶段</option>
            <option value="global">全球最高阶段</option>
            <option value="china">中国最高阶段</option>
          </select>
        </label>
        <label>
          <span>靶点聚合</span>
          <select
            aria-label="靶点聚合口径"
            value={targetAggregation}
            onChange={(event) =>
              onAnalysisChange({
                dimension,
                view,
                limit,
                stageScope,
                targetAggregation: event.target.value as PipelineTargetAggregation,
              })
            }
          >
            <option value="all">全部靶点</option>
            <option value="primary">主靶点</option>
          </select>
        </label>
        <output aria-live="polite">
          {dimensionOptions.find((option) => option.value === dimension)?.label} · {view === "chart" ? "图表" : "表格"}{" "}
          · Top {limit} · {stageScope === "overall" ? "总体" : stageScope === "global" ? "全球" : "中国"}阶段
          {targetAggregation === "primary" ? " · 主靶点" : ""}
        </output>
      </fieldset>

      <div className={`pipeline-landscape-grid${dimension !== "all" ? " pipeline-landscape-grid-focused" : ""}`}>
        {visibleDistributions.map((distribution) => (
          <Distribution
            key={distribution.dimension}
            title={distribution.title}
            detail={distribution.detail}
            buckets={distribution.buckets}
            filterField={distribution.filterField}
            onFilter={onFilter}
            onOpenEntity={distribution.openEntity ? distribution.entityOpener : undefined}
            view={view}
            limit={limit}
          />
        ))}
      </div>
      <footer className="pipeline-landscape-note">
        <Globe2 size={15} />
        <span>占比基于当前查询结果中的项目数；缺失值单独显示，不代表全球不存在。</span>
      </footer>
    </section>
  );
}
