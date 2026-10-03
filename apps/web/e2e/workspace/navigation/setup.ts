import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../../src/lib/browserAcceptanceCredentials";
import type { WebVitalBatchCreate } from "../../../src/lib/generated";

export async function verifySetup(
  { browser, page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "browser" | "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(240_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const pipelineTargetId = process.env.E2E_PIPELINE_TARGET_ID;
  const pipelineCombinationTargetId = process.env.E2E_PIPELINE_COMBINATION_TARGET_ID;
  const pipelineDiseaseId = process.env.E2E_PIPELINE_DISEASE_ID;
  const trialProfileId = process.env.E2E_TRIAL_PROFILE_ID;
  const pipelineOrganizationId = process.env.E2E_PIPELINE_ORGANIZATION_ID;
  const pipelineCollaboratorId = process.env.E2E_PIPELINE_COLLABORATOR_ID;
  const regulatorySubjectId = process.env.E2E_REGULATORY_SUBJECT_ID;
  const regulatoryIndicationId = process.env.E2E_REGULATORY_INDICATION_ID;
  const regulatoryEventId = process.env.E2E_REGULATORY_EVENT_ID;
  const regulatoryNegativeEventId = process.env.E2E_REGULATORY_NEGATIVE_EVENT_ID;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  const epidemiologyPatientPopulationId = process.env.E2E_EPIDEMIOLOGY_PATIENT_POPULATION_ID;
  const epidemiologyObservationId = process.env.E2E_EPIDEMIOLOGY_OBSERVATION_ID;
  const patentFamilyId = process.env.E2E_PATENT_FAMILY_ID;
  const newsEventId = process.env.E2E_NEWS_EVENT_ID;
  const dealEntityId = process.env.E2E_DEAL_ENTITY_ID;
  const dealProfileId = process.env.E2E_DEAL_PROFILE_ID;
  const ingestionRunId =
    process.env[`E2E_INGESTION_RUN_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const quarantineVersionId =
    process.env[`E2E_QUARANTINE_VERSION_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const resolutionCaseId =
    process.env[`E2E_RESOLUTION_CASE_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const qualityIssueId =
    process.env[`E2E_QUALITY_ISSUE_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const qualityOwnerId =
    process.env[`E2E_QUALITY_OWNER_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  test.skip(
    !credentials ||
      !fixtureKeyBase ||
      !pipelineTargetId ||
      !pipelineCombinationTargetId ||
      !pipelineDiseaseId ||
      !trialProfileId ||
      !pipelineOrganizationId ||
      !pipelineCollaboratorId ||
      !regulatorySubjectId ||
      !regulatoryIndicationId ||
      !regulatoryEventId ||
      !regulatoryNegativeEventId ||
      !epidemiologyDiseaseId ||
      !epidemiologyPatientPopulationId ||
      !epidemiologyObservationId ||
      !patentFamilyId ||
      !newsEventId ||
      !dealEntityId ||
      !dealProfileId ||
      !ingestionRunId ||
      !quarantineVersionId ||
      !resolutionCaseId ||
      !qualityIssueId ||
      !qualityOwnerId,
    "Authenticated browser fixture credentials and cross-domain entity IDs are required",
  );
  if (
    !credentials ||
    !fixtureKeyBase ||
    !pipelineTargetId ||
    !pipelineCombinationTargetId ||
    !pipelineDiseaseId ||
    !trialProfileId ||
    !pipelineOrganizationId ||
    !pipelineCollaboratorId ||
    !regulatorySubjectId ||
    !regulatoryIndicationId ||
    !regulatoryEventId ||
    !regulatoryNegativeEventId ||
    !epidemiologyDiseaseId ||
    !epidemiologyPatientPopulationId ||
    !epidemiologyObservationId ||
    !patentFamilyId ||
    !newsEventId ||
    !dealEntityId ||
    !dealProfileId ||
    !ingestionRunId ||
    !quarantineVersionId ||
    !resolutionCaseId ||
    !qualityIssueId ||
    !qualityOwnerId
  ) {
    throw new Error("Required browser acceptance fixtures are unavailable");
  }
  const fixtureKey = `${fixtureKeyBase}-${testInfo.project.name}`;
  const projectSuffix = testInfo.project.name.replaceAll("-", "_").toUpperCase();
  const searchTargetId = process.env[`E2E_SEARCH_TARGET_ID_${projectSuffix}`];
  const searchCompanyId = process.env[`E2E_SEARCH_COMPANY_ID_${projectSuffix}`];
  if (!searchTargetId || !searchCompanyId) throw new Error("Curated public research fixture IDs are required");
  const fixtureName = `Browser acceptance target ${fixtureKey}`;
  const rumBatches: WebVitalBatchCreate[] = [];
  const rumStatuses: number[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname !== "/api/v1/workspace/web-vitals" || request.method() !== "POST") return;
    const body = request.postData();
    if (!body) throw new Error("Web Vitals RUM request did not contain a body");
    rumBatches.push(JSON.parse(body) as WebVitalBatchCreate);
  });
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/v1/workspace/web-vitals") {
      rumStatuses.push(response.status());
    }
  });
  return {
    page,
    browser,
    testInfo,
    credentials,
    fixtureKeyBase,
    pipelineTargetId,
    pipelineCombinationTargetId,
    pipelineDiseaseId,
    trialProfileId,
    pipelineOrganizationId,
    pipelineCollaboratorId,
    regulatorySubjectId,
    regulatoryIndicationId,
    regulatoryEventId,
    regulatoryNegativeEventId,
    epidemiologyDiseaseId,
    epidemiologyPatientPopulationId,
    epidemiologyObservationId,
    patentFamilyId,
    newsEventId,
    dealEntityId,
    dealProfileId,
    ingestionRunId,
    quarantineVersionId,
    resolutionCaseId,
    qualityIssueId,
    qualityOwnerId,
    fixtureKey,
    projectSuffix,
    searchTargetId,
    searchCompanyId,
    fixtureName,
    rumBatches,
    rumStatuses,
  };
}
