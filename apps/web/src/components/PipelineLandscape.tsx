import { useLocale } from "../lib/i18n";
import { pipelineLandscapeText as t } from "../lib/i18n/pipelineLandscape";
import { AnalysisControls } from "./pipelineLandscape/AnalysisControls";
import { Distribution } from "./pipelineLandscape/Distribution";
import { labeledModalities, labeledPhases } from "./pipelineLandscape/presentation";
import type { PipelineLandscapeProps } from "./pipelineLandscape/types";

export type { PipelineLandscapeFilterField } from "./pipelineLandscape/types";

import { BarChart3, Building2, Crosshair, FlaskConical, Globe2, Pill } from "lucide-react";

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
}: PipelineLandscapeProps) {
  useLocale();
  const targetOpener = onOpenTarget ?? onOpenEntity;
  const diseaseOpener = onOpenDisease ?? onOpenEntity;
  const organizationOpener = onOpenOrganization ?? onOpenEntity;
  const distributions = [
    {
      dimension: "global_phase" as const,
      title: t("全球研发阶段"),
      detail: t("同一筛选条件下各项目的全球最高阶段"),
      buckets: labeledPhases(
        (landscape.global_phase ?? []).length ? (landscape.global_phase ?? []) : (landscape.overall_phase ?? []),
      ),
      filterField: (landscape.global_phase ?? []).length ? ("globalPhase" as const) : ("phase" as const),
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "china_phase" as const,
      title: t("中国研发阶段"),
      detail: t("中国阶段独立统计，未披露不会推断"),
      buckets: labeledPhases(landscape.china_phase ?? []),
      filterField: "chinaPhase" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "targets" as const,
      title: t("靶点"),
      detail: t("按靶点汇总，可继续筛选或查看靶点详情"),
      buckets: landscape.targets ?? [],
      filterField: "targetEntityId" as const,
      openEntity: true,
      entityOpener: targetOpener,
    },
    {
      dimension: "target_combinations" as const,
      title: t("靶点组合"),
      detail: t("按已确认的靶点组合汇总，未明确披露的关系不会自动推断"),
      buckets: landscape.target_combinations ?? [],
      filterField: "targetCombinationKey" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "diseases" as const,
      title: t("适应症"),
      detail: t("按适应症汇总，未明确披露的适应症不会自动推断"),
      buckets: landscape.diseases ?? [],
      filterField: "diseaseEntityId" as const,
      openEntity: true,
      entityOpener: diseaseOpener,
    },
    {
      dimension: "modality" as const,
      title: t("药物类型"),
      detail: t("按药物类型汇总"),
      buckets: labeledModalities(landscape.modality ?? []),
      filterField: "modality" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "geography" as const,
      title: t("地区分布"),
      detail: t("记录地区与权益地区保持不同口径"),
      buckets: landscape.geography ?? [],
      filterField: "geography" as const,
      openEntity: false,
      entityOpener: undefined,
    },
    {
      dimension: "organizations" as const,
      title: t("研发机构"),
      detail: t("按研发机构汇总，可继续筛选或查看公司详情"),
      buckets: landscape.organizations ?? [],
      filterField: "organizationEntityId" as const,
      openEntity: true,
      entityOpener: organizationOpener,
    },
  ];
  const visibleDistributions =
    dimension === "all" ? distributions : distributions.filter((item) => item.dimension === dimension);

  return (
    <section className="pipeline-landscape" aria-label={t("管线竞争格局")}>
      <dl className="pipeline-landscape-kpis">
        <div>
          <BarChart3 size={17} />
          <dt>{t("研发项目")}</dt>
          <dd>{landscape.total_programs}</dd>
        </div>
        <div>
          <Pill size={17} />
          <dt>{t("药物")}</dt>
          <dd>{landscape.distinct_drugs}</dd>
        </div>
        <div>
          <Crosshair size={17} />
          <dt>{t("靶点")}</dt>
          <dd>{landscape.distinct_targets}</dd>
        </div>
        <div>
          <FlaskConical size={17} />
          <dt>{t("适应症")}</dt>
          <dd>{landscape.distinct_diseases}</dd>
        </div>
        <div>
          <Building2 size={17} />
          <dt>{t("研发机构")}</dt>
          <dd>{landscape.distinct_organizations}</dd>
        </div>
      </dl>

      <AnalysisControls
        dimension={dimension}
        view={view}
        limit={limit}
        stageScope={stageScope}
        targetAggregation={targetAggregation}
        onAnalysisChange={onAnalysisChange}
      />
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
        <span>{t("占比基于当前查询结果中的项目数；缺失值单独显示，不代表全球不存在。")}</span>
      </footer>
    </section>
  );
}
