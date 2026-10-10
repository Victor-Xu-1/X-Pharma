import { X } from "lucide-react";
import type { FormEvent } from "react";
import { FormStatus } from "../../components/FormStatus";
import { useLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { useModalFocus } from "../../lib/useModalFocus";
import type { MappingAction } from "./types";

export function CustomerMappingModal({
  action,
  externalReference,
  reason,
  busy,
  error = "",
  onExternalReference,
  onReason,
  onClose,
  onSubmit,
}: {
  action: MappingAction;
  externalReference: string;
  reason: string;
  busy: boolean;
  error?: string;
  onExternalReference: (value: string) => void;
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
        aria-labelledby="customer-mapping-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">BILLING PROVIDER</p>
            <h2 id="customer-mapping-title">{t("配置客户编号")}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t("关闭")} disabled={busy}>
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.account.display_name}
            <span className="mono-cell">{action.account.account_key}</span>
          </p>
          <label>
            <span>{t("Provider 客户编号")}</span>
            <input
              disabled={busy}
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
            <span>{t("变更原因")}</span>
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
              className="primary-button"
              type="submit"
              disabled={busy || externalReference.trim().length < 1 || reason.trim().length < 3}
            >
              {t("保存映射")}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
