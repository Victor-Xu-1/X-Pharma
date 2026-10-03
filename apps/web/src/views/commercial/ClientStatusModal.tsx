import { X } from "lucide-react";
import type { FormEvent } from "react";
import type { ClientAction } from "./types";

export function ClientStatusModal({
  action,
  reason,
  busy,
  onReason,
  onClose,
  onSubmit,
}: {
  action: ClientAction;
  reason: string;
  busy: boolean;
  onReason: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="client-status-title">
        <header>
          <div>
            <p className="eyebrow">AGENT CLIENT</p>
            <h2 id="client-status-title">{action.active ? "重新启用客户端" : "停用客户端"}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.client.display_name}
            <span className="mono-cell">{action.client.client_key}</span>
          </p>
          <label>
            <span>操作原因</span>
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
              className={action.active ? "primary-button" : "danger-button"}
              type="submit"
              disabled={busy || reason.trim().length < 3}
            >
              {action.active ? "确认启用" : "确认停用"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
