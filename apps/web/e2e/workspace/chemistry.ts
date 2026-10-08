import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { selectInterfaceLanguage } from "../interface-language";
import { navigateResearchView } from "./helpers";

export async function verifyChemistry(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKey = process.env.E2E_FIXTURE_KEY;
  const expectedEntityId = process.env.E2E_REGULATORY_SUBJECT_ID;
  test.skip(
    !credentials || !fixtureKey || !expectedEntityId,
    "Real chemistry fixture and browser credentials are required",
  );
  if (!credentials || !fixtureKey || !expectedEntityId) return;
  const aspirinSmiles = "CC(=O)Oc1ccccc1C(=O)O";
  const expectedEntityName = `Browser regulatory drug ${fixtureKey}`;

  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await navigateResearchView(page, "chemistry");
  const deferredResourcePattern = /(?:\.wasm$|rdkit|indigo|ketcher|structureeditor)/i;
  const chemistryResourcesBeforeEditor = await page.evaluate(() =>
    (performance.getEntriesByType("resource") as PerformanceResourceTiming[]).map(
      (entry) => new URL(entry.name).pathname,
    ),
  );
  expect(chemistryResourcesBeforeEditor.filter((path) => deferredResourcePattern.test(path))).toEqual([]);
  await page.getByRole("button", { name: "打开结构画板" }).click();
  await expect(page.getByRole("region", { name: "结构式编辑器" })).toBeVisible();
  await expect
    .poll(async () =>
      page.evaluate(() =>
        (performance.getEntriesByType("resource") as PerformanceResourceTiming[]).some((entry) =>
          /structureeditor/i.test(new URL(entry.name).pathname),
        ),
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "苯环（T）" }).click();
  const structureCanvas = page.getByRole("application").getByTestId("canvas");
  const structureCanvasBox = await structureCanvas.boundingBox();
  expect(structureCanvasBox).not.toBeNull();
  const position = {
    x: Math.round((structureCanvasBox?.width ?? 0) / 2),
    y: Math.round((structureCanvasBox?.height ?? 0) / 2),
  };
  await structureCanvas.hover({ position });
  await expect(structureCanvas.getByTestId("bond")).toHaveCount(6);
  if (testInfo.project.use.hasTouch) await structureCanvas.tap({ position });
  else await structureCanvas.click({ position });
  await page.getByRole("button", { name: "应用到检索" }).click();
  await expect(page.getByRole("status").filter({ hasText: "结构已用于本次检索" })).toHaveText("结构已用于本次检索");
  await page.getByRole("tab", { name: "高级输入" }).click();
  await expect(page.getByLabel("SMILES")).not.toHaveValue("");
  await page.getByLabel("SMILES").fill(aspirinSmiles);
  const chemistryResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/chemistry/search",
  );
  await page.getByRole("button", { name: "检索", exact: true }).click();
  const chemistryResponse = await chemistryResponsePromise;
  expect(chemistryResponse.status()).toBe(200);
  const chemistryPayload = (await chemistryResponse.json()) as {
    mode: string;
    normalized_query: string;
    count: number;
    items: Array<{ entity_id: string; entity_name: string; standard_inchi_key: string }>;
  };
  expect(chemistryPayload.mode).toBe("exact");
  expect(chemistryPayload.normalized_query).toBe(aspirinSmiles);
  expect(chemistryPayload.count).toBe(1);
  expect(chemistryPayload.items).toEqual([
    expect.objectContaining({
      entity_id: expectedEntityId,
      entity_name: expectedEntityName,
      standard_inchi_key: "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
    }),
  ]);

  await expect(page.getByRole("heading", { name: expectedEntityName })).toBeVisible();
  const depiction = page.locator(".molecule-depiction");
  await expect(depiction).toHaveCount(1);
  await expect(depiction).toHaveAttribute("data-rdkit-version", /\S+/);
  const image = depiction.locator("img");
  await expect(image).toBeVisible();
  expect(
    await image.evaluate((element) => {
      if (!(element instanceof HTMLImageElement)) throw new Error("Expected a real RDKit image");
      return { width: element.naturalWidth, height: element.naturalHeight };
    }),
  ).toEqual({
    width: 360,
    height: 180,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.getByRole("button", { name: "保存结构检索", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "保存当前结构检索" })).toBeVisible();
  const savedSearchName = `Aspirin structure ${fixtureKey}`;
  await page.getByRole("dialog").getByLabel("名称").fill(savedSearchName);
  const savedSearchResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/monitoring/saved-searches",
  );
  await page.getByRole("dialog").getByRole("button", { name: "确认保存" }).click();
  const savedSearchResponse = await savedSearchResponsePromise;
  expect(savedSearchResponse.status()).toBe(201);
  const savedSearchPayload = (await savedSearchResponse.json()) as {
    id: string;
    query_type: string;
    query_json: { mode: string; query: string };
  };
  expect(savedSearchPayload.query_type).toBe("chemistry_search");
  expect(savedSearchPayload.query_json.query).toBe(aspirinSmiles);
  await expect(page).toHaveURL(new RegExp(`/workspace/research\\?view=chemistry&saved=${savedSearchPayload.id}`));
  expect(new URL(page.url()).search).not.toContain("CC(=O)");

  const restoredChemistryResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/chemistry/search",
  );
  await page.reload();
  const restoredChemistryResponse = await restoredChemistryResponsePromise;
  expect(restoredChemistryResponse.status()).toBe(200);
  await expect(page.getByRole("heading", { name: expectedEntityName })).toBeVisible();

  await page.getByRole("button", { name: "查看实体", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/workspace/research\\?view=(?:entity|drug)&entity=${expectedEntityId}`));
  await expect(page.getByRole("heading", { name: expectedEntityName })).toBeVisible();
}
