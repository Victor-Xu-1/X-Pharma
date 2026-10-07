import { X } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { useModalFocus } from "../lib/useModalFocus";
import "./InlineEntityLinks.css";

type LinkItem = { key: string; label: string };

/** Presentation only: preserves the complete authorized records and exact IDs
 * supplied by its caller. Does not infer a primary scientific relationship. */
export function InlineEntityLinks<Item extends LinkItem>({
  label,
  items,
  onSelect,
  compact = true,
}: {
  label: string;
  items: readonly Item[];
  onSelect: (item: Item) => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const first = items[0];
  const dialogRef = useModalFocus<HTMLElement>(open && Boolean(first), () => setOpen(false));
  useEffect(() => {
    if (!items.length) setOpen(false);
  }, [items.length]);
  if (!first) return <span>--</span>;

  return (
    <span className={compact ? "inline-entity-links" : "inline-entity-links entity-link-stack"}>
      {(compact ? [first] : items).map((item) => (
        <button
          key={item.key}
          className="inline-entity-primary"
          type="button"
          title={item.label}
          onClick={() => onSelect(item)}
        >
          {item.label}
        </button>
      ))}
      {compact && items.length > 1 ? (
        <button
          className="inline-entity-more"
          type="button"
          aria-label={`查看 ${label}（${items.length} 项）`}
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => setOpen(true)}
        >
          +{items.length - 1}
        </button>
      ) : null}
      {open
        ? createPortal(
            <div className="modal-backdrop" role="presentation">
              <section
                ref={dialogRef}
                className="modal-panel"
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                tabIndex={-1}
              >
                <header>
                  <h2 id={titleId}>{label}</h2>
                  <button
                    className="icon-button"
                    type="button"
                    aria-label="关闭关联列表"
                    onClick={() => setOpen(false)}
                  >
                    <X size={18} aria-hidden="true" />
                  </button>
                </header>
                <ul className="entity-link-list">
                  {items.map((item) => (
                    <li key={item.key}>
                      <button
                        type="button"
                        onClick={() => {
                          setOpen(false);
                          onSelect(item);
                        }}
                      >
                        {item.label}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            </div>,
            document.body,
          )
        : null}
    </span>
  );
}
