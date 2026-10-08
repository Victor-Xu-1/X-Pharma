import { X } from "lucide-react";
import type { FormEvent } from "react";
import { useLocale } from "../lib/i18n";
import { queryText as t } from "../lib/i18n/query";
import { useModalFocus } from "../lib/useModalFocus";
import { FormStatus } from "./FormStatus";

export function SavedSearchDialog({
  open,
  domainLabel,
  name,
  shared,
  monitor,
  allowMonitor = true,
  error,
  pending,
  onNameChange,
  onSharedChange,
  onMonitorChange,
  onClose,
  onSubmit,
}: {
  open: boolean;
  domainLabel: string;
  name: string;
  shared: boolean;
  monitor: boolean;
  allowMonitor?: boolean;
  error: string;
  pending: boolean;
  onNameChange: (value: string) => void;
  onSharedChange: (value: boolean) => void;
  onMonitorChange: (value: boolean) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  useLocale();
  const dialogRef = useModalFocus<HTMLFormElement>(open, onClose, { closeOnEscape: !pending });
  if (!open) return null;
  return (
    <div className="modal-scrim" role="presentation">
      <form
        ref={dialogRef}
        className="workspace-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="saved-search-dialog-title"
        aria-busy={pending || undefined}
        tabIndex={-1}
        onSubmit={(event) => {
          if (pending) event.preventDefault();
          else onSubmit(event);
        }}
      >
        <header>
          <h2 id="saved-search-dialog-title">
            {domainLabel ? t("保存当前{domain}检索", { domain: domainLabel }) : t("保存当前检索")}
          </h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label={t("关闭")} disabled={pending}>
            <X size={18} />
          </button>
        </header>
        <FormStatus pending={pending} error={error} pendingLabel={t("正在保存检索")} />
        <label>
          {t("名称")}
          <input
            value={name}
            disabled={pending}
            onChange={(event) => onNameChange(event.target.value)}
            data-modal-autofocus="true"
            maxLength={200}
            required
          />
        </label>
        <label className="check-control">
          <input
            type="checkbox"
            disabled={pending}
            checked={shared}
            onChange={(event) => onSharedChange(event.target.checked)}
          />
          {t("企业内共享该检索")}
        </label>
        {allowMonitor ? (
          <label className="check-control">
            <input
              type="checkbox"
              disabled={pending}
              checked={monitor}
              onChange={(event) => onMonitorChange(event.target.checked)}
            />
            {t("同时订阅相关数据变更")}
          </label>
        ) : null}
        <footer>
          <button className="secondary-button" type="button" onClick={onClose} disabled={pending}>
            {t("取消")}
          </button>
          <button className="primary-button" type="submit" disabled={pending || !name.trim()}>
            {pending ? t("保存中") : t("确认保存")}
          </button>
        </footer>
      </form>
    </div>
  );
}
