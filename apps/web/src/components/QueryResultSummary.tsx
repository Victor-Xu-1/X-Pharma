import { formatDate } from "./common";

/** Query execution time is not the source's last-updated timestamp. */
export function QueryResultSummary({
  total,
  offset,
  count,
  unit,
  queriedAt,
  note,
  showRange = true,
}: {
  total: number;
  offset: number;
  count: number;
  unit: string;
  queriedAt: string;
  note?: string;
  showRange?: boolean;
}) {
  const start = total > 0 && count > 0 ? offset + 1 : 0;
  const end = Math.min(offset + count, total);
  return (
    <div className="result-summary">
      <strong>{total}</strong>
      <span>{unit}</span>
      <small>
        {showRange && start > 0 ? `${start}–${end} · ` : null}
        <time dateTime={queriedAt} title="本次查询时间，不代表来源数据的最后更新时间；来源日期请查看具体记录。">
          查询时间 {formatDate(queriedAt, true)}
        </time>
        {note ? ` · ${note}` : null}
      </small>
    </div>
  );
}
