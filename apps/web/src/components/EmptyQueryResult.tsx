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
  return (
    <EmptyState
      title={filtered ? "未找到匹配记录" : `暂无可查询的${domain}`}
      detail={
        filtered
          ? "可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"
          : "当前组织尚无可见的已发布记录，请确认数据接入、发布状态与访问权限。"
      }
    >
      {filtered && onClear ? (
        <button className="secondary-button" type="button" onClick={onClear}>
          清除筛选条件
        </button>
      ) : null}
    </EmptyState>
  );
}
