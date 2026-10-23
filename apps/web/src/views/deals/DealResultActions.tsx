import { BarChart3, BookmarkPlus, List } from "lucide-react";
import { QueryRefreshButton } from "../../components/common";
import { DomainExportControl } from "../../components/DomainExportControl";
import { QueryResultSummary } from "../../components/QueryResultSummary";
import type { DealSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";

export function DealResultActions({
  data,
  displayMode,
  refreshing,
  saveable,
  onRefresh,
  onDisplayMode,
  onSave,
}: {
  data: DealSearchResult;
  displayMode: "list" | "landscape";
  refreshing: boolean;
  saveable: boolean;
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
        unit={t("项交易")}
        queriedAt={data.as_of}
        showRange={displayMode === "list"}
      />
      <div className="pipeline-result-actions">
        <QueryRefreshButton refreshing={refreshing} onRefresh={onRefresh} />
        <fieldset className="segmented-control">
          <legend className="sr-only">{t("交易结果展示方式")}</legend>
          <button type="button" aria-pressed={displayMode === "list"} onClick={() => onDisplayMode("list")}>
            <List size={15} aria-hidden="true" />
            {t("列表")}
          </button>
          <button type="button" aria-pressed={displayMode === "landscape"} onClick={() => onDisplayMode("landscape")}>
            <BarChart3 size={15} aria-hidden="true" />
            {t("统计")}
          </button>
        </fieldset>
        <button
          className="secondary-button"
          type="button"
          disabled={!saveable}
          title={saveable ? t("保存或订阅当前交易查询") : t("至少应用一个查询条件")}
          onClick={onSave}
        >
          <BookmarkPlus size={15} aria-hidden="true" />
          {t("保存/订阅")}
        </button>
        <DomainExportControl dataset="deals" totalRows={data.total} />
      </div>
    </div>
  );
}
