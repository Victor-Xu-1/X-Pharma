import { RefreshCw, ScanSearch, X } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ApiError } from "../../lib/api";
import type { IngestionFinding, IngestionRun } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";
import { RunStageGraph, runStageLabel } from "./RunStagePresentation";

export function FindingsDrawer({
  run,
  findings,
  error,
  retry,
  onClose,
  historical = false,
  refreshing = false,
}: {
  run: IngestionRun;
  findings: IngestionFinding[] | null;
  error: Error | null;
  retry: () => void;
  onClose: () => void;
  historical?: boolean;
  refreshing?: boolean;
}) {
  useLocale();
  const denied = error instanceof ApiError && [401, 403].includes(error.status);
  const failedStages = run.stages
    .filter((stage) => stage.status === "failed")
    .map((stage) => runStageLabel(stage.stage));
  const failureMessage = denied
    ? null
    : run.error_summary
      ? run.error_summary
      : failedStages.length
        ? t("运行在{stages}阶段失败，未生成发现项。请查看阶段详情，并在确认原因后重放。", {
            stages: failedStages.join(" / "),
          })
        : null;
  const dialogRef = useModalFocus<HTMLElement>(true, onClose);

  return (
    <div className="drawer-backdrop" role="presentation">
      <aside
        ref={dialogRef}
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="finding-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <h2 id="finding-title">{t("运行发现项")}</h2>
            {!denied ? <small className="mono-cell">{run.workflow_id}</small> : null}
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={retry}
            disabled={refreshing}
            title={t("刷新运行详情")}
            aria-label={t("刷新运行详情")}
          >
            <RefreshCw size={18} aria-hidden="true" />
          </button>
          <button className="icon-button" type="button" onClick={onClose} title={t("关闭")} aria-label={t("关闭")}>
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          {!denied && historical ? (
            <p className="field-help" role="status">
              {t("阶段信息来自上次读取，尚未重新确认当前状态。")}
            </p>
          ) : null}
          {!denied ? <RunStageGraph run={run} /> : null}
          {failureMessage ? (
            <div className="factory-warning" role="status">
              <ScanSearch size={17} />
              <span>
                <strong>{t("运行说明")}</strong>
                {failureMessage}
              </span>
            </div>
          ) : null}
          {error ? <ErrorState message={error.message} retry={retry} /> : null}
          {error && !denied && findings !== null ? (
            <p className="field-help">{t("上次读取的发现项（非实时）")}</p>
          ) : null}
          {denied || (error && findings === null) ? null : findings === null ? (
            <Spinner />
          ) : findings.length ? (
            findings.map((finding) => (
              <article className="finding-record" key={finding.id}>
                <div>
                  <StatusBadge value={finding.stage} label={runStageLabel(finding.stage)} />
                  <span className="mono-cell">{finding.code}</span>
                </div>
                <strong>{finding.message}</strong>
                <p className="mono-cell">{finding.source_path}</p>
                <small>
                  {formatDate(finding.occurred_at, true)} · {t(finding.retryable ? "可重试" : "不可重试")}
                </small>
              </article>
            ))
          ) : failureMessage || error ? null : (
            <EmptyState title={t("该运行没有发现项")} />
          )}
        </div>
      </aside>
    </div>
  );
}
