import { X } from "lucide-react";
import type { FormEvent } from "react";
import type { RiskAction } from "./types";

export function RiskReviewModal({
  action,
  reason,
  busy,
  onReason,
  onStatus,
  onClose,
  onSubmit,
}: {
  action: RiskAction;
  reason: string;
  busy: boolean;
  onReason: (value: string) => void;
  onStatus: (status: RiskAction["status"]) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="risk-review-title">
        <header>
          <div>
            <p className="eyebrow">POLICY RISK</p>
            <h2 id="risk-review-title">处置风险事件</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
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
            <select value={action.status} onChange={(event) => onStatus(event.target.value as RiskAction["status"])}>
              <option value="acknowledged">已确认</option>
              <option value="resolved">已解决</option>
              <option value="dismissed">不构成风险</option>
            </select>
          </label>
          <label>
            <span>处置记录</span>
            <textarea rows={4} maxLength={2000} value={reason} onChange={(event) => onReason(event.target.value)} />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
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
