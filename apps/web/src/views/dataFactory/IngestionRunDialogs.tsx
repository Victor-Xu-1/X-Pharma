import { CircleStop, RotateCcw, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { FormStatus } from "../../components/FormStatus";
import type { IngestionRun } from "../../lib/contracts/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";

export function ReplayRunDialog({
  run,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  run: IngestionRun;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (operationKey: string, reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [operationKey] = useState(() => `ingestion-replay:${run.id}:${crypto.randomUUID()}`);
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length < 3 || busy) return;
    await onConfirm(operationKey, reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-busy={busy}
        aria-labelledby="replay-run-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">INGESTION RECOVERY</p>
            <h2 id="replay-run-title">重放入库运行</h2>
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
            将按当前数据源治理配置重新扫描；原运行与发现项保持不变，新运行会单独记录并写入审计日志。
          </p>
          <label>
            <span>原工作流</span>
            <input value={run.workflow_id} readOnly className="mono-cell" />
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
          <FormStatus pending={busy} error={error} pendingLabel="正在提交重放请求" />
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

export function CancelRunDialog({
  run,
  busy,
  error,
  onClose,
  onConfirm,
}: {
  run: IngestionRun;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (operationKey: string, reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [operationKey] = useState(() => `ingestion-cancel:${run.id}:${crypto.randomUUID()}`);
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length < 3 || busy) return;
    await onConfirm(operationKey, reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-busy={busy}
        aria-labelledby="cancel-run-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">CONTROLLED CANCELLATION</p>
            <h2 id="cancel-run-title">取消入库运行</h2>
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
            取消请求只发送到该运行绑定的 Temporal 执行。已完成的不可变快照会保留，后续阶段将在安全检查点停止。
          </p>
          <label>
            <span>运行关联标识</span>
            <input value={run.workflow_id} readOnly className="mono-cell" />
          </label>
          <label>
            <span>取消原因</span>
            <textarea
              disabled={busy}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              maxLength={500}
              required
            />
          </label>
          <FormStatus pending={busy} error={error} pendingLabel="正在提交取消请求" />
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={onClose} disabled={busy}>
              返回
            </button>
            <button className="danger-button" type="submit" disabled={busy || reason.trim().length < 3}>
              <CircleStop size={15} />
              {busy ? "正在取消" : "确认取消"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
