import { BookmarkPlus } from "lucide-react";
import { QueryRefreshButton } from "../../components/common";
import { QueryResultSummary } from "../../components/QueryResultSummary";
import type { EpidemiologyFilters, EpidemiologySearchResult } from "../../lib/contracts/epidemiology";
import { hasEpidemiologySearchFilter } from "../../lib/contracts/epidemiology";
import { useLocale } from "../../lib/i18n";
import { epidemiologyText as t } from "../../lib/i18n/epidemiology";
export function EpidemiologyResultActions({
  data,
  filters,
  refreshing,
  onRefresh,
  onDisplayMode,
  onSave,
}: {
  data: EpidemiologySearchResult;
  filters: EpidemiologyFilters;
  refreshing: boolean;
  onRefresh: () => void;
  onDisplayMode: (mode: "list" | "landscape") => void;
  onSave: () => void;
}) {
  useLocale();
  return (
    <div className="pipeline-result-toolbar">
      <QueryResultSummary
        total={data.total}
        offset={data.offset}
        count={data.items.length}
        unit={t("项疾病负担观测")}
        queriedAt={data.as_of}
      />
      <div className="pipeline-result-actions">
        <QueryRefreshButton refreshing={refreshing} onRefresh={onRefresh} />
        <fieldset className="segmented-control">
          <legend className="sr-only">{t("结果展示方式")}</legend>
          <button type="button" aria-pressed={filters.displayMode === "list"} onClick={() => onDisplayMode("list")}>
            {t("列表")}
          </button>
          <button
            type="button"
            aria-pressed={filters.displayMode === "landscape"}
            onClick={() => onDisplayMode("landscape")}
          >
            {t("统计")}
          </button>
        </fieldset>
        <button
          className="secondary-button"
          type="button"
          disabled={!hasEpidemiologySearchFilter(filters)}
          title={hasEpidemiologySearchFilter(filters) ? t("保存或订阅当前流行病学查询") : t("至少应用一个查询条件")}
          onClick={onSave}
        >
          <BookmarkPlus size={15} />
          {t("保存/订阅")}
        </button>
      </div>
    </div>
  );
}
