import { ChevronLeft } from "lucide-react";
import { researchReturnLabel } from "./locationModel";
import type { ResearchRouteContext } from "./routeContext";

export function ResearchReturnControl({ context }: { context: ResearchRouteContext }) {
  const { activeReturnLocation, navigate } = context;
  if (!activeReturnLocation) return null;
  return (
    <button
      className="trial-back-button"
      type="button"
      title="保留最近两级与起始研究；更早访问可使用浏览器后退"
      onClick={() => navigate(activeReturnLocation, true, true)}
    >
      <ChevronLeft size={16} aria-hidden="true" />
      {researchReturnLabel(activeReturnLocation)}
    </button>
  );
}
