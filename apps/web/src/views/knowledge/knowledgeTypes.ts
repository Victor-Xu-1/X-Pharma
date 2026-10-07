import { entityLabels } from "../../lib/entityPresentation";
import type { KnowledgePanel } from "../../lib/workspaceRouting";

export type KnowledgeLocation = {
  query: string;
  pageId: string | null;
  panel: KnowledgePanel;
  versionNumber: number | null;
  offset: number;
  pageType: string;
  sortBy: "title" | "updated_at";
  sortDirection: "asc" | "desc";
};

export function knowledgeTypeLabel(type: string): string {
  if (type === "disease") return "疾病/登记条件";
  if (Object.hasOwn(entityLabels, type)) return entityLabels[type];
  if (type === "topic") return "研究专题";
  if (type === "entity") return "对象档案";
  return type;
}
