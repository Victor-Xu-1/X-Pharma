import { DomainLandscape } from "../../components/DomainLandscape";
import type { NewsEventSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { newsText as t } from "../../lib/i18n/news";
import { newsEventTypeLabels } from "../../lib/newsDisplay";
import { newsTypeLabel } from "./presentation";
export function NewsLandscape({
  landscape,
  view,
  onViewChange,
  onFilter,
}: {
  landscape: NewsEventSearchResult["landscape"];
  view: "chart" | "table";
  onViewChange: (view: "chart" | "table") => void;
  onFilter: (field: "event_type" | "venue", value: string) => void;
}) {
  useLocale();
  return (
    <DomainLandscape<"event_type" | "venue">
      domainId="news"
      ariaLabel={t("资讯统计分析")}
      total={landscape.total_events}
      totalUnit={t("条动态")}
      unitLabel={t("事件数")}
      sections={[
        {
          id: "event-type",
          title: t("事件类型"),
          detail: t("按事件类型统计完整命中集"),
          buckets: (landscape.event_type ?? []).map((bucket) => ({
            ...bucket,
            label: Object.hasOwn(newsEventTypeLabels, bucket.key) ? newsTypeLabel(bucket.key) : bucket.label,
          })),
          filterField: "event_type",
        },
        {
          id: "venue",
          title: t("会议与期刊"),
          detail: t("按会议/期刊统计完整命中集"),
          buckets: landscape.venue ?? [],
          filterField: "venue",
        },
        {
          id: "published-year",
          title: t("发布年份"),
          detail: t("按发布年份统计完整命中集"),
          buckets: landscape.published_year ?? [],
          filterField: null,
        },
      ]}
      view={view}
      onViewChange={onViewChange}
      onFilter={onFilter}
    />
  );
}
