import { DomainLandscape } from "../../components/DomainLandscape";
import type { RegulatoryEventSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { regulatoryText as t } from "../../lib/i18n/regulatory";
import { eventTypeLabels } from "../../lib/regulatoryDisplay";
import { regulatoryValue } from "./presentation";
export function RegulatoryLandscape({
  landscape,
  view,
  onViewChange,
  onFilter,
}: {
  landscape: RegulatoryEventSearchResult["landscape"];
  view: "chart" | "table";
  onViewChange: (view: "chart" | "table") => void;
  onFilter: (field: "event_type" | "agency", value: string) => void;
}) {
  useLocale();
  return (
    <DomainLandscape<"event_type" | "agency">
      domainId="regulatory"
      ariaLabel={t("监管统计分析")}
      total={landscape.total_events}
      totalUnit={t("项监管事件")}
      unitLabel={t("事件数")}
      sections={[
        {
          id: "event-type",
          title: t("事件类型"),
          detail: t("按事件类型统计完整命中集"),
          buckets: (landscape.event_type ?? []).map((bucket) => ({
            ...bucket,
            label: Object.hasOwn(eventTypeLabels, bucket.key)
              ? regulatoryValue(bucket.key, eventTypeLabels)
              : bucket.label,
          })),
          filterField: "event_type",
        },
        {
          id: "agency",
          title: t("监管机构"),
          detail: t("按监管机构统计完整命中集"),
          buckets: landscape.agency ?? [],
          filterField: "agency",
        },
        {
          id: "decision-year",
          title: t("决定年份"),
          detail: t("按决定年份统计完整命中集"),
          buckets: landscape.decision_year ?? [],
          filterField: null,
        },
      ]}
      view={view}
      onViewChange={onViewChange}
      onFilter={onFilter}
    />
  );
}
