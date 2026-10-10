import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useLocale } from "../../lib/i18n";
import { commercialRecordText as t } from "../../lib/i18n/commercialRecordDetails";
import { useModalFocus } from "../../lib/useModalFocus";

export function RecordInspectionDialog({
  id,
  name,
  children,
  onClose,
}: {
  id: string;
  name: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useLocale();
  const ref = useModalFocus<HTMLElement>(true, onClose);
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={ref}
        id={id}
        className="modal-panel commercial-record-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby={id + "-title"}
        tabIndex={-1}
      >
        <header>
          <h2 id={id + "-title"}>{t("{name} 的记录详情", { name })}</h2>
          <button className="icon-button" type="button" aria-label={t("关闭")} onClick={onClose}>
            <X size={18} />
          </button>
        </header>
        <div className="commercial-record-body">{children}</div>
      </section>
    </div>
  );
}
