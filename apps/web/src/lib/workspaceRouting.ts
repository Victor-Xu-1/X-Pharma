import { views, workbenchForView } from "./workspace/catalog";
import { parseWorkspaceQuery } from "./workspace/queryParser";
import { serializeWorkspaceLocation } from "./workspace/querySerializer";
import type { ViewKey, WorkbenchKey, WorkspaceLocation } from "./workspace/types";

export {
  canAccessView,
  canAccessWorkbench,
  defaultViewForWorkbench,
  workbenchForView,
  workbenchPath,
} from "./workspace/catalog";
export * from "./workspace/types";

const maximumReturnPathLength = 4_096;

const entityDossierViews: ReadonlySet<ViewKey> = new Set(["drug", "target", "company", "disease", "entity"]);

/** Parse only bounded, same-workbench context; never follow a referrer or browser history blindly. */
export function researchReturnLocation(value: string | null | undefined): WorkspaceLocation | null {
  return parseResearchReturnLocation(value, 3);
}

function parseResearchReturnLocation(
  value: string | null | undefined,
  remainingDepth: number,
): WorkspaceLocation | null {
  if (
    !value ||
    value.length > maximumReturnPathLength ||
    !value.startsWith("/workspace/research?") ||
    /[\\#]/.test(value) ||
    Array.from(value).some((character) => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127)
  ) {
    return null;
  }
  const url = new URL(value, "https://pharma.local");
  if (url.origin !== "https://pharma.local" || url.pathname !== "/workspace/research") return null;
  const requestedView = url.searchParams.get("view") as ViewKey;
  if (
    url.searchParams.getAll("view").length !== 1 ||
    !views.has(requestedView) ||
    workbenchForView(requestedView) !== "research" ||
    url.searchParams.getAll("from").length > 1
  ) {
    return null;
  }
  const nestedPath = url.searchParams.get("from");
  // Strip before the ordinary parser so nested untrusted input cannot create unbounded recursion.
  url.searchParams.delete("from");
  const parsed = parseWorkbenchLocation("research", url.search);
  if (
    parsed.invalidEntityId ||
    parsed.invalidTrialId ||
    parsed.invalidPatentId ||
    parsed.invalidDealId ||
    parsed.invalidRegulatoryEventId ||
    parsed.invalidNewsEventId ||
    parsed.invalidCollectionId ||
    parsed.invalidChemistrySavedSearchId ||
    parsed.invalidKnowledgePageId ||
    (entityDossierViews.has(parsed.view) && !parsed.entityId) ||
    (parsed.view === "collections" && !parsed.collectionId)
  ) {
    return null;
  }
  const nested = remainingDepth > 1 ? parseResearchReturnLocation(nestedPath, remainingDepth - 1) : null;
  if (nested) parsed.returnTo = workspaceUrl(nested);
  return workspaceUrl(parsed).length <= maximumReturnPathLength ? parsed : null;
}

function boundedResearchReturnPath(value: string | null | undefined): string | undefined {
  const parsed = researchReturnLocation(value);
  return parsed ? workspaceUrl(parsed) : undefined;
}

export function parseWorkbenchLocation(workbench: WorkbenchKey, search = ""): WorkspaceLocation {
  return parseWorkspaceQuery(workbench, search, boundedResearchReturnPath);
}

export function workspaceUrl(location: Parameters<typeof serializeWorkspaceLocation>[0]): string {
  return serializeWorkspaceLocation(location, boundedResearchReturnPath);
}
