import { X } from "lucide-react";
import { useState } from "react";
import { useLocale } from "../../lib/i18n";
import { governanceMaintenanceText as t } from "../../lib/i18n/governanceMaintenance";
import { useModalFocus } from "../../lib/useModalFocus";

export function ProjectionRebuildDialog({
  open,
  busy,
  ready,
  error,
  onClose,
  onConfirm,
}: {
  open: boolean;
  busy: boolean;
  ready: boolean;
  error: string;
  onClose: () => void;
  onConfirm: () => void;
}) {
  useLocale();
  const ref = useModalFocus<HTMLFormElement>(open, onClose, { closeOnEscape: !busy });
  const [acknowledged, setAcknowledged] = useState(false);
  if (!open) return null;
  return (
    <div className="modal-scrim" role="presentation">
      <form
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="projection-rebuild-title"
        aria-busy={busy}
        className="projection-rebuild-dialog"
        tabIndex={-1}
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy && ready && acknowledged) onConfirm();
        }}
      >
        <header>
          <h2 id="projection-rebuild-title">{t("重建全局检索投影")}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label={t("关闭重建确认")}
            disabled={busy}
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </header>
        <div className="projection-rebuild-body">
          <p>
            {t(
              "该操作影响所有组织的检索投影。构建新索引并校验后，后台才执行原子切换；不会直接改写 PostgreSQL 权威事实。",
            )}
          </p>
          <label className="check-control">
            <input
              type="checkbox"
              checked={acknowledged}
              disabled={busy}
              onChange={(event) => setAcknowledged(event.target.checked)}
            />
            <span>{t("我确认需要重建所有组织的全局检索投影")}</span>
          </label>
          <p className="field-help">{t("任务受理不代表重建成功，请查看后台任务状态与结果。")}</p>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
        <footer className="form-actions">
          <button type="button" disabled={busy} onClick={onClose}>
            {t("取消")}
          </button>
          <button type="submit" className="danger-button" disabled={busy || !ready || !acknowledged}>
            {t("确认重建")}
          </button>
        </footer>
      </form>
    </div>
  );
}
