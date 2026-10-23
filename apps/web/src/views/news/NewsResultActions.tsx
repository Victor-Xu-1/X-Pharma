import { BookmarkPlus } from "lucide-react";
import { QueryRefreshButton } from "../../components/common";
import { QueryResultSummary } from "../../components/QueryResultSummary";
import type { NewsEventSearchResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { newsText as t } from "../../lib/i18n/news";
export function NewsResultActions({
  data,
  displayMode,
  refreshing,
  saveable,
  onRefresh,
  onSave,
}: {
  data: NewsEventSearchResult;
  displayMode: "list" | "timeline" | "landscape";
  refreshing: boolean;
  saveable: boolean;
  onRefresh: () => void;
  onSave: () => void;
}) {
  useLocale();
  return (
    <div className="pipeline-result-toolbar">
      <QueryResultSummary
        total={data.total}
        offset={data.offset}
        count={data.items.length}
        unit={displayMode === "timeline" ? t("项研究发布") : t("项最新动态")}
        queriedAt={data.as_of}
      />
      <div className="pipeline-result-actions">
        <QueryRefreshButton refreshing={refreshing} onRefresh={onRefresh} />
        <button
          className="secondary-button"
          type="button"
          disabled={!saveable}
          title={saveable ? t("保存或订阅当前资讯查询") : t("至少应用一个查询条件")}
          onClick={onSave}
        >
          <BookmarkPlus size={15} />
          {t("保存/订阅")}
        </button>
      </div>
    </div>
  );
}
