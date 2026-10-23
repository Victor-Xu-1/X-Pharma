import { entityLabels } from "../../lib/entityPresentation";
import { entityText as t } from "../../lib/i18n/entity";
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
  if (type === "disease") return t("疾病/登记条件");
  const labels = entityLabels();
  if (Object.hasOwn(labels, type)) return labels[type];
  if (type === "topic") return t("研究专题");
  if (type === "entity") return t("对象档案");
  return type;
}
