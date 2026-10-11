import type { Column } from "@tanstack/react-table";
import { Check, ChevronDown, ChevronUp, Columns3 } from "lucide-react";
import { useLocale } from "../../lib/i18n";
import { tableText as t } from "../../lib/i18n/table";
import { columnLabel } from "../../lib/tablePresentation";
import { useDismissibleDetails } from "../../lib/useDismissibleDetails";

export function TableColumnMenu<T>({
  leafColumns,
  preferenceControlsDisabled,
  columnOrderAnnouncement,
  moveColumn,
}: {
  leafColumns: Column<T, unknown>[];
  preferenceControlsDisabled: boolean;
  columnOrderAnnouncement: { columnId: string; index: number } | null;
  moveColumn: (columnId: string, direction: -1 | 1) => void;
}) {
  useLocale();
  const columnPopover = useDismissibleDetails();
  const visibleColumnCount = leafColumns.filter((column) => column.getIsVisible()).length;
  const movedColumn = columnOrderAnnouncement
    ? leafColumns.find((column) => column.id === columnOrderAnnouncement.columnId)
    : undefined;
  return (
    <details className="table-column-menu" {...columnPopover}>
      <summary>
        <Columns3 size={15} />
        {t("列")}
      </summary>
      <fieldset>
        <legend>{t("列设置")}</legend>
        {leafColumns.map((column, index) => {
          const label = columnLabel(column);
          const visible = column.getIsVisible();
          return (
            <div className="table-column-option" key={column.id}>
              <input
                type="checkbox"
                checked={visible}
                disabled={preferenceControlsDisabled || (visible && visibleColumnCount === 1)}
                aria-label={t("显示列：{column}", { column: label })}
                onChange={column.getToggleVisibilityHandler()}
              />
              <span>{label}</span>
              <fieldset className="table-column-order-controls">
                <legend className="sr-only">{t("调整列顺序：{column}", { column: label })}</legend>
                <button
                  type="button"
                  aria-label={t("上移列：{column}", { column: label })}
                  title={t("上移{column}", { column: label })}
                  disabled={preferenceControlsDisabled || index === 0}
                  onClick={() => moveColumn(column.id, -1)}
                >
                  <ChevronUp size={13} />
                </button>
                <button
                  type="button"
                  aria-label={t("下移列：{column}", { column: label })}
                  title={t("下移{column}", { column: label })}
                  disabled={preferenceControlsDisabled || index === leafColumns.length - 1}
                  onClick={() => moveColumn(column.id, 1)}
                >
                  <ChevronDown size={13} />
                </button>
              </fieldset>
              {visible ? <Check size={13} aria-hidden="true" /> : null}
            </div>
          );
        })}
      </fieldset>
      <span className="sr-only" aria-live="polite">
        {columnOrderAnnouncement && movedColumn
          ? t("{column}已移至第{index}列", {
              column: columnLabel(movedColumn),
              index: columnOrderAnnouncement.index,
            })
          : ""}
      </span>
    </details>
  );
}
