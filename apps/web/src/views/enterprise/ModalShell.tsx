import { X } from "lucide-react";
import type { ReactNode } from "react";
import { FormStatus } from "../../components/FormStatus";
import { useLocale } from "../../lib/i18n";
import { enterpriseWorkspaceText as t } from "../../lib/i18n/enterpriseWorkspace";
import { useModalFocus } from "../../lib/useModalFocus";
import { useEnterpriseOperationContext } from "./useEnterpriseOperationBoundary";

export function ModalShell({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  useLocale();
  const boundary = useEnterpriseOperationContext();
  const busy = Boolean(boundary?.busy);
  const dialogRef = useModalFocus<HTMLDivElement>(true, close, { closeOnEscape: !busy });

  return (
    <div className="modal-backdrop" role="presentation">
      <div
        ref={dialogRef}
        className="modal-panel enterprise-modal-panel"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <header>
          <h2>{title}</h2>
          <button
            className="icon-button"
            type="button"
            onClick={close}
            title={t("关闭")}
            aria-label={t("关闭")}
            disabled={busy}
          >
            <X size={18} />
          </button>
        </header>
        <FormStatus pending={busy} error={boundary?.actionError ?? ""} />
        <fieldset className="enterprise-form-boundary" disabled={busy}>
          {children}
        </fieldset>
      </div>
    </div>
  );
}
