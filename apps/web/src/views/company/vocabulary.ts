import type { ResearchTabOption } from "../../components/ResearchTabList";
import type { CompanyDossierSection } from "../../lib/workspaceRouting";
export const tabs: Array<ResearchTabOption<CompanyDossierSection>> = [
  { key: "overview", label: "公司概览" },
  { key: "pipeline", label: "研发管线" },
  { key: "timeline", label: "公司时间线" },
  { key: "deals", label: "交易合作" },
  { key: "relationships", label: "关联网络" },
  { key: "trials", label: "临床试验" },
  { key: "patents", label: "专利" },
  { key: "regulatory", label: "监管" },
  { key: "news", label: "公司动态" },
];
