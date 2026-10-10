import { Database, RotateCcw } from "lucide-react";
import { formatDate, Spinner, StatusBadge } from "../../components/common";
import type { loadProjectionMaintenanceJobs } from "../../lib/contracts/governance";

export function ProjectionMaintenancePanel({
  jobs,
  loading,
  error,
  busy,
  onRequest,
  onRefresh,
}: {
  jobs: Awaited<ReturnType<typeof loadProjectionMaintenanceJobs>>;
  loading: boolean;
  error: string;
  busy: boolean;
  onRequest: (operation: "consistency_check" | "rebuild") => void;
  onRefresh: () => void;
}) {
  const latest = jobs[0] ?? null;
  const active = latest?.status === "queued" || latest?.status === "running";
  const expected = latest?.result.expected_counts as Record<string, number> | undefined;
  const actual = latest?.result.actual_counts as Record<string, number> | undefined;
  return (
    <section className="projection-maintenance" aria-labelledby="projection-maintenance-title">
      <header>
        <span>
          <Database size={17} />
          <strong id="projection-maintenance-title">检索投影维护</strong>
        </span>
        <div>
          <button className="icon-button" type="button" title="刷新投影任务" onClick={onRefresh}>
            <RotateCcw size={15} />
          </button>
          <button type="button" disabled={busy || active} onClick={() => onRequest("consistency_check")}>
            一致性检查
          </button>
          <button
            className="danger-button"
            type="button"
            disabled={busy || active}
            onClick={() => onRequest("rebuild")}
          >
            原子重建全局投影
          </button>
        </div>
      </header>
      {loading ? <Spinner label="正在读取投影维护任务" /> : null}
      {latest ? (
        <div className="projection-maintenance-result">
          <span>
            <StatusBadge value={latest.status} />
            <strong>{latest.operation === "consistency_check" ? "一致性检查" : "全局原子重建"}</strong>
            <small>{formatDate(latest.created_at, true)}</small>
          </span>
          {expected && actual ? (
            <dl>
              {Object.keys(expected).map((kind) => (
                <div key={kind}>
                  <dt>{kind}</dt>
                  <dd>
                    {actual[kind] ?? 0} / {expected[kind] ?? 0}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
          {latest.last_error ? <p>{latest.last_error}</p> : null}
        </div>
      ) : (
        <p className="field-help">尚无投影维护任务。</p>
      )}
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
