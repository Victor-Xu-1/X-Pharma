import { useRef } from "react";
import { t, useLocale } from "../lib/i18n";
import { useHorizontalActiveItem } from "../lib/useHorizontalActiveItem";
import { researchWorkflowForView } from "../lib/workspace/researchNavigation";
import type { ViewKey } from "../lib/workspaceRouting";

export function ResearchViewNavigation({
  activeView,
  onView,
}: {
  activeView: ViewKey;
  onView: (view: ViewKey) => void;
}) {
  useLocale();
  const navigationRef = useRef<HTMLElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);
  const workflow = researchWorkflowForView(activeView);
  const destinations = workflow?.destinations.map(({ view, label }) => ({ key: view, label: t(label) })) ?? [];
  useHorizontalActiveItem(navigationRef, selectedRef, destinations, activeView);
  // Dossiers already own their section tabs and return control; do not stack another navigation row there.
  if (!workflow || workflow.destinations.length < 2 || !workflow.destinations.some((item) => item.view === activeView))
    return null;
  return (
    <nav
      ref={navigationRef}
      className="view-tabs research-view-navigation"
      aria-label={t("{workflow}分类", { workflow: t(workflow.label) })}
    >
      {destinations.map(({ key: view, label }) => (
        <button
          key={view}
          ref={view === activeView ? selectedRef : undefined}
          type="button"
          className={view === activeView ? "active" : undefined}
          aria-current={view === activeView ? "page" : undefined}
          onClick={() => {
            if (view !== activeView) onView(view);
          }}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
