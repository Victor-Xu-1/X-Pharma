import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";

export async function verifyEvidenceResearchContinuity(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  test.skip(!credentials, "Authenticated browser fixture credentials are required");
  if (!credentials) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const catalogResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === "/api/v1/evidence/datasets";
  });
  const initialSearchPromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST" && url.pathname === "/api/v1/evidence/search";
  });
  await page.goto("/workspace/research?view=evidence&q=EGFR");
  const [catalogResponse, initialSearchResponse] = await Promise.all([catalogResponsePromise, initialSearchPromise]);
  expect(catalogResponse.ok()).toBe(true);
  expect(initialSearchResponse.ok()).toBe(true);
  const catalog = (await catalogResponse.json()) as Array<{ dataset_key: string; display_name: string }>;
  const initialResult = (await initialSearchResponse.json()) as {
    chunks: Array<{ dataset_id: string; document_id: string; document_name: string }>;
  };
  expect(initialResult.chunks.length).toBeGreaterThan(1);
  const firstInitialChunk = initialResult.chunks[0];
  expect(firstInitialChunk).toBeTruthy();
  if (!firstInitialChunk) return;
  const dataset = catalog.find((item) => item.dataset_key === firstInitialChunk.dataset_id);
  expect(dataset, "the result dataset must be present in the licensed web catalog").toBeTruthy();
  if (!dataset) return;

  const datasetButton = page.getByRole("button", { name: dataset.display_name, exact: true });
  await expect(datasetButton).toBeVisible();
  await datasetButton.click();
  const filteredSearchPromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST" && url.pathname === "/api/v1/evidence/search";
  });
  await page.getByRole("button", { name: "查证原文" }).click();
  const filteredSearchResponse = await filteredSearchPromise;
  expect(filteredSearchResponse.ok()).toBe(true);
  expect(filteredSearchResponse.request().postDataJSON()).toMatchObject({ dataset_keys: [dataset.dataset_key] });
  const filteredResult = (await filteredSearchResponse.json()) as {
    chunks: Array<{ document_id: string; document_name: string }>;
  };
  expect(filteredResult.chunks.length).toBeGreaterThan(1);

  await page.getByRole("button", { name: "定位引用 01" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("dataset")).toBe(dataset.dataset_key);
  await expect.poll(() => new URL(page.url()).searchParams.get("document")).toBe(filteredResult.chunks[0]?.document_id);
  await expect.poll(() => new URL(page.url()).searchParams.get("chunk")).toBe("1");
  await expect(page.getByLabel("当前引用定位")).toContainText(filteredResult.chunks[0]?.document_name ?? "");

  await page.reload();
  await expect(datasetButton).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("article.evidence-record[aria-current='true']")).toContainText(
    filteredResult.chunks[0]?.document_name ?? "",
  );

  await page.getByRole("button", { name: "定位引用 02" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("chunk")).toBe("2");
  await page.goBack();
  await expect.poll(() => new URL(page.url()).searchParams.get("chunk")).toBe("1");
  await expect(page.locator("article.evidence-record[aria-current='true']")).toContainText(
    filteredResult.chunks[0]?.document_name ?? "",
  );
}
