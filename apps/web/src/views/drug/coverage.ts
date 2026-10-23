import type { ResearchTabOption } from "../../components/ResearchTabList";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import { drugDossierCaption, drugDossierText as t } from "../../lib/i18n/drugDossier";
import type { DrugDossierSection } from "../../lib/workspaceRouting";
import { uniqueProgramEntities } from "./associations";
import type { DrugCoverageDomain } from "./types";

export const drugTabs: Array<ResearchTabOption<DrugDossierSection>> = [
  { key: "overview", label: "药物概览" },
  { key: "pipeline", label: "研发管线" },
  { key: "relationships", label: "关联信息" },
  { key: "activities", label: "活性" },
  { key: "trials", label: "临床结果与试验" },
  { key: "patents", label: "专利" },
  { key: "deals", label: "交易" },
  { key: "regulatory", label: "获批与监管" },
  { key: "news", label: "动态" },
  { key: "structures", label: "结构" },
];

export function dossierSectionAvailability(data: DrugDossier, domain: DrugCoverageDomain, observedCount: number) {
  const coverage = data.coverage.find((item) => item.domain === domain);
  const count = Math.max(observedCount, coverage?.total ?? 0);
  return {
    count,
    disabled: count === 0 && coverage?.status === "not_observed",
    disabledReason: count === 0 && coverage?.status === "not_observed" ? t("当前数据暂未收录相关信息") : undefined,
  };
}

export function drugAssociationCount(data: DrugDossier): number {
  const identities = new Set<string>();
  for (const kind of ["target", "disease", "organization"] as const) {
    for (const entity of uniqueProgramEntities(data, kind)) identities.add(`${entity.kind}:${entity.id}`);
  }
  for (const relationship of data.relationships) {
    identities.add(`${relationship.related_entity.entity_type}:${relationship.related_entity.id}`);
  }
  return identities.size;
}

export function publicDrugCoverage(data: DrugDossier): DrugDossier["coverage"] {
  const associationCount = drugAssociationCount(data);
  return data.coverage.map((item) =>
    item.domain === "relationships" && associationCount > item.total
      ? {
          ...item,
          total: associationCount,
          returned: Math.max(item.returned, associationCount),
          status: "available",
          note: t("包含研发项目中的靶点、适应症与研发机构"),
        }
      : item,
  );
}

export function buildDrugTabs(data: DrugDossier, programTotal: number): Array<ResearchTabOption<DrugDossierSection>> {
  const availability: Partial<Record<DrugDossierSection, ReturnType<typeof dossierSectionAvailability>>> = {
    pipeline: dossierSectionAvailability(data, "programs", programTotal),
    relationships: dossierSectionAvailability(data, "relationships", drugAssociationCount(data)),
    activities: dossierSectionAvailability(data, "activities", data.activities.length),
    trials: dossierSectionAvailability(data, "clinical_trials", data.clinical_trials.length),
    patents: dossierSectionAvailability(data, "patents", data.patents.length),
    deals: dossierSectionAvailability(data, "deals", data.deals.length),
    regulatory: dossierSectionAvailability(data, "regulatory_events", data.regulatory_events.length),
    news: dossierSectionAvailability(data, "news_events", data.news_events.length),
    structures: dossierSectionAvailability(data, "structures", data.structures.length),
  };
  return drugTabs.map((tab) => ({ ...tab, label: drugDossierCaption(tab.label), ...availability[tab.key] }));
}

export function coverageLabel(value: string): string {
  const labels: Record<string, string> = {
    relationships: t("关联信息"),
    evidence: t("资料来源"),
    activities: t("生物活性"),
    programs: t("研发项目"),
    clinical_trials: t("临床试验"),
    patents: t("专利信息"),
    deals: t("交易信息"),
    regulatory_events: t("监管信息"),
    news_events: t("新闻与会议"),
    structures: t("化学结构"),
    target_evidence: t("靶点证据"),
  };
  return labels[value] ?? value;
}
