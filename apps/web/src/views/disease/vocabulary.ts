import type { ResearchTabOption } from "../../components/ResearchTabList";
import type { DiseaseDossierSection } from "../../lib/workspaceRouting";

export const tabs: Array<ResearchTabOption<DiseaseDossierSection>> = [
  { key: "overview", label: "疾病概览" },
  { key: "epidemiology", label: "流行病学" },
  { key: "pipeline", label: "研发格局" },
  { key: "evidence", label: "靶点证据" },
  { key: "trials", label: "临床试验" },
  { key: "patents", label: "专利" },
  { key: "deals", label: "交易合作" },
  { key: "regulatory", label: "监管" },
  { key: "news", label: "疾病动态" },
  { key: "relationships", label: "关联网络" },
];
