import { ChevronDown } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { t, useLocale } from "../lib/i18n";
import { useCompactNavigation } from "../lib/useCompactNavigation";
import "./ResponsiveDirectory.css";

/** Presentation only: retain children/drafts and never own a query, route or permission. */
export function ResponsiveDirectory({
  selectedKey,
  title,
  summary,
  icon,
  className,
  contentClassName = "",
  children,
}: {
  selectedKey: string | null;
  title: string;
  summary: string;
  icon: ReactNode;
  className: string;
  contentClassName?: string;
  children: (collapse: () => void) => ReactNode;
}) {
  useLocale();
  const compact = useCompactNavigation();
  const [expandedFor, setExpandedFor] = useState<string | null>(null);
  const contentId = useId();
  const contentRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const visible = !compact || !selectedKey || expandedFor === selectedKey;
  useEffect(() => {
    if (!visible && contentRef.current?.contains(document.activeElement))
      toggleRef.current?.focus({ preventScroll: true });
  }, [visible]);
  return (
    <aside className={className} aria-label={title}>
      {compact && selectedKey ? (
        <button
          ref={toggleRef}
          className="responsive-directory-toggle"
          type="button"
          aria-label={visible ? t("收起{title}", { title }) : t("展开{title}", { title })}
          aria-expanded={visible}
          aria-controls={contentId}
          onClick={() => setExpandedFor(visible ? null : selectedKey)}
        >
          {icon}
          <strong>{title}</strong>
          <span>{visible ? t("检索与筛选") : summary}</span>
          <ChevronDown size={17} aria-hidden="true" data-expanded={visible} />
        </button>
      ) : null}
      <div
        id={contentId}
        ref={contentRef}
        className={`responsive-directory-content ${contentClassName}`.trim()}
        hidden={!visible}
      >
        {children(() => setExpandedFor(null))}
      </div>
    </aside>
  );
}
