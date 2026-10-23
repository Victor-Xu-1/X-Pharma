import { X } from "lucide-react";
import type { FormEvent } from "react";
import { FormStatus } from "../../components/FormStatus";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { useModalFocus } from "../../lib/useModalFocus";
import type { ClientAction } from "./types";

export function ClientStatusModal({
  action,
  reason,
  busy,
  error = "",
  onReason,
  onClose,
  onSubmit,
}: {
  action: ClientAction;
  reason: string;
  busy: boolean;
  error?: string;
  onReason: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  useLocale();
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !busy });
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="client-status-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">AGENT CLIENT</p>
            <h2 id="client-status-title">{action.active ? t("重新启用客户端") : t("停用客户端")}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t("关闭")} disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.client.display_name}
            <span className="mono-cell">{action.client.client_key}</span>
          </p>
          <label>
            <span>{t("操作原因")}</span>
            <textarea
              disabled={busy}
              rows={4}
              required
              minLength={3}
              maxLength={500}
              value={reason}
              onChange={(event) => onReason(event.target.value)}
            />
          </label>
          <FormStatus pending={busy} error={error} />
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose} disabled={busy}>
              {t("取消")}
            </button>
            <button
              className={action.active ? "primary-button" : "danger-button"}
              type="submit"
              disabled={busy || reason.trim().length < 3}
            >
              {action.active ? t("确认启用") : t("确认停用")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
