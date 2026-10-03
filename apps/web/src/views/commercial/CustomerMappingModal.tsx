import { X } from "lucide-react";
import type { FormEvent } from "react";
import type { MappingAction } from "./types";

export function CustomerMappingModal({
  action,
  externalReference,
  reason,
  busy,
  onExternalReference,
  onReason,
  onClose,
  onSubmit,
}: {
  action: MappingAction;
  externalReference: string;
  reason: string;
  busy: boolean;
  onExternalReference: (value: string) => void;
  onReason: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="customer-mapping-title">
        <header>
          <div>
            <p className="eyebrow">BILLING PROVIDER</p>
            <h2 id="customer-mapping-title">配置客户编号</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.account.display_name}
            <span className="mono-cell">{action.account.account_key}</span>
          </p>
          <label>
            <span>Provider 客户编号</span>
            <input
              required
              minLength={1}
              maxLength={500}
              pattern="[A-Za-z0-9][A-Za-z0-9._:/-]{0,499}"
              autoComplete="off"
              value={externalReference}
              onChange={(event) => onExternalReference(event.target.value)}
            />
          </label>
          <label>
            <span>变更原因</span>
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
            <button
              className="primary-button"
              type="submit"
              disabled={busy || externalReference.trim().length < 1 || reason.trim().length < 3}
            >
              保存映射
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
