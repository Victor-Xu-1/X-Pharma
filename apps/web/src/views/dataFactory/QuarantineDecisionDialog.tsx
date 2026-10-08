import { useQuery } from "@tanstack/react-query";
import { ShieldAlert, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { FormStatus } from "../../components/FormStatus";
import type { QuarantineAction, QuarantineCase } from "../../lib/contracts/dataFactory";
import { dataFactoryKeys, decideQuarantineCase, loadQuarantineCase } from "../../lib/contracts/dataFactory";
import { quarantineStatusLabel } from "../../lib/quarantinePresentation";
import { useModalFocus } from "../../lib/useModalFocus";

const QUARANTINE_ACTION_LABELS: Record<QuarantineAction, string> = {
  hold: "留置待审",
  reject: "永久拒绝",
  rescan: "重新安全扫描",
};

const QUARANTINE_DECISION_LABELS: Record<string, string> = {
  scan_detected: "扫描发现威胁",
  hold: "留置待审",
  reject: "永久拒绝",
  rescan: "申请重新扫描",
  scan_clean: "复扫结果清洁",
  rescan_failed: "复扫启动失败",
};

function availableQuarantineActions(status: QuarantineCase["quarantine_status"]): QuarantineAction[] {
  if (status === "pending_review") return ["hold", "reject", "rescan"];
  if (status === "held") return ["reject", "rescan"];
  return [];
}

export function QuarantineDecisionDialog({
  versionId,
  canManage,
  onClose,
  onDecided,
}: {
  versionId: string;
  canManage: boolean;
  onClose: () => void;
  onDecided: () => Promise<void>;
}) {
  const quarantine = useQuery({
    queryKey: dataFactoryKeys.quarantine(versionId),
    queryFn: ({ signal }) => loadQuarantineCase(versionId, signal),
  });
  const caseData = quarantine.data;
  const actions = caseData ? availableQuarantineActions(caseData.quarantine_status) : [];
  const [action, setAction] = useState<QuarantineAction>("hold");
  const [reason, setReason] = useState("");
  const [operationKey, setOperationKey] = useState(() => `quarantine-decision:${crypto.randomUUID()}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState("");
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });

  useEffect(() => {
    if (actions.length > 0 && !actions.includes(action)) setAction(actions[0]);
  }, [action, actions]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!caseData || !actions.includes(action) || reason.trim().length < 3 || busy) return;
    setBusy(true);
    setError("");
    setAccepted("");
    try {
      const result = await decideQuarantineCase(versionId, {
        operation_key: operationKey,
        expected_version: caseData.quarantine_version,
        action,
        reason: reason.trim(),
      });
      setAccepted(
        result.action === "rescan"
          ? `复扫工作流已提交：${result.workflow_id ?? "等待运行标识"}`
          : `处置已记录：${QUARANTINE_ACTION_LABELS[result.action]}`,
      );
      setReason("");
      setOperationKey(`quarantine-decision:${crypto.randomUUID()}`);
      await onDecided();
      await quarantine.refetch();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "隔离案件处置失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel quarantine-dialog"
        role="dialog"
        aria-modal="true"
        aria-busy={busy}
        aria-labelledby="quarantine-dialog-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">MALWARE QUARANTINE</p>
            <h2 id="quarantine-dialog-title">隔离案件处置</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={busy}
            title="关闭隔离案件"
            aria-label="关闭隔离案件"
          >
            <X size={18} />
          </button>
        </header>
        {quarantine.isPending ? <Spinner label="正在读取隔离案件" /> : null}
        {quarantine.error instanceof Error ? (
          <div className="quarantine-dialog-state">
            <ErrorState message={quarantine.error.message} retry={() => void quarantine.refetch()} />
          </div>
        ) : null}
        {caseData ? (
          <form onSubmit={submit}>
            <dl className="quarantine-case-summary">
              <div>
                <dt>文件</dt>
                <dd>{caseData.file_name}</dd>
              </div>
              <div>
                <dt>状态</dt>
                <dd>
                  <StatusBadge
                    value={caseData.quarantine_status}
                    label={quarantineStatusLabel(caseData.quarantine_status)}
                  />
                </dd>
              </div>
              <div>
                <dt>来源路径</dt>
                <dd className="mono-cell">{caseData.logical_path}</dd>
              </div>
              <div>
                <dt>威胁签名</dt>
                <dd className="quarantine-threat">{caseData.threat_name ?? "未披露"}</dd>
              </div>
              <div>
                <dt>决策版本</dt>
                <dd>v{caseData.quarantine_version}</dd>
              </div>
              <div>
                <dt>最近变更</dt>
                <dd>{formatDate(caseData.updated_at, true)}</dd>
              </div>
            </dl>

            <div className="quarantine-safety-note" role="note">
              <ShieldAlert size={17} />
              <span>重新扫描只会从恶意文件扫描阶段启动，仍强制经过 ClamAV；不会直接进入解析、AI 治理或检索发布。</span>
            </div>

            <section className="quarantine-history" aria-labelledby="quarantine-history-title">
              <h3 id="quarantine-history-title">不可变处置历史</h3>
              {caseData.decisions?.length ? (
                <ol>
                  {caseData.decisions.map((decision) => (
                    <li key={decision.id}>
                      <span className="quarantine-history-version">v{decision.resulting_version}</span>
                      <span>
                        <strong>{QUARANTINE_DECISION_LABELS[decision.action] ?? decision.action}</strong>
                        <small>
                          {decision.actor_id} · {formatDate(decision.created_at, true)}
                        </small>
                        <p>{decision.reason}</p>
                      </span>
                      <StatusBadge value={decision.resulting_status} />
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="field-help">尚无处置历史，案件数据不完整，请联系平台管理员。</p>
              )}
            </section>

            {canManage && actions.length ? (
              <>
                <label>
                  <span>处置动作</span>
                  <select
                    disabled={busy}
                    value={action}
                    onChange={(event) => {
                      setAction(event.target.value as QuarantineAction);
                      setOperationKey(`quarantine-decision:${crypto.randomUUID()}`);
                      setError("");
                    }}
                  >
                    {actions.map((item) => (
                      <option key={item} value={item}>
                        {QUARANTINE_ACTION_LABELS[item]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>处置原因</span>
                  <textarea
                    disabled={busy}
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    minLength={3}
                    maxLength={500}
                    required
                  />
                </label>
              </>
            ) : (
              <p className="field-help">
                {canManage ? "当前案件状态没有可执行的人工动作。" : "当前账号仅可查看隔离案件与审计历史。"}
              </p>
            )}
            {accepted ? (
              <div className="inline-success" role="status">
                {accepted}
              </div>
            ) : null}
            <FormStatus
              pending={busy}
              error={error}
              pendingLabel={accepted ? "正在刷新隔离案件状态" : "正在提交隔离处置"}
            />
            <div className="form-actions">
              <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>
                关闭
              </button>
              {canManage && actions.length ? (
                <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
                  <ShieldAlert size={15} />
                  {busy ? "正在提交" : "提交处置"}
                </button>
              ) : null}
            </div>
          </form>
        ) : null}
      </section>
    </div>
  );
}
