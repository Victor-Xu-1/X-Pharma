import { type LucideIcon, X } from "lucide-react";
import { type FormEvent, type ReactNode, useRef, useState } from "react";
import { FormStatus } from "../../components/FormStatus";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";

type Props = {
  title: string;
  titleId: string;
  description: ReactNode;
  children?: ReactNode;
  operationKeyPrefix: string;
  reasonLabel: string;
  pendingLabel: string;
  confirmLabel: string;
  pendingConfirmLabel: string;
  cancelLabel?: string;
  icon: LucideIcon;
  danger?: boolean;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (key: string, reason: string) => Promise<void>;
};

/** Shared reason/focus presentation. The caller owns the request, error and recovery state. */
export function FactoryReasonDialog({
  title,
  titleId,
  description,
  children,
  operationKeyPrefix,
  reasonLabel,
  pendingLabel,
  confirmLabel,
  pendingConfirmLabel,
  cancelLabel = t("取消"),
  icon: Icon,
  danger = false,
  busy,
  error,
  onClose,
  onConfirm,
}: Props) {
  useLocale();
  const [reason, setReason] = useState("");
  const [operationKey] = useState(() => `${operationKeyPrefix}:${crypto.randomUUID()}`);
  const locked = useRef(false);
  const dismiss = () => {
    if (!busy && !locked.current) onClose();
  };
  const dialogRef = useModalFocus<HTMLElement>(true, dismiss, { closeOnEscape: !busy });
  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = reason.trim();
    if (locked.current || busy || value.length < 3 || value.length > 500) return;
    locked.current = true;
    try {
      await onConfirm(operationKey, value);
    } finally {
      locked.current = false;
    }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-busy={busy}
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header>
          <h2 id={titleId}>{title}</h2>
          <button
            className="icon-button"
            type="button"
            onClick={dismiss}
            disabled={busy}
            title={t("关闭")}
            aria-label={t("关闭")}
          >
            <X size={18} aria-hidden="true" />
          </button>
        </header>
        <form onSubmit={submit}>
          <p className="field-help">{description}</p>
          {children}
          <label>
            <span>{reasonLabel}</span>
            <textarea
              disabled={busy}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              minLength={3}
              maxLength={500}
              required
            />
          </label>
          <FormStatus pending={busy} error={error} pendingLabel={pendingLabel} />
          <div className="form-actions">
            <button className="secondary-button" type="button" onClick={dismiss} disabled={busy}>
              {cancelLabel}
            </button>
            <button
              className={danger ? "danger-button" : "primary-button"}
              type="submit"
              disabled={busy || reason.trim().length < 3 || reason.trim().length > 500}
            >
              <Icon size={15} aria-hidden="true" />
              {busy ? pendingConfirmLabel : confirmLabel}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
