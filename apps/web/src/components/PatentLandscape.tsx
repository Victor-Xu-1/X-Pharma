import type { PatentLandscapeRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { patentText as t } from "../lib/i18n/patents";
import { patentStatus } from "../lib/patentDisplay";
import { type DomainAnalysisView, DomainLandscape } from "./DomainLandscape";

export type PatentLandscapeFilterField = "legal_status" | "applicant";
export type PatentAnalysisView = DomainAnalysisView;

export function PatentLandscape({
  landscape,
  view,
  onViewChange,
  onFilter,
}: {
  landscape: PatentLandscapeRead;
  view: PatentAnalysisView;
  onViewChange: (view: PatentAnalysisView) => void;
  onFilter: (field: PatentLandscapeFilterField, value: string) => void;
}) {
  useLocale();
  return (
    <DomainLandscape<PatentLandscapeFilterField>
      domainId="patent"
      ariaLabel={t("专利统计分析")}
      total={landscape.total_families}
      totalUnit={t("个专利族")}
      unitLabel={t("专利族数")}
      sections={[
        {
          id: "legal-status",
          title: t("法律状态"),
          detail: t("按当前受治理法律状态统计完整命中集"),
          buckets: (landscape.legal_status ?? []).map((bucket) => ({
            ...bucket,
            label: bucket.key === "__missing__" ? t("未披露") : patentStatus(bucket.key, bucket.label),
          })),
          filterField: "legal_status",
        },
        {
          id: "top-applicants",
          title: t("主要申请人"),
          detail: t("按申请人统计的前列专利族数量"),
          buckets: landscape.top_applicants ?? [],
          filterField: "applicant",
        },
        {
          id: "priority-year",
          title: t("优先权年份"),
          detail: t("按最早优先权年份统计完整命中集"),
          buckets: landscape.priority_year ?? [],
          filterField: null,
        },
      ]}
      view={view}
      onViewChange={onViewChange}
      onFilter={onFilter}
    />
  );
}
