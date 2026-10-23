import { formatDate } from "../../components/common";
import type { DataSourceReadinessRead } from "../../lib/generated/models/DataSourceReadinessRead";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";

const PHASE_NAMES = {
  backfill: "历史回填",
  incremental: "更新同步",
  reconcile: "完整复核",
  full_scan: "机制复核",
} as const;

export function SourceSyncStatus({ readiness }: { readiness?: DataSourceReadinessRead }) {
  useLocale();
  const sync = readiness?.sync_status;
  if (!sync) return null;
  return (
    <section className="source-sync-status" aria-label={t("持续同步进度")}>
      <strong>
        {Object.hasOwn(PHASE_NAMES, sync.phase) ? t(PHASE_NAMES[sync.phase]) : sync.phase} ·{" "}
        {t(sync.pending ? "分批同步中" : "本周期完成")}
      </strong>
      <span>{t("本周期已处理 {count} 条记录", { count: sync.processed_records })}</span>
      {sync.window_start && sync.window_end ? (
        <span>{t("当前日期分区：{from} — {to}", { from: sync.window_start, to: sync.window_end })}</span>
      ) : null}
      {sync.completed_through ? (
        <span>{t("已完成覆盖截至 {date}（仅限配置查询）", { date: sync.completed_through })}</span>
      ) : null}
      {sync.last_completed_at ? (
        <span>{t("最近完整周期：{date}", { date: formatDate(sync.last_completed_at, true) })}</span>
      ) : null}
    </section>
  );
}
