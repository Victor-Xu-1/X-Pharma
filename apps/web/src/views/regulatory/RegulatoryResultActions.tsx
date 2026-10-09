import { BookmarkPlus } from "lucide-react";
import { QueryRefreshButton } from "../../components/common";
import { QueryResultSummary } from "../../components/QueryResultSummary";
import type { RegulatorySearchFilters } from "../../lib/contracts/regulatory";
import type { RegulatoryEventSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { regulatoryText as t } from "../../lib/i18n/regulatory";
export function RegulatoryResultActions({
  data,
  filters,
  refreshing,
  saveable,
  onRefresh,
  onDisplayMode,
  onSave,
}: {
  data: RegulatoryEventSearchResult;
  filters: RegulatorySearchFilters;
  refreshing: boolean;
  saveable: boolean;
  onRefresh: () => void;
  onDisplayMode: (displayMode: "list" | "landscape") => void;
  onSave: () => void;
}) {
  useLocale();
  return (
    <div className="pipeline-result-toolbar">
      <QueryResultSummary
        total={data.total}
        offset={data.offset}
        count={data.items.length}
        unit={t("项监管事件")}
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
          disabled={!saveable}
          title={saveable ? t("保存或订阅当前监管查询") : t("至少应用一个查询条件")}
          onClick={onSave}
        >
          <BookmarkPlus size={15} />
          {t("保存/订阅")}
        </button>
      </div>
    </div>
  );
}
