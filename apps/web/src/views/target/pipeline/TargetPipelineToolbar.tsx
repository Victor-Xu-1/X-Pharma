import { Columns3, RotateCcw } from "lucide-react";
import { AddToComparisonControl } from "../../../components/AddToComparisonControl";
import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import { useDismissibleDetails } from "../../../lib/useDismissibleDetails";
import { defaultTargetDrugColumns, targetDrugColumnOptions } from "./presentation";
import type { TargetPipelineProps } from "./types";
import type { TargetPipelineState } from "./useTargetPipeline";

export function TargetPipelineToolbar({
  state,
  pageDrugIds,
  allPageDrugsSelected,
  onOpenComparison,
}: {
  state: Pick<
    TargetPipelineState,
    | "displayMode"
    | "updateDisplayMode"
    | "visibleDrugColumns"
    | "toggleDrugColumn"
    | "setVisibleDrugColumns"
    | "selectedDrugIds"
    | "setSelectedDrugIds"
    | "setComparisonMessage"
    | "setComparisonTarget"
    | "comparisonMessage"
    | "comparisonTarget"
    | "togglePageDrugSelection"
    | "clearDrugSelection"
  >;
  onOpenComparison: TargetPipelineProps["onOpenComparison"];
  pageDrugIds: string[];
  allPageDrugsSelected: boolean;
}) {
  const text = useMessages(targetPipelineMessages);
  const columnPopover = useDismissibleDetails();
  const {
    displayMode,
    updateDisplayMode,
    visibleDrugColumns,
    toggleDrugColumn,
    setVisibleDrugColumns,
    selectedDrugIds,
    setSelectedDrugIds,
    setComparisonMessage,
    setComparisonTarget,
    comparisonMessage,
    comparisonTarget,
    togglePageDrugSelection,
    clearDrugSelection,
  } = state;
  return (
    <>
      <div className="pipeline-result-actions query-results-toolbar">
        <fieldset className="segmented-control">
          <legend className="sr-only">{text("研发药物展示方式")}</legend>
          <button type="button" aria-pressed={displayMode === "drug"} onClick={() => updateDisplayMode("drug")}>
            {text("药物概览")}
          </button>
          <button type="button" aria-pressed={displayMode === "program"} onClick={() => updateDisplayMode("program")}>
            {text("项目明细")}
          </button>
          <button
            type="button"
            aria-pressed={displayMode === "landscape"}
            onClick={() => updateDisplayMode("landscape")}
          >
            {text("可视化")}
          </button>
        </fieldset>
        {displayMode === "drug" ? (
          <details className="table-column-menu" {...columnPopover}>
            <summary>
              <Columns3 size={15} />
              {text("列")}
            </summary>
            <fieldset>
              <legend>{text("药物概览列设置")}</legend>
              {targetDrugColumnOptions.map((column) => (
                <label className="table-column-option" key={column.key}>
                  <input
                    type="checkbox"
                    aria-label={text("显示列：{label}", { label: text(column.label) })}
                    checked={visibleDrugColumns.has(column.key)}
                    onChange={(event) => toggleDrugColumn(column.key, event.target.checked)}
                  />
                  <span>{text(column.label)}</span>
                </label>
              ))}
              <button
                className="secondary-button"
                type="button"
                disabled={visibleDrugColumns.size === targetDrugColumnOptions.length}
                onClick={() => setVisibleDrugColumns(defaultTargetDrugColumns())}
              >
                <RotateCcw size={14} />
                {text("恢复默认列")}
              </button>
            </fieldset>
          </details>
        ) : null}
        <AddToComparisonControl
          selectedEntityIds={[...selectedDrugIds]}
          onAdded={(message) => {
            setSelectedDrugIds(new Set());
            setComparisonMessage(message);
            setComparisonTarget(null);
          }}
          onComparisonReady={
            onOpenComparison
              ? (comparisonSetId, entityIds) => setComparisonTarget({ comparisonSetId, entityIds })
              : undefined
          }
        />
        {displayMode === "drug" ? (
          <div
            className="table-selection-actions pipeline-result-actions"
            role="toolbar"
            aria-label={text("竞品候选选择")}
          >
            <span role="status">
              {selectedDrugIds.size
                ? text("已选 {count} 个药物，可继续调整筛选添加其他候选", { count: selectedDrugIds.size })
                : text("尚未选择药物")}
            </span>
            <button
              className="secondary-button"
              type="button"
              disabled={!pageDrugIds.length}
              aria-pressed={allPageDrugsSelected}
              onClick={() => togglePageDrugSelection(pageDrugIds, allPageDrugsSelected)}
            >
              {allPageDrugsSelected ? text("取消选择本页") : text("选择本页")}
            </button>
            {selectedDrugIds.size ? (
              <button className="secondary-button" type="button" onClick={clearDrugSelection}>
                {text("清空选择")}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
      {comparisonMessage ? (
        <p className="inline-success" role="status">
          {comparisonMessage}
          {comparisonTarget && onOpenComparison ? (
            <button
              className="text-button"
              type="button"
              onClick={() => onOpenComparison(comparisonTarget.comparisonSetId, comparisonTarget.entityIds)}
            >
              {text("打开对比列表")}
            </button>
          ) : null}
        </p>
      ) : null}
    </>
  );
}
