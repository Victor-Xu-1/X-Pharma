import { Activity, ChevronLeft, ChevronRight } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import type { GovernanceRunStatus, loadGovernanceRuns } from "../../lib/contracts/governance";
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
  if (loading) return <Spinner label="正在读取 AI 治理运行" />;
  if (error && !page) return <ErrorState message={error} retry={onRetry} />;
  const items = page?.items ?? [];
  const selected = items.find((item) => item.id === selectedRunId) ?? items[0] ?? null;
  const limit = page?.limit ?? 30;
  return (
    <>
      <div className="governance-run-toolbar">
        <label>
          <span>运行状态</span>
          <select value={status} onChange={(event) => onStatus(event.target.value as GovernanceRunStatus | "all")}>
            <option value="all">全部</option>
            <option value="pending">等待中</option>
            <option value="running">运行中</option>
            <option value="succeeded">成功</option>
            <option value="partial">部分成功</option>
            <option value="failed">失败</option>
            <option value="canceled">已取消</option>
          </select>
        </label>
        <span>
          共 <strong>{page?.total ?? 0}</strong> 次运行
        </span>
        {page ? (
          <code title={page.current_policy_sha256}>当前策略 {page.current_policy_sha256.slice(0, 12)}</code>
        ) : null}
      </div>
      {!items.length ? (
        <EmptyState title="当前筛选下没有 AI 治理运行" />
      ) : (
        <section className="governance-layout">
          <aside className="review-list">
            <div className="review-list-head">
              <Activity size={19} />
              <span>
                <strong>{items.length}</strong> 条运行记录
              </span>
            </div>
            {items.map((run) => (
              <button
                key={run.id}
                type="button"
                className={selected?.id === run.id ? "active" : ""}
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
      <nav className="governance-run-pagination" aria-label="AI 治理运行分页">
        <button
          type="button"
          title="上一页"
          aria-label="AI 治理运行上一页"
          disabled={offset === 0}
          onClick={() => onOffset(Math.max(0, offset - limit))}
        >
          <ChevronLeft size={17} />
        </button>
        <span>{page?.total ? `${offset + 1}-${Math.min(offset + limit, page.total)} / ${page.total}` : "0 / 0"}</span>
        <button
          type="button"
          title="下一页"
          aria-label="AI 治理运行下一页"
          disabled={!page || offset + limit >= page.total}
          onClick={() => onOffset(offset + limit)}
        >
          <ChevronRight size={17} />
        </button>
      </nav>
    </>
  );
}
