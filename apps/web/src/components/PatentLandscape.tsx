import type { PatentLandscapeRead } from "../lib/generated";
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
  return (
    <DomainLandscape<PatentLandscapeFilterField>
      domainId="patent"
      ariaLabel="专利统计分析"
      total={landscape.total_families}
      totalUnit="个专利族"
      unitLabel="专利族数"
      sections={[
        {
          id: "legal-status",
          title: "法律状态",
          detail: "按当前受治理法律状态统计完整命中集",
          buckets: landscape.legal_status ?? [],
          filterField: "legal_status",
        },
        {
          id: "top-applicants",
          title: "主要申请人",
          detail: "按申请人统计的前列专利族数量",
          buckets: landscape.top_applicants ?? [],
          filterField: "applicant",
        },
        {
          id: "priority-year",
          title: "优先权年份",
          detail: "按最早优先权年份统计完整命中集",
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
