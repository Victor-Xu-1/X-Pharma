import { tableText as t } from "./i18n/table";

type PresentationColumn = { id: string; columnDef: { header?: unknown } };

export function columnLabel(column: PresentationColumn): string {
  return typeof column.columnDef.header === "string" ? column.columnDef.header : column.id;
}

export function describeTableSorting(
  sorting: readonly { id: string; desc: boolean }[],
  columns: readonly PresentationColumn[],
  scope: "all" | "page",
  defaultDescription?: string,
): string {
  const scopeLabel = scope === "all" ? t("全部结果") : t("当前页");
  if (sorting.length) {
    const description = sorting
      .map((sort) => {
        const column = columns.find((candidate) => candidate.id === sort.id);
        return t("{column}{direction}", {
          column: column ? columnLabel(column) : sort.id,
          direction: sort.desc ? t("降序") : t("升序"),
        });
      })
      .join(t("、"));
    return t("{scope}按{sort}", { scope: scopeLabel, sort: description });
  }
  return defaultDescription
    ? t("{scope}{description}", { scope: scopeLabel, description: defaultDescription })
    : t("{scope}未排序", { scope: scopeLabel });
}
