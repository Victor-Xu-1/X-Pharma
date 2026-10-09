import type { ResearchTabOption } from "../../components/ResearchTabList";
import { type dossierRecordMessages, dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import type { EntityDossierSection } from "../../lib/workspaceRouting";

export const domainLabels: Record<string, string> = {
  relationships: "实体关系",
  evidence: "来源证据",
  activities: "活性数据",
  programs: "研发管线",
  clinical_trials: "临床试验",
  patents: "专利",
  deals: "交易",
  regulatory_events: "监管事件",
  news_events: "新闻与会议",
  structures: "化学结构",
  target_evidence: "靶点证据",
};

export const tabs: Array<ResearchTabOption<EntityDossierSection>> = [
  { key: "overview", label: "概览" },
  { key: "company_intelligence", label: "公司情报" },
  { key: "relationships", label: "关系网络" },
  { key: "programs", label: "研发管线" },
  { key: "activities", label: "活性数据" },
  { key: "clinical_trials", label: "临床试验" },
  { key: "patents", label: "专利" },
  { key: "deals", label: "交易" },
  { key: "regulatory_events", label: "监管" },
  { key: "news_events", label: "动态" },
  { key: "structures", label: "结构" },
];

export const coverageSectionMap: Partial<Record<string, EntityDossierSection>> = {
  relationships: "relationships",
  activities: "activities",
  programs: "programs",
  clinical_trials: "clinical_trials",
  patents: "patents",
  deals: "deals",
  regulatory_events: "regulatory_events",
  news_events: "news_events",
  structures: "structures",
};

export function dossierDomainLabel(value: string): string {
  const caption = domainLabels[value];
  return caption ? t(caption as keyof typeof dossierRecordMessages) : value;
}
