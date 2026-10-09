import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { collectionLanguageFixture } from "./fixtures/collection-language";
import { selectInterfaceLanguage } from "./interface-language";

test("[collection-language] keeps comparison, export and pending editor state across cross-tab language changes", async ({
  page,
  context,
}, testInfo) => {
  const fixture = collectionLanguageFixture();
  const writes: string[] = [],
    errors: string[] = [];
  let reads = 0,
    simulatedUpdates = 0,
    finishUpdate: (() => void) | undefined,
    detailVersion = 2;
  page.on("pageerror", (error) => errors.push(error.message));
  // This entire scenario uses browser-only responses. The one controlled PATCH
  // simulates a conflict and never reaches an account, provider or business server.
  await context.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals" && request.method() === "POST")
      return route.fulfill({ status: 202, json: {} });
    if (request.method() === "PATCH" && path === `/api/v1/comparison-sets/${fixture.detail.id}`) {
      simulatedUpdates++;
      await new Promise<void>((resolve) => {
        finishUpdate = resolve;
      });
      detailVersion = 3;
      return route.fulfill({ status: 409, json: { detail: "Controlled conflict / 原始诊断" } });
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: fixture.detail.owner_user_id,
          tenant_id: "controlled-list-tenant",
          role: "analyst",
          email: "collection-language@example.test",
          display_name: "Controlled browser fixture",
        },
      });
    if (request.frame().page() === page) reads++;
    if (path.endsWith("/comparison-sets/catalog"))
      return route.fulfill({
        json: {
          items: [fixture.detail],
          total: 1,
          limit: 25,
          offset: 0,
        },
      });
    if (path.endsWith(`/comparison-sets/${fixture.detail.id}`))
      return route.fulfill({ json: { ...fixture.detail, version: detailVersion } });
    if (path.endsWith("/versions")) return route.fulfill({ json: fixture.history });
    if (path === "/api/v1/workspace/export-policy") return route.fulfill({ json: fixture.policy });
    if (path === "/api/v1/drugs/comparison") return route.fulfill({ json: fixture.drugComparison });
    const dossierId = /^\/api\/v1\/entities\/([^/]+)\/dossier$/.exec(path)?.[1];
    if (dossierId) return route.fulfill({ json: fixture.dossier(dossierId) });
    return route.fulfill({ json: [] });
  });
  async function audit(name: string) {
    expect(
      (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
    ).toEqual([]);
    const bounds = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: false, animations: "disabled" });
  }
  const url = `/workspace/research?view=collections&collection=${fixture.detail.id}&compare=${fixture.target.id},${fixture.company.id}`;
  await page.goto(url);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const matrix = page.getByRole("table", { name: "R&D intelligence comparison", exact: true });
  await expect(matrix).toBeVisible();
  await expect(matrix.getByRole("row", { name: /Development programs/ })).toContainText("1,200");
  await expect(matrix).toContainText("Registry sponsor");
  await expect(matrix).toContainText(fixture.company.name);
  const memberLayout = await page.locator(".collection-entity-link").evaluateAll((nodes) =>
    nodes.map((node) => {
      const name = node.querySelector("strong")?.getBoundingClientRect();
      const description = node.querySelector("small")?.getBoundingClientRect();
      return { nameBottom: name?.bottom, descriptionTop: description?.top };
    }),
  );
  for (const member of memberLayout) {
    expect(member.nameBottom).toBeDefined();
    expect(member.descriptionTop).toBeDefined();
    expect(member.descriptionTop).toBeGreaterThanOrEqual(member.nameBottom ?? 0);
  }
  await audit("collection-comparison-en");
  if ((page.viewportSize()?.width ?? 1440) < 900)
    await page.getByRole("button", { name: "Expand List directory", exact: true }).click();
  await expect(page.locator(".collection-picker").getByText("Private", { exact: true })).toBeVisible();
  const badgeLayout = await page.locator(".collection-picker .badge").evaluate((node) => ({
    right: node.getBoundingClientRect().right,
    ownerRight: node.closest("button")?.getBoundingClientRect().right,
  }));
  expect(badgeLayout.ownerRight).toBeDefined();
  expect(badgeLayout.right).toBeLessThanOrEqual(badgeLayout.ownerRight ?? 0);
  await page.getByRole("textbox", { name: "List name", exact: true }).fill("未提交新列表");
  const languagePage = await context.newPage();
  await languagePage.goto(url);
  await languagePage.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Edit list", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Edit comparison list", exact: true });
  await dialog.getByRole("textbox", { name: "Name", exact: true }).fill("编辑中的原始名称");
  const before = reads,
    selectedUrl = page.url();
  await selectInterfaceLanguage(languagePage, "zh-CN");
  await expect(
    page.getByRole("dialog", { name: "编辑对比列表", exact: true }).getByRole("textbox", { name: "名称", exact: true }),
  ).toHaveValue("编辑中的原始名称");
  expect(reads).toBe(before);
  expect(page.url()).toBe(selectedUrl);
  await page
    .getByRole("dialog", { name: "编辑对比列表", exact: true })
    .getByRole("button", { name: "保存修改", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveAttribute("aria-busy", "true");
  await selectInterfaceLanguage(languagePage, "en");
  await expect(dialog.getByRole("textbox", { name: "Name", exact: true })).toBeDisabled();
  await expect(dialog.getByRole("button", { name: "Saving", exact: true })).toBeDisabled();
  await audit("collection-pending-en");
  expect(finishUpdate).toBeDefined();
  finishUpdate?.();
  await expect(dialog.getByRole("alert")).toContainText("Nothing was overwritten automatically");
  await expect(dialog.getByRole("textbox", { name: "Name", exact: true })).toHaveValue("编辑中的原始名称");
  await expect(dialog.getByRole("textbox", { name: "Name", exact: true })).toBeEnabled();
  await audit("collection-conflict-en");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await languagePage.close();
  await expect(page.getByRole("textbox", { name: "List name", exact: true })).toHaveValue("未提交新列表");
  if ((page.viewportSize()?.width ?? 1440) < 900)
    await page.getByRole("button", { name: "Collapse List directory", exact: true }).click();
  await page.locator(".collection-export-menu > summary").click();
  const exportForm = page.getByRole("form", { name: "List export", exact: true });
  await expect(exportForm.getByRole("button", { name: "Export", exact: true })).toBeEnabled();
  await exportForm.getByRole("combobox", { name: "Export format", exact: true }).selectOption("xlsx");
  await exportForm.getByRole("checkbox", { name: "Description", exact: true }).check();
  const exportReads = reads;
  await selectInterfaceLanguage(page, "zh-CN");
  const chineseExport = page.getByRole("form", { name: "列表导出", exact: true });
  await expect(chineseExport.getByRole("combobox", { name: "导出格式", exact: true })).toHaveValue("xlsx");
  await expect(chineseExport.getByRole("checkbox", { name: "描述", exact: true })).toBeChecked();
  await expect(chineseExport).toContainText(fixture.policy.attribution);
  expect(reads).toBe(exportReads);
  await audit("collection-export-zh");
  await page.locator(".collection-export-menu > summary").click();
  await selectInterfaceLanguage(page, "en");
  await page.getByText("List change history", { exact: true }).click();
  await expect(page.getByRole("table", { name: "List change history", exact: true })).toContainText("FUTURE_SCOPE");
  await page.getByRole("button", { name: "Clear comparison", exact: true }).click();
  for (const drug of fixture.drugs)
    await page.getByRole("checkbox", { name: `Include in intelligence comparison: ${drug.name}`, exact: true }).check();
  await expect(matrix).toContainText("Small molecule");
  await expect(matrix).toContainText("FUTURE_MODALITY");
  await expect(matrix.getByRole("row", { name: /Highest China phase/ })).toContainText("Phase I");
  await expect(matrix).toContainText("FUTURE_STATUS (0)");
  await audit("collection-drug-en");
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("table", { name: "研发情报对比表", exact: true })).toContainText("小分子");
  await audit("collection-drug-zh");
  expect(simulatedUpdates).toBe(1);
  expect(writes).toEqual([]);
});
