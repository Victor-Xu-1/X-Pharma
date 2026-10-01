import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
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
  const context0 = await verifySetup({ page, browser }, testInfo);
  const context1 = await verifyLoginAndAppearance(context0);
  const context2 = await verifyQueryCancellationAndPagination(context1);
  const context3 = await verifyDenseResultAndLandscape(context2);
  const context4 = await verifyTablePreferencesAndQuickDetail(context3);
  const context5 = await verifyExportsAndComparison(context4);
  const context6 = await verifyClinicalQueryAndResults(context5);
  const context7 = await verifyPipelineQuerySignals(context6);
  const context8 = await verifyProfessionalQueryDomains(context7);
  const context9 = await verifyNewsDealAndPatentDetails(context8);
  const context10 = await verifyDealRegulatoryAndSavedSearch(context9);
  const context11 = await verifyPipelineDossiers(context10);
  const context12 = await verifyRegulatoryAndDomainContinuity(context11);
  const context13 = await verifyIngestionAndQuarantine(context12);
  const context14 = await verifyPublication(context13);
  const context15 = await verifyIdentityAndQuality(context14);
  const context16 = await verifyCrossWorkbenchReturn(context15);
  void context16;
}
