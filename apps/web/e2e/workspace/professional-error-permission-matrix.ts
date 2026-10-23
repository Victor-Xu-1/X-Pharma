import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, type Locator, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { selectInterfaceLanguage } from "../interface-language";
import { verifyProfessionalErrorPermissionLifecycle } from "./helpers";

export async function verifyProfessionalErrorPermissionMatrix(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(180_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const pipelineTargetId = process.env.E2E_PIPELINE_TARGET_ID;
  const regulatorySubjectId = process.env.E2E_REGULATORY_SUBJECT_ID;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  test.skip(
    !credentials || !fixtureKeyBase || !pipelineTargetId || !regulatorySubjectId || !epidemiologyDiseaseId,
    "Authenticated browser fixture credentials and governed professional entities are required",
  );
  if (!credentials || !fixtureKeyBase || !pipelineTargetId || !regulatorySubjectId || !epidemiologyDiseaseId) return;

  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const domains: Array<{ endpoint: string; resultSurface: () => Locator; url: string }> = [
    {
      endpoint: "/api/v1/entities",
      resultSurface: () => page.getByRole("table", { name: "实体检索结果" }),
      url: `/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`,
    },
    {
      endpoint: "/api/v1/pipelines",
      resultSurface: () => page.getByRole("table", { name: "药物与研发管线结果" }),
      url: `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}`,
    },
    {
      endpoint: "/api/v1/trials",
      resultSurface: () => page.getByRole("table", { name: "临床试验结果" }),
      url: `/workspace/research?view=trials&investigational_drug_entity_ids=${regulatorySubjectId}`,
    },
    {
      endpoint: "/api/v1/patent-families",
      resultSurface: () => page.getByRole("table", { name: "专利族结果" }),
      url: `/workspace/research?view=patents&q=${encodeURIComponent(fixtureKeyBase)}`,
    },
    {
      endpoint: "/api/v1/deal-transactions",
      resultSurface: () => page.getByRole("table", { name: "交易结果" }),
      url: `/workspace/research?view=deals&asset_entity_id=${regulatorySubjectId}`,
    },
    {
      endpoint: "/api/v1/regulatory-event-timeline",
      resultSurface: () => page.getByRole("table", { name: "监管事件结果" }),
      url: `/workspace/research?view=regulatory&entity_id=${regulatorySubjectId}`,
    },
    {
      endpoint: "/api/v1/epidemiology-observations",
      resultSurface: () => page.getByRole("table", { name: "流行病学结果" }),
      url: `/workspace/research?view=epidemiology&disease_entity_id=${epidemiologyDiseaseId}`,
    },
    {
      endpoint: "/api/v1/news-events",
      resultSurface: () => page.getByRole("region", { name: "研究发布时间线" }),
      url: `/workspace/research?view=news&entity_id=${pipelineTargetId}&display=timeline`,
    },
  ];

  for (const domain of domains) {
    await page.goto(domain.url);
    const resultSurface = domain.resultSurface();
    await expect(resultSurface).toContainText(fixtureKeyBase, { timeout: 15_000 });
    await verifyProfessionalErrorPermissionLifecycle({
      page,
      endpoint: domain.endpoint,
      resultSurface,
    });
  }
}
