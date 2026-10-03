import { X } from "lucide-react";
import type { FormEvent } from "react";
import type { ReplayAction } from "./types";

export function BillingReplayModal({
  action,
  reason,
  busy,
  onReason,
  onClose,
  onSubmit,
}: {
  action: ReplayAction;
  reason: string;
  busy: boolean;
  onReason: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="billing-replay-title">
        <header>
          <div>
            <p className="eyebrow">DEAD LETTER</p>
            <h2 id="billing-replay-title">重放账单投递</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.delivery.statement_key}
            <span>{action.delivery.last_error ?? "--"}</span>
          </p>
          <label>
            <span>重放原因</span>
            <textarea
              rows={4}
              required
              minLength={3}
              maxLength={500}
              value={reason}
              onChange={(event) => onReason(event.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              确认重放
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
