import { RotateCcw, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { FormStatus } from "../../components/FormStatus";
import type { SourceVersionReplayStage } from "../../lib/contracts/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";

export const VERSION_REPLAY_STAGE_LABELS: Record<SourceVersionReplayStage, string> = {
  malware_scan: "安全扫描",
  parse: "文档解析",
  governance: "AI 治理",
  retrieval: "检索投影",
};

export function ReplayVersionDialog({
  versionNumber,
  errorCode,
  stages,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  versionNumber: number;
  errorCode: string | null;
  stages: SourceVersionReplayStage[];
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (operationKey: string, fromStage: SourceVersionReplayStage, reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [fromStage, setFromStage] = useState<SourceVersionReplayStage>(stages.at(-1) ?? "malware_scan");
  const [operationKey] = useState(() => `source-version-replay:${crypto.randomUUID()}`);
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length < 3 || busy) return;
    await onConfirm(operationKey, fromStage, reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-busy={busy}
        aria-labelledby="replay-version-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">VERSION RECOVERY</p>
            <h2 id="replay-version-title">重放源版本 {versionNumber}</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={busy}
            title="关闭"
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </header>
        <form onSubmit={submit}>
          <p className="field-help">
            恢复只复用已成功且仍可核验的前序产物，并从所选阶段重置后续状态。当前失败代码：
            <span className="mono-cell">{errorCode ?? "无（阶段状态失败）"}</span>
          </p>
          <label>
            <span>恢复起点</span>
            <select
              disabled={busy}
              value={fromStage}
              onChange={(event) => setFromStage(event.target.value as SourceVersionReplayStage)}
            >
              {stages.map((stage) => (
                <option key={stage} value={stage}>
                  {VERSION_REPLAY_STAGE_LABELS[stage]}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>重放原因</span>
            <textarea
              disabled={busy}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              maxLength={500}
              required
            />
          </label>
          <FormStatus pending={busy} error={error} pendingLabel="正在提交版本重放请求" />
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              <RotateCcw size={15} />
              {busy ? "正在提交" : "确认重放"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
