import { lazy } from "react";
import type { ResearchRouteContext } from "./routeContext";

const OverviewView = lazy(() =>
  import("../../views/OverviewView").then((module) => ({ default: module.OverviewView })),
);

export function OverviewRoute({ context }: { context: ResearchRouteContext }) {
  const { user, onLogout, onUserUpdated } = context;
  return <OverviewView user={user} onLogout={onLogout} onUserUpdated={onUserUpdated} />;
}
