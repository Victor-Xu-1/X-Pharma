import { ChevronLeft } from "lucide-react";
import { researchReturnLabel } from "./locationModel";
import type { ResearchRouteContext } from "./routeContext";

export function ResearchReturnControl({ context }: { context: ResearchRouteContext }) {
  const { activeReturnLocation, location, navigate } = context;
  // These dossiers already expose the same validated source in their header/back action.
  if (!activeReturnLocation || ["drug", "target", "trials"].includes(location.view)) return null;
  return (
    <button className="trial-back-button" type="button" onClick={() => navigate(activeReturnLocation, true, true)}>
      <ChevronLeft size={16} aria-hidden="true" />
      {researchReturnLabel(activeReturnLocation)}
    </button>
  );
}
