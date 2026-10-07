import { X } from "lucide-react";
import type { FormEvent } from "react";
import { FormStatus } from "../../components/FormStatus";
import type { BillingDisputeCategory } from "../../lib/contracts/commercial";
import { useModalFocus } from "../../lib/useModalFocus";
import type { CreateDisputeAction } from "./types";

export function CreateBillingDisputeModal({
  action,
  category,
  units,
  subject,
  description,
  busy,
  error = "",
  onCategory,
  onUnits,
  onSubject,
  onDescription,
  onClose,
  onSubmit,
}: {
  action: CreateDisputeAction;
  category: BillingDisputeCategory;
  units: string;
  subject: string;
  description: string;
  busy: boolean;
  error?: string;
  onCategory: (value: BillingDisputeCategory) => void;
  onUnits: (value: string) => void;
  onSubject: (value: string) => void;
  onDescription: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const valid = Number(units) > 0 && subject.trim().length >= 3 && description.trim().length >= 3;
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-dispute-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">BILLING DISPUTE</p>
            <h2 id="create-dispute-title">发起计费争议</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭" disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.delivery.statement_key}
            <span className="mono-cell">{action.delivery.billing_account_name}</span>
          </p>
          <label>
            <span>争议类别</span>
            <select
              disabled={busy}
              value={category}
              onChange={(event) => onCategory(event.target.value as BillingDisputeCategory)}
            >
              <option value="usage">用量</option>
              <option value="pricing">定价</option>
              <option value="duplicate">重复计费</option>
              <option value="authorization">授权</option>
              <option value="service">服务</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>
            <span>争议额度</span>
            <input
              aria-label="争议额度"
              disabled={busy}
              type="number"
              min="0.00000001"
              step="0.00000001"
              required
              value={units}
              onChange={(event) => onUnits(event.target.value)}
            />
          </label>
          <label>
            <span>主题</span>
            <input
              aria-label="争议主题"
              disabled={busy}
              minLength={3}
              maxLength={200}
              required
              value={subject}
              onChange={(event) => onSubject(event.target.value)}
            />
          </label>
          <label>
            <span>争议说明</span>
            <textarea
              aria-label="争议说明"
              disabled={busy}
              rows={4}
              minLength={3}
              maxLength={4000}
              required
              value={description}
              onChange={(event) => onDescription(event.target.value)}
            />
          </label>
          <FormStatus pending={busy} error={error} />
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose} disabled={busy}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || !valid}>
              提交争议
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
