import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { verifyDossierSourceReturn } from "./dossier-source-return";

export async function verifyEntityResearchContinuity(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  test.skip(!credentials || !fixtureKeyBase, "Authenticated browser fixture credentials are required");
  if (!credentials || !fixtureKeyBase) return;

  const fixtureKey = `${fixtureKeyBase}-continuity-${testInfo.project.name}`;
  const targetName = `Continuity target ${fixtureKey}`;
  const companyName = `Continuity company ${fixtureKey}`;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const csrfCookie = (await page.context().cookies()).find((cookie) => cookie.name === "pharma_csrf");
  if (!csrfCookie?.value) throw new Error("Authenticated session did not issue the CSRF cookie");
  const createEntity = async (entityType: "target" | "organization", name: string) => {
    const response = await page.request.post("/api/v1/entities", {
      headers: { "X-CSRF-Token": csrfCookie.value },
      data: {
        entity_type: entityType,
        name,
        description: "Controlled dossier continuity browser fixture",
        external_ids: { acceptance: `${fixtureKey}-${entityType}` },
        attributes: { acceptance_fixture: true, acceptance_fixture_key: fixtureKey },
      },
    });
    expect(response.status()).toBe(201);
    return (await response.json()) as { id: string };
  };
  const targetEntity = await createEntity("target", targetName);
  const companyEntity = await createEntity("organization", companyName);

  await page.goto(`/workspace/research?view=target&entity=${targetEntity.id}`);
  await expect(page.getByRole("heading", { name: targetName, exact: true })).toBeVisible();
  const targetOverviewTab = page.getByRole("tab", { name: "概览" });
  await targetOverviewTab.focus();
  await targetOverviewTab.press("ArrowRight");
  await expect(page).toHaveURL(/section=relationships/);
  await expect(page.getByRole("tab", { name: "关系网络" })).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(page.getByRole("tab", { name: "关系网络" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).not.toHaveURL(/section=/);
  await expect(page.getByRole("tab", { name: "概览" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${companyEntity.id}`);
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${companyEntity.id}`));
  await expect(page.getByRole("heading", { name: companyName, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "公司时间线" }).click();
  await expect(page).toHaveURL(/section=timeline/);
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("tab", { name: "公司时间线" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await page.goBack();
  await expect(page).not.toHaveURL(/section=/);
  await expect(page.getByRole("tab", { name: "公司概览" })).toHaveAttribute("aria-selected", "true");
  const projectKey = testInfo.project.name.toUpperCase().replaceAll("-", "_");
  const publishedTargetId = process.env[`E2E_SEARCH_TARGET_ID_${projectKey}`];
  const publishedDrugId = process.env.E2E_PIPELINE_DRUG_B_ID;
  if (!publishedTargetId || !publishedDrugId) throw new Error("Published source-return fixture IDs are required");
  const publishedResponse = await page.request.get(`/api/v1/entities/${publishedTargetId}`);
  expect(publishedResponse.ok()).toBe(true);
  const publishedTarget = (await publishedResponse.json()) as { id: string; name: string; review_status: string };
  expect(publishedTarget.review_status).toBe("verified");
  await verifyDossierSourceReturn(page, testInfo, {
    targetId: publishedTarget.id,
    targetName: publishedTarget.name,
    drugId: publishedDrugId,
    query: publishedTarget.name,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
}
