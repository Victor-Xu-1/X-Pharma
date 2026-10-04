import { formatDate } from "../../components/common";
import type { DataSourceReadinessRead } from "../../lib/generated/models/DataSourceReadinessRead";

const PHASE_NAMES = { backfill: "历史回填", incremental: "更新同步", reconcile: "完整复核", full_scan: "机制复核" };

export function SourceSyncStatus({ readiness }: { readiness?: DataSourceReadinessRead }) {
  const sync = readiness?.sync_status;
  if (!sync) return null;
  return (
    <section className="source-sync-status" aria-label="持续同步进度">
      <strong>
        {PHASE_NAMES[sync.phase]} · {sync.pending ? "分批同步中" : "本周期完成"}
      </strong>
      <span>本周期已处理 {sync.processed_records} 条记录</span>
      {sync.window_start && sync.window_end ? (
        <span>
          当前日期分区：{sync.window_start} — {sync.window_end}
        </span>
      ) : null}
      {sync.completed_through ? <span>已完成覆盖截至 {sync.completed_through}（仅限配置查询）</span> : null}
      {sync.last_completed_at ? <span>最近完整周期：{formatDate(sync.last_completed_at, true)}</span> : null}
    </section>
  );
}
