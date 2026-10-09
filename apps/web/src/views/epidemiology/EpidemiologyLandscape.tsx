import { DomainLandscape } from "../../components/DomainLandscape";
import type { EpidemiologySearchResult } from "../../lib/contracts/epidemiology";
import { useLocale } from "../../lib/i18n";
import { epidemiologyText as t } from "../../lib/i18n/epidemiology";
import { measureValue } from "./presentation";
export function EpidemiologyLandscape({
  landscape,
  view,
  onViewChange,
  onFilter,
}: {
  landscape: EpidemiologySearchResult["landscape"];
  view: "chart" | "table";
  onViewChange: (view: "chart" | "table") => void;
  onFilter: (field: "measure" | "geography" | "population_scope", value: string) => void;
}) {
  useLocale();
  return (
    <DomainLandscape<"measure" | "geography" | "population_scope">
      domainId="epidemiology"
      ariaLabel={t("疾病负担统计分析")}
      total={landscape.total_observations}
      totalUnit={t("条观察")}
      unitLabel={t("观察数")}
      sections={[
        {
          id: "measure",
          title: t("统计口径"),
          detail: t("按统计口径统计完整命中集"),
          buckets: (landscape.measure ?? []).map((bucket) => ({
            ...bucket,
            label: bucket.label === bucket.key ? measureValue(bucket.key) : bucket.label,
          })),
          filterField: "measure",
        },
        {
          id: "geography",
          title: t("地区"),
          detail: t("按结果口径地区统计完整命中集"),
          buckets: landscape.geography ?? [],
          filterField: "geography",
        },
        {
          id: "population-scope",
          title: t("人群口径"),
          detail: t("按人群口径统计完整命中集"),
          buckets: landscape.population_scope ?? [],
          filterField: "population_scope",
        },
      ]}
      view={view}
      onViewChange={onViewChange}
      onFilter={onFilter}
    />
  );
}
