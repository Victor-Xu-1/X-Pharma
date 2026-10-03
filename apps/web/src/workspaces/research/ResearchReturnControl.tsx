import { ChevronLeft } from "lucide-react";
import { researchReturnLabel } from "./locationModel";
import type { ResearchRouteContext } from "./routeContext";

export function ResearchReturnControl({ context }: { context: ResearchRouteContext }) {
  const { activeReturnLocation, navigate } = context;
  if (!activeReturnLocation) return null;
  return (
    <button className="trial-back-button" type="button" onClick={() => navigate(activeReturnLocation, true, true)}>
      <ChevronLeft size={16} aria-hidden="true" />
      {researchReturnLabel(activeReturnLocation)}
    </button>
  );
}
