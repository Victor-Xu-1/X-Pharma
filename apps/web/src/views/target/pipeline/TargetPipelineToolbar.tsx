import { Columns3, RotateCcw } from "lucide-react";
import { AddToComparisonControl } from "../../../components/AddToComparisonControl";
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
          <legend className="sr-only">研发药物展示方式</legend>
          <button type="button" aria-pressed={displayMode === "drug"} onClick={() => updateDisplayMode("drug")}>
            药物概览
          </button>
          <button type="button" aria-pressed={displayMode === "program"} onClick={() => updateDisplayMode("program")}>
            项目明细
          </button>
          <button
            type="button"
            aria-pressed={displayMode === "landscape"}
            onClick={() => updateDisplayMode("landscape")}
          >
            可视化
          </button>
        </fieldset>
        {displayMode === "drug" ? (
          <details className="table-column-menu">
            <summary>
              <Columns3 size={15} />列
            </summary>
            <fieldset>
              <legend>药物概览列设置</legend>
              {targetDrugColumnOptions.map((column) => (
                <label className="table-column-option" key={column.key}>
                  <input
                    type="checkbox"
                    aria-label={`显示列：${column.label}`}
                    checked={visibleDrugColumns.has(column.key)}
                    onChange={(event) => toggleDrugColumn(column.key, event.target.checked)}
                  />
                  <span>{column.label}</span>
                </label>
              ))}
              <button
                className="secondary-button"
                type="button"
                disabled={visibleDrugColumns.size === targetDrugColumnOptions.length}
                onClick={() => setVisibleDrugColumns(defaultTargetDrugColumns())}
              >
                <RotateCcw size={14} />
                恢复默认列
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
          <div className="table-selection-actions pipeline-result-actions" role="toolbar" aria-label="竞品候选选择">
            <span role="status">
              {selectedDrugIds.size
                ? `已选 ${selectedDrugIds.size} 个药物，可继续调整筛选添加其他候选`
                : "尚未选择药物"}
            </span>
            <button
              className="secondary-button"
              type="button"
              disabled={!pageDrugIds.length}
              aria-pressed={allPageDrugsSelected}
              onClick={() => togglePageDrugSelection(pageDrugIds, allPageDrugsSelected)}
            >
              {allPageDrugsSelected ? "取消选择本页" : "选择本页"}
            </button>
            {selectedDrugIds.size ? (
              <button className="secondary-button" type="button" onClick={clearDrugSelection}>
                清空选择
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
              打开对比列表
            </button>
          ) : null}
        </p>
      ) : null}
    </>
  );
}
