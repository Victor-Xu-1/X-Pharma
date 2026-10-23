import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { selectInterfaceLanguage } from "../interface-language";

export async function verifyClinicalTrialSubscription(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  test.skip(!credentials || !fixtureKeyBase, "Authenticated browser fixture credentials are required");
  if (!credentials || !fixtureKeyBase) return;

  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const query = new URLSearchParams({
    view: "trials",
    q: fixtureKeyBase,
    registry: "ClinicalTrials.gov",
    status: "RECRUITING",
    phase: "PHASE2",
    study_type: "INTERVENTIONAL",
    has_results: "true",
    result_evaluation: "positive",
    results_posted_from: "2026-01-01",
    results_posted_to: "2026-07-31",
    investigational_drug: "VX-101",
    combination_drug: "Pembrolizumab",
    investigational_target: "EGFR",
    combination_target: "PD-1",
    has_key_result: "true",
    publication_id: "PMID:12345678",
    conference: "ASCO 2026",
    disclosed_from: "2026-06-01",
    disclosed_to: "2026-07-31",
    sort: "registry_id:asc",
  });
  await page.goto(`/workspace/research?${query}`);
  await expect(page.getByRole("button", { name: "保存/订阅" })).toBeEnabled();
  const subscriptionName = `Browser trial subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const saveForm = page.getByRole("dialog", { name: "保存当前临床试验检索" });
  await saveForm.getByLabel("名称").fill(subscriptionName);
  await saveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("临床试验检索已保存并启用监控")).toBeVisible();

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedRow = page.getByRole("row").filter({ hasText: subscriptionName });
  await expect(savedRow).toContainText("临床试验");
  await savedRow.getByRole("button", { name: `运行 ${subscriptionName}` }).click();
  for (const [name, value] of query.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  const filters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(filters.getByLabel("结果发布", { exact: true })).toHaveValue("true");
  await expect(filters.getByLabel("结果最优评价")).toHaveValue("positive");
  await expect(filters.getByLabel("会议")).toHaveValue("ASCO 2026");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
}
