import { researchWorkflowForView } from "../lib/workspace/researchNavigation";
import type { ViewKey } from "../lib/workspaceRouting";

export function ResearchViewNavigation({
  activeView,
  onView,
}: {
  activeView: ViewKey;
  onView: (view: ViewKey) => void;
}) {
  const workflow = researchWorkflowForView(activeView);
  // Dossiers already own their section tabs and return control; do not stack another navigation row there.
  if (!workflow || workflow.destinations.length < 2 || !workflow.destinations.some((item) => item.view === activeView))
    return null;
  return (
    <nav className="view-tabs research-view-navigation" aria-label={`${workflow.label}分类`}>
      {workflow.destinations.map(({ view, label }) => (
        <button
          key={view}
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
