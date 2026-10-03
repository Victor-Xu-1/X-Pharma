import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useModalFocus } from "../../lib/useModalFocus";

export function ModalShell({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const dialogRef = useModalFocus<HTMLDivElement>(true, close);

  return (
    <div className="modal-backdrop" role="presentation">
      <div ref={dialogRef} className="modal-panel" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
        <header>
          <h2>{title}</h2>
          <button className="icon-button" type="button" onClick={close} title="关闭" aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
