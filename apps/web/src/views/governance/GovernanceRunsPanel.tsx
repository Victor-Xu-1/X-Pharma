import { Activity, ChevronLeft, ChevronRight } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import type { GovernanceRunStatus, loadGovernanceRuns } from "../../lib/contracts/governance";
import { useLocale } from "../../lib/i18n";
import { governanceRunText as t } from "../../lib/i18n/governanceRuns";
import { GovernanceRunDetail } from "./GovernanceRunDetail";

export function GovernanceRunsPanel({
  page,
  loading,
  error,
  status,
  offset,
  selectedRunId,
  onStatus,
  onOffset,
  onSelect,
  onRetry,
}: {
  page: Awaited<ReturnType<typeof loadGovernanceRuns>> | null;
  loading: boolean;
  error: string;
  status: GovernanceRunStatus | "all";
  offset: number;
  selectedRunId: string;
  onStatus: (value: GovernanceRunStatus | "all") => void;
  onOffset: (value: number) => void;
  onSelect: (value: string) => void;
  onRetry: () => void;
}) {
  useLocale();
  if (loading) return <Spinner label={t("正在读取AI治理运行")} />;
  if (error && !page) return <ErrorState message={error} retry={onRetry} />;
  const items = page?.items ?? [];
  const selected = items.find((item) => item.id === selectedRunId) ?? items[0] ?? null;
  const limit = page?.limit ?? 30;
  return (
    <>
      {error ? (
        <>
          <p role="status" className="field-help">
            {t("刷新失败；当前显示上次读取的运行记录。")}
          </p>
          <ErrorState message={error} retry={onRetry} />
        </>
      ) : null}
      <div className="governance-run-toolbar">
        <label>
          <span>{t("运行状态")}</span>
          <select
            aria-label={t("运行状态")}
            value={status}
            onChange={(event) => onStatus(event.target.value as GovernanceRunStatus | "all")}
          >
            <option value="all">{t("全部")}</option>
            <option value="pending">{t("等待中")}</option>
            <option value="running">{t("运行中")}</option>
            <option value="succeeded">{t("成功")}</option>
            <option value="partial">{t("部分成功")}</option>
            <option value="failed">{t("失败")}</option>
            <option value="canceled">{t("已取消")}</option>
          </select>
        </label>
        <span>{t("共 {count} 次运行", { count: page?.total ?? 0 })}</span>
        {page ? (
          <code title={page.current_policy_sha256}>
            {t("当前策略 {hash}", { hash: page.current_policy_sha256.slice(0, 12) })}
          </code>
        ) : null}
      </div>
      {!items.length ? (
        <EmptyState title={t("当前筛选下没有AI治理运行")} />
      ) : (
        <section className="governance-layout">
          <aside className="review-list">
            <div className="review-list-head">
              <Activity size={19} />
              <span>{t("{count} 条运行记录", { count: items.length })}</span>
            </div>
            {items.map((run) => (
              <button
                key={run.id}
                type="button"
                className={selected?.id === run.id ? "active" : ""}
                aria-pressed={selected?.id === run.id}
                onClick={() => onSelect(run.id)}
              >
                <div>
                  <strong>{run.source_file_name}</strong>
                  <StatusBadge value={run.status} />
                </div>
                <p>{run.model_name}</p>
                <small>
                  {run.schema_name} {run.schema_version} · {formatDate(run.created_at, true)}
                </small>
              </button>
            ))}
          </aside>
          <GovernanceRunDetail run={selected} />
        </section>
      )}
      <nav className="governance-run-pagination" aria-label={t("AI治理运行分页")}>
        <button
          type="button"
          title={t("上一页")}
          aria-label={t("AI治理运行上一页")}
          disabled={offset === 0}
          onClick={() => onOffset(Math.max(0, offset - limit))}
        >
          <ChevronLeft size={17} />
        </button>
        <span>
          {page?.total && items.length
            ? `${page.offset + 1}-${Math.min(page.offset + items.length, page.total)} / ${page.total}`
            : `0 / ${page?.total ?? 0}`}
        </span>
        <button
          type="button"
          title={t("下一页")}
          aria-label={t("AI治理运行下一页")}
          disabled={!page || offset + limit >= page.total}
          onClick={() => onOffset(offset + limit)}
        >
          <ChevronRight size={17} />
        </button>
      </nav>
    </>
  );
}
