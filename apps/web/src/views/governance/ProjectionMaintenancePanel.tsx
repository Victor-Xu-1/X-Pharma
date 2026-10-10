import { Database, RotateCcw } from "lucide-react";
import { formatDate, Spinner, StatusBadge } from "../../components/common";
import type { loadProjectionMaintenanceJobs } from "../../lib/contracts/governance";
import { useLocale } from "../../lib/i18n";
import { governanceMaintenanceText as t } from "../../lib/i18n/governanceMaintenance";
import { projectionCountRows, projectionCountValue } from "./projectionCounts";

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
  useLocale();
  const latest = jobs[0] ?? null;
  const active = jobs.some((job) => job.status === "queued" || job.status === "running");
  const counts = latest ? projectionCountRows(latest.result) : [];
  return (
    <section className="projection-maintenance" aria-labelledby="projection-maintenance-title">
      <header>
        <span>
          <Database size={17} />
          <strong id="projection-maintenance-title">{t("检索投影维护")}</strong>
        </span>
        <div>
          <button
            className="icon-button"
            type="button"
            title={t("刷新投影任务")}
            aria-label={t("刷新投影任务")}
            disabled={loading}
            onClick={onRefresh}
          >
            <RotateCcw size={15} />
          </button>
          <button
            type="button"
            disabled={busy || loading || Boolean(error) || active}
            onClick={() => onRequest("consistency_check")}
          >
            {t("一致性检查")}
          </button>
          <button
            className="danger-button"
            type="button"
            disabled={busy || loading || Boolean(error) || active}
            onClick={() => onRequest("rebuild")}
          >
            {t("原子重建全局投影")}
          </button>
        </div>
      </header>
      {loading ? <Spinner label={t("正在读取投影维护任务")} /> : null}
      {latest ? (
        <div className="projection-maintenance-result">
          <span>
            <StatusBadge value={latest.status} />
            <strong>{t(latest.operation === "consistency_check" ? "一致性检查" : "全局原子重建")}</strong>
            <small>{formatDate(latest.created_at, true)}</small>
          </span>
          {counts.length ? (
            <dl>
              {counts.map((row) => (
                <div key={row.kind}>
                  <dt>{row.kind}</dt>
                  <dd>
                    {projectionCountValue(row.actual, t("未上报"))} / {projectionCountValue(row.expected, t("未上报"))}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}
          {latest.last_error ? <p>{latest.last_error}</p> : null}
        </div>
      ) : !loading && !error ? (
        <p className="field-help">{t("尚无投影维护任务")}</p>
      ) : null}
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
