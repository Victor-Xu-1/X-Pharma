import { X } from "lucide-react";
import { type FormEvent, useId } from "react";
import { useModalFocus } from "../lib/useModalFocus";

export function ResearchMetadataDialog({
  title,
  open,
  name,
  description,
  pending,
  error,
  onNameChange,
  onDescriptionChange,
  onClose,
  onSubmit,
}: {
  title: string;
  open: boolean;
  name: string;
  description: string;
  pending: boolean;
  error: string;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const titleId = useId();
  const dialogRef = useModalFocus<HTMLFormElement>(open, onClose, { closeOnEscape: !pending });
  if (!open) return null;
  return (
    <div className="modal-scrim" role="presentation">
      <form
        ref={dialogRef}
        className="workspace-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onSubmit={onSubmit}
      >
        <header>
          <h2 id={titleId}>{title}</h2>
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
        <label>
          业务说明
          <textarea
            value={description}
            onChange={(event) => onDescriptionChange(event.target.value)}
            maxLength={1000}
            rows={4}
            placeholder="记录适用场景、筛选口径或交付用途"
          />
        </label>
        <footer>
          <button className="secondary-button" type="button" onClick={onClose} disabled={pending}>
            取消
          </button>
          <button className="primary-button" type="submit" disabled={pending || !name.trim()}>
            {pending ? "保存中" : "保存修改"}
          </button>
        </footer>
      </form>
    </div>
  );
}
