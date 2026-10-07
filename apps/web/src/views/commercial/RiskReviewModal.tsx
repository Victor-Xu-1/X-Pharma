import { X } from "lucide-react";
import type { FormEvent } from "react";
import { FormStatus } from "../../components/FormStatus";
import { useModalFocus } from "../../lib/useModalFocus";
import type { RiskAction } from "./types";

export function RiskReviewModal({
  action,
  reason,
  busy,
  error = "",
  onReason,
  onStatus,
  onClose,
  onSubmit,
}: {
  action: RiskAction;
  reason: string;
  busy: boolean;
  error?: string;
  onReason: (value: string) => void;
  onStatus: (status: RiskAction["status"]) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="risk-review-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">POLICY RISK</p>
            <h2 id="risk-review-title">处置风险事件</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭" disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.event.client_name}
            <span>{action.event.reason_code}</span>
          </p>
          <label>
            <span>处置状态</span>
            <select
              disabled={busy}
              value={action.status}
              onChange={(event) => onStatus(event.target.value as RiskAction["status"])}
            >
              <option value="acknowledged">已确认</option>
              <option value="resolved">已解决</option>
              <option value="dismissed">不构成风险</option>
            </select>
          </label>
          <label>
            <span>处置记录</span>
            <textarea
              disabled={busy}
              rows={4}
              maxLength={2000}
              value={reason}
              onChange={(event) => onReason(event.target.value)}
            />
          </label>
          <FormStatus pending={busy} error={error} />
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy}>
              提交处置
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
