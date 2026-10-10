import { ScanSearch, X } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import type { IngestionFinding, IngestionRun } from "../../lib/contracts/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";
import { runStageLabel, RunStageGraph } from "./RunStagePresentation";

export function FindingsDrawer({
  run,
  findings,
  error,
  retry,
  onClose,
}: {
  run: IngestionRun;
  findings: IngestionFinding[] | null;
  error: string;
  retry: () => void;
  onClose: () => void;
}) {
  const failedStages = run.stages
    .filter((stage) => stage.status === "failed")
    .map((stage) => runStageLabel(stage.stage));
  const failureMessage = run.error_summary
    ? run.error_summary
    : failedStages.length
      ? `运行在${failedStages.join("、")}阶段失败，未生成发现项。请查看阶段详情，并在确认原因后重放。`
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
            <p className="eyebrow">INGESTION FINDINGS</p>
            <h2 id="finding-title">运行发现项</h2>
            <small className="mono-cell">{run.workflow_id}</small>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="关闭" aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          <RunStageGraph run={run} />
          {failureMessage ? (
            <div className="factory-warning" role="status">
              <ScanSearch size={17} />
              <span>
                <strong>运行说明</strong>
                {failureMessage}
              </span>
            </div>
          ) : null}
          {error ? (
            <ErrorState message={error} retry={retry} />
          ) : findings === null ? (
            <Spinner />
          ) : findings.length ? (
            findings.map((finding) => (
              <article className="finding-record" key={finding.id}>
                <div>
                  <StatusBadge value={finding.stage} />
                  <span className="mono-cell">{finding.code}</span>
                </div>
                <strong>{finding.message}</strong>
                <p className="mono-cell">{finding.source_path}</p>
                <small>
                  {formatDate(finding.occurred_at, true)} · {finding.retryable ? "可重试" : "不可重试"}
                </small>
              </article>
            ))
          ) : failureMessage ? null : (
            <EmptyState title="该运行没有发现项" />
          )}
        </div>
      </aside>
    </div>
  );
}
