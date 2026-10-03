import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";

export async function verifyRealTargetDossier(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(120_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const targetId = process.env.E2E_PIPELINE_TARGET_ID;
  test.skip(
    !credentials || !fixtureKeyBase || !targetId,
    "Authenticated browser fixture credentials and a target dossier ID are required",
  );
  if (!credentials || !fixtureKeyBase || !targetId) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const dossierResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === `/api/v1/targets/${targetId}/dossier` && response.request().method() === "GET";
  });
  await page.goto(`/workspace/research?view=target&entity=${targetId}&section=overview`);
  const dossierResponse = await dossierResponsePromise;
  expect(dossierResponse.status()).toBe(200);
  const dossier = (await dossierResponse.json()) as {
    entity?: { id?: string };
    programs?: unknown[];
    clinical_trials?: unknown[];
    patents?: unknown[];
    deals?: unknown[];
    regulatory_events?: unknown[];
    news_events?: unknown[];
    activities?: unknown[];
    structures?: unknown[];
  };
  expect(dossier.entity?.id).toBe(targetId);
  const dossierCollections = [
    "programs",
    "clinical_trials",
    "patents",
    "deals",
    "regulatory_events",
    "news_events",
    "activities",
    "structures",
  ] as const;
  for (const collection of dossierCollections) expect(Array.isArray(dossier[collection])).toBe(true);
  for (const collection of [
    "programs",
    "clinical_trials",
    "patents",
    "deals",
    "news_events",
    "activities",
    "structures",
  ] as const) {
    expect(dossier[collection]?.length, `${collection} must contain a governed dossier record`).toBeGreaterThan(0);
  }

  await expect(
    page.getByRole("heading", { name: `Browser pipeline target ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  const dossierSections: ReadonlyArray<readonly [string, string]> = [
    ["overview", "概览"],
    ["relationships", "关系网络"],
    ["evidence", "转化证据"],
    ["activities", "活性数据"],
    ["pipeline", "竞品管线"],
    ["trials", "临床试验"],
    ["patents", "专利"],
    ["deals", "交易"],
    ["regulatory", "监管动态"],
    ["news", "新闻与会议"],
    ["structures", "结构"],
  ];
  for (const [section, label] of dossierSections) {
    await page.goto(`/workspace/research?view=target&entity=${targetId}&section=${section}`);
    await expect(page.getByRole("tab", { name: label, exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel")).toBeVisible();
    await expect(page.locator("main")).not.toContainText("加载失败");
    if (section === "activities") {
      await expect(page.getByRole("table", { name: "靶点活性数据" })).toContainText("IC50");
    }
    if (section === "structures") {
      await expect(page.getByText("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", { exact: true })).toBeVisible();
    }
  }

  const sarResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === `/api/v1/targets/${targetId}/sar-comparison` && response.request().method() === "GET";
  });
  await page.goto(`/workspace/research?view=target&entity=${targetId}&section=sar`);
  const sarResponse = await sarResponsePromise;
  expect(sarResponse.status()).toBe(200);
  const sarPayload = (await sarResponse.json()) as { total?: number; items?: unknown[] };
  expect(sarPayload.total).toBeGreaterThan(0);
  expect(sarPayload.items?.length).toBeGreaterThan(0);
  await expect(page.getByRole("tab", { name: "SAR 对比", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("table", { name: "SAR 活性对比结果" })).toContainText("IC50");
  await expect(page.getByRole("tabpanel")).toBeVisible();
  testInfo.annotations.push({
    type: "real-target-dossier",
    description: JSON.stringify({
      dossier_api_status: dossierResponse.status(),
      sar_api_status: sarResponse.status(),
      populated_domains: ["programs", "clinical_trials", "patents", "deals", "news_events", "activities", "structures"],
      empty_allowed_domains: ["regulatory_events"],
    }),
  });
}
