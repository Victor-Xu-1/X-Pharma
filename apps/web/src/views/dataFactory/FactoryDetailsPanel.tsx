import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

/** Native disclosure only; query state and operational actions stay with their existing owners. */
export function FactoryDetailsPanel({
  title,
  summary,
  reveal = false,
  className = "",
  children,
}: {
  title: string;
  summary: ReactNode;
  reveal?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <details
      className={["pipeline-panel", "factory-details-panel", className].filter(Boolean).join(" ")}
      open={reveal || undefined}
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
