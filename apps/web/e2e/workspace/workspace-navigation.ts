import { type PlaywrightTestArgs, type PlaywrightWorkerArgs, type TestInfo, test } from "@playwright/test";
import { verifyClinicalQueryAndResults } from "./navigation/clinical-query-and-results";
import { verifyCrossWorkbenchReturn } from "./navigation/cross-workbench-return";
import { verifyDealRegulatoryAndSavedSearch } from "./navigation/deal-regulatory-and-saved-search";
import { verifyDenseResultAndLandscape } from "./navigation/dense-result-and-landscape";
import { verifyExportsAndComparison } from "./navigation/exports-and-comparison";
import { verifyIdentityAndQuality } from "./navigation/identity-and-quality";
import { verifyIngestionAndQuarantine } from "./navigation/ingestion-and-quarantine";
import { verifyLoginAndAppearance } from "./navigation/login-and-appearance";
import { verifyNewsDealAndPatentDetails } from "./navigation/news-deal-and-patent-details";
import { verifyPipelineDossiers } from "./navigation/pipeline-dossiers";
import { verifyPipelineQuerySignals } from "./navigation/pipeline-query-signals";
import { verifyProfessionalQueryDomains } from "./navigation/professional-query-domains";
import { verifyPublication } from "./navigation/publication";
import { verifyQueryCancellationAndPagination } from "./navigation/query-cancellation-and-pagination";
import { verifyRegulatoryAndDomainContinuity } from "./navigation/regulatory-and-domain-continuity";
import { verifySetup } from "./navigation/setup";
import { verifyTablePreferencesAndQuickDetail } from "./navigation/table-preferences-and-quick-detail";

export async function verifyWorkspaceNavigation(
  { page, browser }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page" | "browser">,
  testInfo: TestInfo,
) {
  async function stage<Result>(name: string, action: () => Promise<Result>): Promise<Result> {
    return test.step(name, async () => {
      const started = performance.now();
      try {
        return await action();
      } finally {
        // Only fixed stage names and timings: never serialize fixture IDs, accounts or form contents.
        const durationMs = Math.round(performance.now() - started);
        console.info(JSON.stringify({ type: "workspace-stage", stage: name, duration_ms: durationMs }));
      }
    });
  }
  const context0 = await stage("setup", () => verifySetup({ page, browser }, testInfo));
  const context1 = await stage("login-and-appearance", () => verifyLoginAndAppearance(context0));
  const context2 = await stage("query-cancellation-and-pagination", () =>
    verifyQueryCancellationAndPagination(context1),
  );
  const context3 = await stage("dense-result-and-landscape", () => verifyDenseResultAndLandscape(context2));
  const context4 = await stage("table-preferences-and-quick-detail", () =>
    verifyTablePreferencesAndQuickDetail(context3),
  );
  const context5 = await stage("exports-and-comparison", () => verifyExportsAndComparison(context4));
  const context6 = await stage("clinical-query-and-results", () => verifyClinicalQueryAndResults(context5));
  const context7 = await stage("pipeline-query-signals", () => verifyPipelineQuerySignals(context6));
  const context8 = await stage("professional-query-domains", () => verifyProfessionalQueryDomains(context7));
  const context9 = await stage("news-deal-and-patent-details", () => verifyNewsDealAndPatentDetails(context8));
  const context10 = await stage("deal-regulatory-and-saved-search", () => verifyDealRegulatoryAndSavedSearch(context9));
  const context11 = await stage("pipeline-dossiers", () => verifyPipelineDossiers(context10));
  const context12 = await stage("regulatory-and-domain-continuity", () =>
    verifyRegulatoryAndDomainContinuity(context11),
  );
  const context13 = await stage("ingestion-and-quarantine", () => verifyIngestionAndQuarantine(context12));
  const context14 = await stage("publication", () => verifyPublication(context13));
  const context15 = await stage("identity-and-quality", () => verifyIdentityAndQuality(context14));
  const context16 = await stage("cross-workbench-return", () => verifyCrossWorkbenchReturn(context15));
  void context16;
}
