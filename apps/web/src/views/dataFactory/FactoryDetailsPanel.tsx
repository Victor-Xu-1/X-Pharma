import { ChevronDown } from "lucide-react";
import { type ReactNode, type Ref, useEffect, useState } from "react";

/** Native disclosure only; query state and operational actions stay with their existing owners. */
export function FactoryDetailsPanel({
  title,
  summary,
  reveal = false,
  className = "",
  panelRef,
  children,
}: {
  title: string;
  summary: ReactNode;
  reveal?: boolean;
  className?: string;
  panelRef?: Ref<HTMLDetailsElement>;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(reveal);
  useEffect(() => {
    if (reveal) setOpen(true);
  }, [reveal]);
  return (
    <details
      ref={panelRef}
      className={["pipeline-panel", "factory-details-panel", className].filter(Boolean).join(" ")}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <h2>{title}</h2>
        <span className="factory-panel-meta">{summary}</span>
        <ChevronDown size={16} className="disclosure-chevron" aria-hidden="true" />
      </summary>
      <div className="factory-details-content">{children}</div>
    </details>
  );
}
