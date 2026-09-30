import { lazy, Suspense, useCallback, useEffect, useState } from "react";

import { AccessDeniedState, Spinner } from "./components/common";
import { SessionBoundary } from "./components/SessionBoundary";
import { WorkspaceShell } from "./components/WorkspaceShell";
import type { AuthMode } from "./lib/contracts/session";
import type { User } from "./lib/types";
import {
  canAccessView,
  canAccessWorkbench,
  parseWorkbenchLocation,
  type ViewKey,
  type WorkspaceLocation,
  workbenchForView,
  workspaceUrl,
} from "./lib/workspaceRouting";

const CommercialView = lazy(() =>
  import("./views/CommercialView").then((module) => ({ default: module.CommercialView })),
);
const DataFactoryView = lazy(() =>
  import("./views/DataFactoryView").then((module) => ({ default: module.DataFactoryView })),
);
const EnterpriseView = lazy(() =>
  import("./views/EnterpriseView").then((module) => ({ default: module.EnterpriseView })),
);
const GovernanceView = lazy(() =>
  import("./views/GovernanceView").then((module) => ({ default: module.GovernanceView })),
);

export function InternalApp() {
  return (
    <SessionBoundary workbench="internal">
      {({ authMode, user, logout }) => <InternalWorkspace authMode={authMode} user={user} onLogout={logout} />}
    </SessionBoundary>
  );
}

function InternalWorkspace({ authMode, user, onLogout }: { authMode: AuthMode; user: User; onLogout: () => void }) {
  const [location, setLocation] = useState<WorkspaceLocation>(() =>
    parseWorkbenchLocation("internal", window.location.search),
  );

  useEffect(() => {
    const canonicalUrl = workspaceUrl(location);
    if (`${window.location.pathname}${window.location.search}` !== canonicalUrl) {
      window.history.replaceState(null, "", canonicalUrl);
    }
  }, [location]);

  useEffect(() => {
    const popState = () => setLocation(parseWorkbenchLocation("internal", window.location.search));
    window.addEventListener("popstate", popState);
    return () => window.removeEventListener("popstate", popState);
  }, []);

  const navigateToView = useCallback((view: ViewKey, replace = false) => {
    if (workbenchForView(view) !== "internal") return;
    const next: WorkspaceLocation = {
      workbench: "internal",
      view,
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
    };
    const method = replace ? "replaceState" : "pushState";
    window.history[method](null, "", workspaceUrl(next));
    setLocation(next);
  }, []);

  if (!canAccessWorkbench("internal", user.role)) {
    return (
      <div className="session-loading">
        <AccessDeniedState onReturn={onLogout} actionLabel="退出内部工作台" />
      </div>
    );
  }

  const allowed = canAccessView(location.view, user.role);
  return (
    <WorkspaceShell
      user={user}
      activeWorkbench="internal"
      activeView={location.view}
      onView={navigateToView}
      onLogout={onLogout}
    >
      <Suspense fallback={<Spinner label="正在加载内部工作区" />}>
        {!allowed ? <AccessDeniedState onReturn={() => navigateToView("factory", true)} /> : null}
        {allowed && location.view === "factory" ? <DataFactoryView user={user} /> : null}
        {allowed && location.view === "governance" ? <GovernanceView /> : null}
        {allowed && location.view === "commercial" ? <CommercialView /> : null}
        {allowed && location.view === "enterprise" ? <EnterpriseView user={user} authMode={authMode} /> : null}
      </Suspense>
    </WorkspaceShell>
  );
}
