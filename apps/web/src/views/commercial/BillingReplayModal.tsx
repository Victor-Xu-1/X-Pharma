import { X } from "lucide-react";
import type { FormEvent } from "react";
import { FormStatus } from "../../components/FormStatus";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { useModalFocus } from "../../lib/useModalFocus";
import type { ReplayAction } from "./types";

export function BillingReplayModal({
  action,
  reason,
  busy,
  error = "",
  onReason,
  onClose,
  onSubmit,
}: {
  action: ReplayAction;
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
        aria-labelledby="billing-replay-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">DEAD LETTER</p>
            <h2 id="billing-replay-title">{t("重放账单投递")}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t("关闭")} disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.delivery.statement_key}
            <span>{action.delivery.last_error ?? "--"}</span>
          </p>
          <label>
            <span>{t("重放原因")}</span>
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
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              {t("确认重放")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
