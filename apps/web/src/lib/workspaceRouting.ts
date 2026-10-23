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
const maximumReturnFrames = 16;
const retainedReturnFrames = 3;

const entityDossierViews: ReadonlySet<ViewKey> = new Set(["drug", "target", "company", "disease", "entity"]);

/** Parse only bounded, same-workbench context; never follow a referrer or browser history blindly. */
export function researchReturnLocation(value: string | null | undefined): WorkspaceLocation | null {
  const frames: WorkspaceLocation[] = [];
  let cursor = value;
  while (cursor) {
    if (frames.length === maximumReturnFrames) return null;
    const frame = parseResearchReturnFrame(cursor);
    if (!frame) break;
    frames.push(frame.location);
    cursor = frame.nestedPath;
  }
  if (!frames.length) return null;
  // A return context is not an unbounded history log: keep the two most recent
  // destinations and the originating research, rather than discarding its query.
  const retained = frames.length > retainedReturnFrames ? [...frames.slice(0, 2), frames[frames.length - 1]] : frames;
  let nestedPath: string | undefined;
  for (const location of [...retained].reverse()) {
    if (nestedPath) location.returnTo = nestedPath;
    // Every frame has already passed the same typed/same-workbench validation.
    // Encode the constructed path directly; do not recursively parse it again.
    nestedPath = serializeWorkspaceLocation(location, () => location.returnTo);
    if (nestedPath.length > maximumReturnPathLength) return null;
  }
  return retained[0];
}

function parseResearchReturnFrame(value: string): { location: WorkspaceLocation; nestedPath: string | null } | null {
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
  return { location: parsed, nestedPath };
}

function boundedResearchReturnPath(value: string | null | undefined): string | undefined {
  const parsed = researchReturnLocation(value);
  return parsed ? serializeWorkspaceLocation(parsed, () => parsed.returnTo) : undefined;
}

export function parseWorkbenchLocation(workbench: WorkbenchKey, search = ""): WorkspaceLocation {
  return parseWorkspaceQuery(workbench, search, boundedResearchReturnPath);
}

export function workspaceUrl(location: Parameters<typeof serializeWorkspaceLocation>[0]): string {
  return serializeWorkspaceLocation(location, boundedResearchReturnPath);
}
