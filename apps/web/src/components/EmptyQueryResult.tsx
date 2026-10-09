import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";
import { EmptyState } from "./common";

/** Zero visible records is a query/permission boundary, not a scientific absence claim. */
export function EmptyQueryResult({
  domain,
  filtered,
  onClear,
}: {
  domain: string;
  filtered: boolean;
  onClear?: () => void;
}) {
  useLocale();
  return (
    <EmptyState
      title={filtered ? t("未找到匹配记录") : t("暂无可查询的{domain}", { domain })}
      detail={
        filtered
          ? t("可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。")
          : t("当前组织尚无可见的已发布记录，请确认数据接入、发布状态与访问权限。")
      }
    >
      {filtered && onClear ? (
        <button className="secondary-button" type="button" onClick={onClear}>
          {t("清除筛选条件")}
        </button>
      ) : null}
    </EmptyState>
  );
}
