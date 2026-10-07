import { X } from "lucide-react";
import type { FormEvent } from "react";
import { FormStatus } from "../../components/FormStatus";
import type { BillingDisputeAction } from "../../lib/contracts/commercial";
import { useModalFocus } from "../../lib/useModalFocus";
import type { DisputeCaseAction } from "./types";

export function BillingDisputeTransitionModal({
  action,
  notes,
  assignee,
  units,
  adjustmentKey,
  busy,
  error = "",
  onAction,
  onNotes,
  onAssignee,
  onUnits,
  onAdjustmentKey,
  onClose,
  onSubmit,
}: {
  action: DisputeCaseAction;
  notes: string;
  assignee: string;
  units: string;
  adjustmentKey: string;
  busy: boolean;
  error?: string;
  onAction: (value: BillingDisputeAction) => void;
  onNotes: (value: string) => void;
  onAssignee: (value: string) => void;
  onUnits: (value: string) => void;
  onAdjustmentKey: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });
  const credit = action.action === "resolve_credit";
  const valid = notes.trim().length >= 3 && (!credit || (Number(units) > 0 && adjustmentKey.trim().length >= 8));
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="transition-dispute-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">BILLING DISPUTE</p>
            <h2 id="transition-dispute-title">处理计费争议</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭" disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.dispute.subject}
            <span>{action.dispute.description}</span>
            <span className="mono-cell">
              争议额度 {action.dispute.disputed_units} · 版本 {action.dispute.version}
            </span>
          </p>
          <label>
            <span>处理动作</span>
            <select
              aria-label="争议处理动作"
              disabled={busy}
              value={action.action}
              onChange={(event) => onAction(event.target.value as BillingDisputeAction)}
            >
              {action.dispute.status === "open" ? <option value="investigate">受理并调查</option> : null}
              {action.dispute.status === "investigating" ? <option value="resolve_no_credit">确认无退款</option> : null}
              {action.dispute.status === "investigating" ? <option value="resolve_credit">退款额度</option> : null}
              {action.dispute.status === "investigating" ? <option value="reject">驳回</option> : null}
              <option value="cancel">取消案件</option>
            </select>
          </label>
          <label>
            <span>负责人</span>
            <input
              disabled={busy}
              maxLength={500}
              value={assignee}
              onChange={(event) => onAssignee(event.target.value)}
            />
          </label>
          {credit ? (
            <>
              <label>
                <span>退款额度</span>
                <input
                  aria-label="退款额度"
                  disabled={busy}
                  type="number"
                  min="0.00000001"
                  max={action.dispute.disputed_units}
                  step="0.00000001"
                  required
                  value={units}
                  onChange={(event) => onUnits(event.target.value)}
                />
              </label>
              <label>
                <span>账本调整键</span>
                <input
                  aria-label="账本调整键"
                  disabled={busy}
                  minLength={8}
                  maxLength={199}
                  required
                  value={adjustmentKey}
                  onChange={(event) => onAdjustmentKey(event.target.value)}
                />
              </label>
            </>
          ) : null}
          <label>
            <span>处理记录</span>
            <textarea
              aria-label="争议处理记录"
              disabled={busy}
              rows={4}
              minLength={3}
              maxLength={4000}
              required
              value={notes}
              onChange={(event) => onNotes(event.target.value)}
            />
          </label>
          <FormStatus pending={busy} error={error} />
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || !valid}>
              提交处理
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
