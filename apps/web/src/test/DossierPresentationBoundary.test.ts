import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";

const consumers = [
  "CompanyView",
  "DiseaseView",
  "DrugView",
  "CompanySourceLabelOverview",
  "disease/RegistryConditionDossier",
  "drug/DrugRegulatory",
  "drug/DrugAssociations",
  "NewsView",
  "DealsView",
  "RegulatoryView",
  "PatentsView",
  "EpidemiologyView",
  "news/NewsTimeline",
  "news/useNewsColumns",
  "news/NewsDetailDrawer",
  "disease/DiseaseEvidence",
  "disease/EpidemiologyPanel",
  "disease/DiseaseOverview",
  "disease/EpidemiologyTable",
  "deals/DealProfessionalDossier",
  "deals/useDealColumns",
  "deals/DealPartiesAssets",
  "deals/DealRights",
  "drug/DrugDealAssets",
  "drug/DrugDealParties",
  "drug/DrugDealIntelligence",
  "epidemiology/useEpidemiologyColumns",
  "regulatory/RegulatoryDetailDrawer",
  "regulatory/useRegulatoryColumns",
  "patents/PatentProfessionalDossier",
  "patents/columns",
];
function source(path: string) {
  const baseline = process.env.X_PHARMA_DOSSIER_BOUNDARY_BASELINE;
  if (baseline) {
    if (process.env.CI || !/^[0-9a-f]{40}$/u.test(baseline))
      throw new Error("Baseline source is local-only and must be exact");
    return execFileSync("git", ["show", `${baseline}:apps/web/src/views/${path}.tsx`], { encoding: "utf8" });
  }
  return readFileSync(resolve("src/views", `${path}.tsx`), "utf8");
}

it.each(consumers)("keeps shared presentation in %s independent of the generic dossier query owner", (path) => {
  // Exact internal module edge, including type imports and multiline declarations.
  expect(source(path)).not.toMatch(/(?:from\s*|import\s*\()\s*["'][^"']*\/EntityDossierView["']/u);
});

it("does not use the generic data-reading page as a shared presentation/type export barrel", () => {
  expect(source("EntityDossierView")).not.toMatch(/^export\s+(?:type\s+)?\{/mu);
});
