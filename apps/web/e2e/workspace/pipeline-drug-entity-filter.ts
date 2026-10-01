import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";

export async function verifyPipelineDrugEntityFilter(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const pipelineDrugId = process.env.E2E_PIPELINE_DRUG_B_ID;
  test.skip(
    !credentials || !fixtureKeyBase || !pipelineDrugId,
    "Authenticated browser fixture credentials and a governed pipeline drug are required",
  );
  if (!credentials || !fixtureKeyBase || !pipelineDrugId) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  await page.goto("/workspace/research?view=pipeline");
  const filters = page.getByRole("form", { name: "药物与管线筛选" });
  const entityComboboxes = filters.getByRole("combobox");
  const controlledListboxes = await entityComboboxes.evaluateAll((inputs) =>
    inputs.map((input) => input.getAttribute("aria-controls")),
  );
  expect(controlledListboxes.every(Boolean)).toBe(true);
  expect(new Set(controlledListboxes).size).toBe(controlledListboxes.length);

  const drugName = `Browser pipeline antibody ${fixtureKeyBase}`;
  const drugCombobox = filters.getByRole("combobox", { name: "药品筛选" });
  await drugCombobox.fill(drugName);
  const candidateOptions = page.getByRole("listbox").getByRole("option");
  await expect(candidateOptions.filter({ hasText: drugName })).toHaveCount(1);
  const optionLabels = await candidateOptions.allTextContents();
  const candidateIndex = optionLabels.findIndex((label) => label.includes(drugName));
  expect(candidateIndex).toBeGreaterThanOrEqual(0);
  for (let index = 0; index <= candidateIndex; index += 1) {
    await drugCombobox.press("ArrowDown");
  }
  const selectedOption = candidateOptions.nth(candidateIndex);
  const selectedOptionId = await selectedOption.getAttribute("id");
  expect(selectedOptionId).toBeTruthy();
  await expect(selectedOption).toHaveAttribute("aria-selected", "true");
  await expect(drugCombobox).toHaveAttribute("aria-activedescendant", selectedOptionId ?? "");
  await drugCombobox.press("Enter");
  await expect(filters.getByRole("group", { name: "药品检索与选择" })).toContainText(drugName);

  const exactDrugResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/v1/pipelines" && url.searchParams.get("drug_entity_id") === pipelineDrugId;
  });
  await filters.getByRole("button", { name: "查询", exact: true }).click();
  const payload = (await (await exactDrugResponse).json()) as {
    total: number;
    items: Array<{ drug_entity_id: string }>;
  };
  expect(payload.total).toBe(1);
  expect(payload.items.map((item) => item.drug_entity_id)).toEqual([pipelineDrugId]);

  await expect(page).toHaveURL(new RegExp(`drug_entity_id=${pipelineDrugId}`));
  await expect(filters.getByRole("group", { name: "药品检索与选择" })).toContainText(drugName);
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("药品");
  await expect(page.getByRole("table", { name: "药物与研发管线结果" })).toContainText(drugName);
  await page.reload();
  await expect(filters.getByRole("group", { name: "药品检索与选择" })).toContainText(drugName);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
}
