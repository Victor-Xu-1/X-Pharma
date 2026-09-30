import { X } from "lucide-react";
import type { FormEvent } from "react";
import { useModalFocus } from "../lib/useModalFocus";

export function SavedSearchDialog({
  open,
  domainLabel,
  name,
  shared,
  monitor,
  allowMonitor = true,
  error = "",
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
  error?: string;
  pending: boolean;
  onNameChange: (value: string) => void;
  onSharedChange: (value: boolean) => void;
  onMonitorChange: (value: boolean) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
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
        tabIndex={-1}
        onSubmit={onSubmit}
      >
        <header>
          <h2 id="saved-search-dialog-title">保存当前{domainLabel}检索</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭" disabled={pending}>
            <X size={18} />
          </button>
        </header>
        {error ? (
          <p className="inline-error" role="alert">
            {error}
          </p>
        ) : null}
        <label>
          名称
          <input
            value={name}
            onChange={(event) => onNameChange(event.target.value)}
            data-modal-autofocus="true"
            maxLength={200}
            required
          />
        </label>
        <label className="check-control">
          <input type="checkbox" checked={shared} onChange={(event) => onSharedChange(event.target.checked)} />
          企业内共享该检索
        </label>
        {allowMonitor ? (
          <label className="check-control">
            <input type="checkbox" checked={monitor} onChange={(event) => onMonitorChange(event.target.checked)} />
            同时订阅相关数据变更
          </label>
        ) : null}
        <footer>
          <button className="secondary-button" type="button" onClick={onClose} disabled={pending}>
            取消
          </button>
          <button className="primary-button" type="submit" disabled={pending || !name.trim()}>
            {pending ? "保存中" : "确认保存"}
          </button>
        </footer>
      </form>
    </div>
  );
}
