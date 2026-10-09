import { BarChart3, BookmarkPlus, List } from "lucide-react";
import { QueryRefreshButton } from "../../components/common";
import { DomainExportControl } from "../../components/DomainExportControl";
import {
  hasPipelineSearchFilter,
  type PipelineResultGrain,
  type PipelineSearchFilters,
} from "../../lib/contracts/pipeline";
import { pipelineText as t } from "../../lib/i18n/pipeline";
export function PipelineResultActions({
  refreshing,
  onRefresh,
  resultGrain,
  onResultGrainChange,
  displayMode,
  onDisplayModeChange,
  initialFilters,
  onSave,
  totalRows,
}: {
  refreshing: boolean;
  onRefresh: () => void;
  resultGrain: PipelineResultGrain;
  onResultGrainChange: (grain: PipelineResultGrain) => void;
  displayMode: "list" | "landscape";
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  initialFilters: PipelineSearchFilters;
  onSave: () => void;
  totalRows: number;
}) {
  return (
    <div className="pipeline-result-actions">
      <QueryRefreshButton refreshing={refreshing} onRefresh={onRefresh} />
      <fieldset className="segmented-control">
        <legend className="sr-only">{t("管线结果统计粒度")}</legend>
        <button type="button" aria-pressed={resultGrain === "drug"} onClick={() => onResultGrainChange("drug")}>
          {t("按药物")}
        </button>
        <button type="button" aria-pressed={resultGrain === "program"} onClick={() => onResultGrainChange("program")}>
          {t("按项目")}
        </button>
      </fieldset>
      <fieldset className="segmented-control">
        <legend className="sr-only">{t("管线结果展示方式")}</legend>
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
          {t("格局")}
        </button>
      </fieldset>
      <button
        className="secondary-button"
        type="button"
        disabled={!hasPipelineSearchFilter(initialFilters)}
        title={hasPipelineSearchFilter(initialFilters) ? t("保存或订阅当前管线查询") : t("至少应用一个查询条件")}
        onClick={onSave}
      >
        <BookmarkPlus size={15} />
        {t("保存/订阅")}
      </button>
      <DomainExportControl dataset="pipelines" totalRows={totalRows} />
    </div>
  );
}
