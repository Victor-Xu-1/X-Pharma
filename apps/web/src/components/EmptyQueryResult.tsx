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
    <div className="state-message empty-state" role="status" aria-live="polite" aria-atomic="true">
      <strong>{filtered ? "未找到匹配记录" : `暂无可查询的${domain}`}</strong>
      <span>
        {filtered
          ? "可调整或清除筛选条件。查询仅覆盖当前组织有权访问的已发布数据，不代表相关研究不存在。"
          : "当前组织尚无可见的已发布记录，请确认数据接入、发布状态与访问权限。"}
      </span>
      {filtered && onClear ? (
        <button className="secondary-button" type="button" onClick={onClear}>
          清除筛选条件
        </button>
      ) : null}
    </div>
  );
}
