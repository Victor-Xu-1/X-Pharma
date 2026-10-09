import { BarChart3, BookmarkPlus, List } from "lucide-react";
import { QueryRefreshButton } from "../../components/common";
import { DomainExportControl } from "../../components/DomainExportControl";
import { hasTrialSearchFilter, type TrialSavedSearchInput } from "../../lib/contracts/trials";
import { clinicalText as t } from "../../lib/i18n/clinical";
export function TrialResultActions({
  refreshing,
  onRefresh,
  displayMode,
  onDisplayModeChange,
  input,
  onSave,
  totalRows,
}: {
  refreshing: boolean;
  onRefresh: () => void;
  displayMode: "list" | "landscape";
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  input: TrialSavedSearchInput;
  onSave: () => void;
  totalRows: number;
}) {
  return (
    <div className="pipeline-result-actions">
      <QueryRefreshButton refreshing={refreshing} onRefresh={onRefresh} />
      <fieldset className="segmented-control">
        <legend className="sr-only">{t("临床结果展示方式")}</legend>
        <button type="button" aria-pressed={displayMode === "list"} onClick={() => onDisplayModeChange("list")}>
          <List size={15} />
          {t("列表")}
        </button>
        <button
          type="button"
          aria-pressed={displayMode === "landscape"}
          onClick={() => onDisplayModeChange("landscape")}
        >
          <BarChart3 size={15} />
          {t("可视化")}
        </button>
      </fieldset>
      <button
        className="secondary-button"
        type="button"
        disabled={!hasTrialSearchFilter(input)}
        title={hasTrialSearchFilter(input) ? t("保存或订阅当前临床试验查询") : t("至少应用一个查询条件")}
        onClick={onSave}
      >
        <BookmarkPlus size={15} />
        {t("保存/订阅")}
      </button>
      <DomainExportControl dataset="trials" totalRows={totalRows} />
    </div>
  );
}
