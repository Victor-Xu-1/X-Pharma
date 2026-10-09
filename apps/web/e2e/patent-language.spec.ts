import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { patentResult } from "../src/test/fixtures/patentsResearch";
import { selectInterfaceLanguage } from "./interface-language";

test("[patent-language] English-first filters keep drafts, selection and source publications across language changes", async ({
  page,
}, testInfo) => {
  let reads = 0;
  const writes: string[] = [],
    errors: string[] = [];
  const patent = {
    ...patentResult.items[0],
    id: "550e8400-e29b-41d4-a716-446655440021",
    title: "CONTROLLED FIXTURE · 原始专利标题",
  };
  page.on("pageerror", (error) => errors.push(error.message));
  // Isolated browser responses, never authoritative records or coverage evidence.
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-patent-user",
          tenant_id: "controlled-patent-tenant",
          email: "patent-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/patent-families") {
      reads++;
      return route.fulfill({ json: { ...patentResult, items: [patent], total: 1 } });
    }
    if (path === `/api/v1/patent-families/${patent.id}`) {
      reads++;
      return route.fulfill({ json: patent });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto("/workspace/research?view=patents&q=EGFR");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const results = page.getByRole("table", { name: "Patent family results", exact: true });
  await expect(results).toContainText(patent.title);
  await expect(results.getByText("Active", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: `Select Compare ${patent.family_identifier}`, exact: true }).check();
  await page.getByText("More patent conditions", { exact: true }).click();
  await page
    .getByRole("group", { name: "Priority dates", exact: true })
    .getByLabel("From", { exact: true })
    .fill("2021-02-03");
  await page.getByRole("textbox", { name: "Keyword", exact: true }).fill("未提交专利草稿");
  const originalUrl = page.url(),
    originalReads = reads;
  await selectInterfaceLanguage(page, "zh-CN");
  expect(page.url()).toBe(originalUrl);
  expect(reads).toBe(originalReads);
  await expect(page.getByRole("textbox", { name: "关键词", exact: true })).toHaveValue("未提交专利草稿");
  await expect(
    page.getByRole("checkbox", { name: `取消选择对比 ${patent.family_identifier}`, exact: true }),
  ).toBeChecked();
  await expect(page.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  await page.getByRole("button", { name: `打开专利族详情：${patent.family_identifier}`, exact: true }).click();
  await expect(page.getByRole("table", { name: "公开文本", exact: true })).toContainText("WO2022123456A1");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByRole("heading", { name: patent.title, exact: true })).toBeVisible();
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("table", { name: "Publications", exact: true })).toContainText("WO2022123456A1");
  await page.getByRole("button", { name: "Back to patent families", exact: true }).click();
  await page.goto("/workspace/research?view=patents&priority_from=2021-02-03&expiration_to=2042-02-03");
  await expect(page.locator(".secondary-filter-panel")).toHaveAttribute("open", "");
  await expect(page.getByRole("button", { name: "Clear", exact: true })).toBeEnabled();
  await expect(
    page.getByRole("group", { name: "Priority dates", exact: true }).getByLabel("From", { exact: true }),
  ).toHaveValue("2021-02-03");
  await expect(
    page.getByRole("group", { name: "Estimated expiration dates", exact: true }).getByLabel("To", { exact: true }),
  ).toHaveValue("2042-02-03");
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => document.documentElement.clientWidth),
  );
  await page.screenshot({ path: testInfo.outputPath("patent-source-preserving-en.png"), animations: "disabled" });
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
