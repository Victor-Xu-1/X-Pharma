import type { MessageKey } from "../i18n/catalog";
import type { ViewKey } from "./types";

type ResearchDestination = { view: ViewKey; label: MessageKey };
export type ResearchWorkflow = { label: MessageKey; destinations: readonly ResearchDestination[] };

/** Presentation hierarchy only: existing URLs, queries and domain services remain authoritative. */
export const researchWorkflows: readonly ResearchWorkflow[] = [
  {
    label: "情报检索",
    destinations: [
      { view: "explorer", label: "实体检索" },
      { view: "chemistry", label: "结构检索" },
      { view: "evidence", label: "证据查证" },
    ],
  },
  {
    label: "研发数据",
    destinations: [
      { view: "pipeline", label: "药物与管线" },
      { view: "trials", label: "临床试验" },
      { view: "regulatory", label: "监管与安全" },
      { view: "epidemiology", label: "流行病学" },
    ],
  },
  {
    label: "竞争情报",
    destinations: [
      { view: "patents", label: "专利情报" },
      { view: "deals", label: "交易与公司" },
    ],
  },
  { label: "研究动态", destinations: [{ view: "news", label: "新闻与会议" }] },
  {
    label: "我的研究",
    destinations: [
      { view: "collections", label: "对比列表" },
      { view: "monitoring", label: "监控与提醒" },
      { view: "knowledge", label: "知识专题" },
    ],
  },
];

const dossierDestinations: Partial<Record<ViewKey, ViewKey>> = {
  target: "pipeline",
  drug: "pipeline",
  company: "deals",
  disease: "epidemiology",
  entity: "explorer",
};

export function researchWorkflowForView(view: ViewKey, sourceView?: ViewKey | null): ResearchWorkflow | undefined {
  const find = (destination: ViewKey) =>
    researchWorkflows.find((workflow) => workflow.destinations.some((item) => item.view === destination));
  const direct = find(view);
  if (direct) return direct;
  const dossierDestination = dossierDestinations[view];
  if (!dossierDestination) return undefined;
  const source = sourceView ? find(dossierDestinations[sourceView] ?? sourceView) : undefined;
  return source ?? find(dossierDestination);
}
