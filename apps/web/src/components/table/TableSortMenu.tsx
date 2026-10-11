import type { Column, SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronDown, ChevronsUpDown, ChevronUp, Plus, Trash2 } from "lucide-react";
import { useLocale } from "../../lib/i18n";
import { tableText as t } from "../../lib/i18n/table";
import { columnLabel } from "../../lib/tablePresentation";
import { useDismissibleDetails } from "../../lib/useDismissibleDetails";
import { useFilterDraft } from "../../lib/useFilterDraft";
import { normalizeSortingState } from "./sorting";

export function TableSortMenu<T>({
  columns,
  sorting,
  defaultSorting,
  onApply,
  onIntent,
}: {
  columns: Column<T, unknown>[];
  sorting: SortingState;
  defaultSorting: SortingState;
  onApply: (sorting: SortingState) => void;
  onIntent: () => void;
}) {
  useLocale();
  const sortPopover = useDismissibleDetails();
  const [sortDraft, setSortDraft] = useFilterDraft(normalizeSortingState(sorting));
  const sortableColumns = columns.filter((column) => column.getCanSort());
  const draftSorting = sortDraft.length ? sortDraft : defaultSorting;
  const sortDraftIsCurrent =
    sorting.length === draftSorting.length &&
    sorting.every((sort, index) => sort.id === draftSorting[index]?.id && sort.desc === draftSorting[index]?.desc);
  function applyServerSort() {
    if (sortDraftIsCurrent) return;
    onIntent();
    onApply(draftSorting);
  }

  function updateSortDraft(index: number, update: Partial<SortingState[number]>) {
    onIntent();
    setSortDraft((current) =>
      normalizeSortingState(
        current.map((criterion, criterionIndex) =>
          criterionIndex === index ? { ...criterion, ...update } : criterion,
        ),
      ),
    );
  }

  function addSortCriterion() {
    const selected = new Set(sortDraft.map((criterion) => criterion.id));
    const nextColumn = sortableColumns.find((column) => !selected.has(column.id));
    if (!nextColumn || sortDraft.length >= 5) return;
    onIntent();
    setSortDraft((current) => [...current, { id: nextColumn.id, desc: false }]);
  }

  function removeSortCriterion(index: number) {
    onIntent();
    setSortDraft((current) => {
      const next = current.filter((_criterion, criterionIndex) => criterionIndex !== index);
      return next.length ? next : defaultSorting;
    });
  }

  function moveSortCriterion(index: number, direction: -1 | 1) {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= sortDraft.length) return;
    onIntent();
    setSortDraft((current) => {
      const next = [...current];
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return next;
    });
  }

  if (!sortableColumns.length) return null;
  return (
    <details className="table-sort-menu" {...sortPopover}>
      <summary title={t("自定义排序")}>
        <ChevronsUpDown size={15} />
        {t("排序")}
      </summary>
      <fieldset className="table-sort-editor">
        <legend>{t("自定义排序")}</legend>
        <div className="table-sort-editor-heading">
          <strong>{t("排序优先级")}</strong>
          <span aria-live="polite">{sortDraft.length}/5</span>
        </div>
        <div className="table-sort-criteria">
          {sortDraft.map((criterion, index) => (
            <div className="table-sort-criterion" key={criterion.id}>
              <span className="table-sort-priority" aria-hidden="true">
                {index + 1}
              </span>
              <label>
                <span className="sr-only">{t("第 {index} 排序字段", { index: index + 1 })}</span>
                <select
                  aria-label={t("第 {index} 排序字段", { index: index + 1 })}
                  value={criterion.id}
                  onChange={(event) => updateSortDraft(index, { id: event.target.value })}
                >
                  {sortableColumns.map((column) => (
                    <option
                      value={column.id}
                      key={column.id}
                      disabled={sortDraft.some(
                        (selected, selectedIndex) => selectedIndex !== index && selected.id === column.id,
                      )}
                    >
                      {columnLabel(column)}
                    </option>
                  ))}
                </select>
              </label>
              <fieldset className="table-sort-direction">
                <legend className="sr-only">{t("第 {index} 排序方向", { index: index + 1 })}</legend>
                <button
                  type="button"
                  aria-label={t("第 {index} 排序方向：升序", { index: index + 1 })}
                  title={t("升序")}
                  aria-pressed={!criterion.desc}
                  onClick={() => updateSortDraft(index, { desc: false })}
                >
                  <ArrowUp size={14} />
                </button>
                <button
                  type="button"
                  aria-label={t("第 {index} 排序方向：降序", { index: index + 1 })}
                  title={t("降序")}
                  aria-pressed={criterion.desc}
                  onClick={() => updateSortDraft(index, { desc: true })}
                >
                  <ArrowDown size={14} />
                </button>
              </fieldset>
              <div className="table-sort-order-controls">
                <button
                  type="button"
                  aria-label={t("上移第 {index} 排序字段", { index: index + 1 })}
                  title={t("提高优先级")}
                  disabled={index === 0}
                  onClick={() => moveSortCriterion(index, -1)}
                >
                  <ChevronUp size={14} />
                </button>
                <button
                  type="button"
                  aria-label={t("下移第 {index} 排序字段", { index: index + 1 })}
                  title={t("降低优先级")}
                  disabled={index === sortDraft.length - 1}
                  onClick={() => moveSortCriterion(index, 1)}
                >
                  <ChevronDown size={14} />
                </button>
                <button
                  type="button"
                  aria-label={t("删除第 {index} 排序字段", { index: index + 1 })}
                  title={t("删除排序字段")}
                  disabled={sortDraft.length === 1}
                  onClick={() => removeSortCriterion(index)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="secondary-button table-sort-add"
          disabled={sortDraft.length >= 5 || sortDraft.length >= sortableColumns.length}
          onClick={addSortCriterion}
        >
          <Plus size={14} />
          {t("添加排序字段")}
        </button>
        <button
          type="button"
          className="primary-button table-sort-apply"
          disabled={sortDraftIsCurrent}
          onClick={applyServerSort}
        >
          {t("应用排序")}
        </button>
      </fieldset>
    </details>
  );
}
