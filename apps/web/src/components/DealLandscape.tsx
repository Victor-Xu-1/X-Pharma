import { BarChart3, CircleDollarSign, Flag, List, Network, Route } from "lucide-react";
import type { DealAnalysisDimension, DealAnalysisLimit, DealAnalysisView } from "../lib/contracts/deals";
import { dealLabel, dealTypeLabels, directionLabels, phaseLabels, statusLabels } from "../lib/dealDisplay";
import type { DealLandscapeBucketRead, DealLandscapeRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { type dealMessages, dealText as t } from "../lib/i18n/deals";
import { DealDistribution } from "./dealLandscape/DealDistribution";
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
const dimensionOptions: Array<{ value: DealAnalysisDimension; label: keyof typeof dealMessages }> = [
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
function labeledBuckets(buckets: DealLandscapeBucketRead[], labels?: Readonly<Record<string, string>>) {
  return buckets.map((bucket) => ({
    ...bucket,
    label:
      bucket.key === "__missing__" ? t("未披露") : labels ? dealLabel(bucket.key, labels, bucket.label) : bucket.label,
  }));
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
  useLocale();
  const distributions = [
    {
      dimension: "deal_type" as const,
      title: t("交易类型"),
      detail: t("按当前授权命中集中的受治理交易类型聚合"),
      buckets: labeledBuckets(landscape.deal_type ?? [], dealTypeLabels),
      filterField: "dealType" as const,
    },
    {
      dimension: "status" as const,
      title: t("交易状态"),
      detail: t("按当前交易生命周期状态聚合"),
      buckets: labeledBuckets(landscape.status ?? [], statusLabels),
      filterField: "status" as const,
    },
    {
      dimension: "direction" as const,
      title: t("交易方向"),
      detail: t("方向基于治理后的参照地区口径"),
      buckets: labeledBuckets(landscape.direction ?? [], directionLabels),
      filterField: "direction" as const,
    },
    {
      dimension: "territory" as const,
      title: t("交易地区"),
      detail: t("交易地区与权益地区保持不同口径"),
      buckets: labeledBuckets(landscape.territory ?? []),
      filterField: "territory" as const,
    },
    {
      dimension: "currency" as const,
      title: t("披露币种"),
      detail: t("仅统计来源披露币种，不换算未披露金额"),
      buckets: labeledBuckets(landscape.currency ?? []),
      filterField: "currency" as const,
    },
    {
      dimension: "asset_modality" as const,
      title: t("资产模态"),
      detail: t("同一交易可关联多个资产模态，占比可能重叠"),
      buckets: labeledBuckets(landscape.asset_modality ?? []),
      filterField: "assetModality" as const,
    },
    {
      dimension: "transaction_phase" as const,
      title: t("交易时阶段"),
      detail: t("按交易发生时的结构化资产阶段聚合"),
      buckets: labeledBuckets(landscape.transaction_phase ?? [], phaseLabels),
      filterField: "developmentPhaseAtTransaction" as const,
    },
    {
      dimension: "current_phase" as const,
      title: t("当前最高阶段"),
      detail: t("按当前数据时点的权威管线阶段聚合"),
      buckets: labeledBuckets(landscape.current_phase ?? [], phaseLabels),
      filterField: "currentDevelopmentPhase" as const,
    },
    {
      dimension: "party_country" as const,
      title: t("参与方地区"),
      detail: t("同一交易可包含多个参与方地区，占比可能重叠"),
      buckets: labeledBuckets(landscape.party_country ?? []),
      filterField: "partyCountryRegion" as const,
    },
    {
      dimension: "rights_territory" as const,
      title: t("权益地区"),
      detail: t("按结构化交易权益记录聚合，不从摘要推断"),
      buckets: labeledBuckets(landscape.rights_territory ?? []),
      filterField: "rightsTerritory" as const,
    },
  ];
  const visible = dimension === "all" ? distributions : distributions.filter((item) => item.dimension === dimension);

  return (
    <section className="pipeline-landscape deal-landscape" aria-label={t("交易数据统计")}>
      <dl className="pipeline-landscape-kpis">
        <div>
          <BarChart3 size={17} />
          <dt>{t("交易总数")}</dt>
          <dd>{landscape.total_deals}</dd>
        </div>
        <div>
          <Network size={17} />
          <dt>{t("交易类型")}</dt>
          <dd>{(landscape.deal_type ?? []).filter((bucket) => bucket.key !== "__missing__").length}</dd>
        </div>
        <div>
          <Route size={17} />
          <dt>{t("交易方向")}</dt>
          <dd>{(landscape.direction ?? []).filter((bucket) => bucket.key !== "__missing__").length}</dd>
        </div>
        <div>
          <Flag size={17} />
          <dt>{t("参与方地区")}</dt>
          <dd>{(landscape.party_country ?? []).length}</dd>
        </div>
        <div>
          <CircleDollarSign size={17} />
          <dt>{t("披露币种")}</dt>
          <dd>{(landscape.currency ?? []).filter((bucket) => bucket.key !== "__missing__").length}</dd>
        </div>
      </dl>

      <fieldset className="pipeline-analysis-toolbar">
        <legend className="sr-only">{t("交易统计分析控制")}</legend>
        <label>
          <span>{t("分析维度")}</span>
          <select
            aria-label={t("交易分析维度")}
            value={dimension}
            onChange={(event) =>
              onAnalysisChange({ dimension: event.target.value as DealAnalysisDimension, view, limit })
            }
          >
            {dimensionOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {t(option.label)}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="segmented-control">
          <legend className="sr-only">{t("交易分析展示方式")}</legend>
          <button
            type="button"
            aria-pressed={view === "chart"}
            onClick={() => onAnalysisChange({ dimension, view: "chart", limit })}
          >
            <BarChart3 size={14} />
            {t("图表")}
          </button>
          <button
            type="button"
            aria-pressed={view === "table"}
            onClick={() => onAnalysisChange({ dimension, view: "table", limit })}
          >
            <List size={14} />
            {t("表格")}
          </button>
        </fieldset>
        <label>
          <span>{t("显示范围")}</span>
          <select
            aria-label={t("交易分析显示范围")}
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
          {t(dimensionOptions.find((option) => option.value === dimension)?.label ?? "全部维度")} ·{" "}
          {view === "chart" ? t("图表") : t("表格")}
          {" · "}Top {limit}
        </output>
      </fieldset>

      <div className={`pipeline-landscape-grid${dimension !== "all" ? " pipeline-landscape-grid-focused" : ""}`}>
        {visible.map((distribution) => (
          <DealDistribution
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
        <span>{t("统计基于当前授权查询的完整命中集；多资产和多参与方维度可重叠，未披露不会推断。")}</span>
      </footer>
    </section>
  );
}
