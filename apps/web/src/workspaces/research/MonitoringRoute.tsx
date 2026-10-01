import { lazy } from "react";
import type { ResearchRouteContext } from "./routeContext";

const MonitoringView = lazy(() =>
  import("../../views/MonitoringView").then((module) => ({ default: module.MonitoringView })),
);

export function MonitoringRoute({ context }: { context: ResearchRouteContext }) {
  const { location, navigate, openEntityById, openSavedSearch, user } = context;
  return (
    <MonitoringView
      user={user}
      activeTab={location.monitoringTab ?? "alerts"}
      onOpenEntity={openEntityById}
      onOpenSearch={openSavedSearch}
      onTabChange={(monitoringTab) => {
        if (monitoringTab !== (location.monitoringTab ?? "alerts")) {
          navigate({ ...location, monitoringTab });
        }
      }}
    />
  );
}
