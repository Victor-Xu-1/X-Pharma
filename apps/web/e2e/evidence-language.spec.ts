import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { selectInterfaceLanguage } from "./interface-language";

test("[evidence-language] English-first controls retain drafts, source literals and selected citations", async ({
  page,
}, testInfo) => {
  const dataset = {
    dataset_key: "controlled-source",
    display_name: "CONTROLLED FIXTURE · 原始证据域",
    attribution: "原始来源声明",
  };
  const content = "CONTROLLED FIXTURE · 原始引文 EGFR 1.2 µM / pH 7.4 ".repeat(30);
  const original = {
    content,
    document_name: "CONTROLLED FIXTURE · 原始文档",
    document_id: "controlled-document",
    dataset_id: dataset.dataset_key,
    positions: [{ locator_kind: "page", locator_value: "7", start_char: 0, end_char: 120 }],
    metadata: { source: "https://example.test/original" },
    similarity: 0.91,
  };
  const searches: unknown[] = [],
    errors: string[] = [],
    unexpectedWrites: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals") return route.fulfill({ status: 202, json: {} });
    if (path === "/api/v1/evidence/search" && request.method() === "POST") {
      searches.push(request.postDataJSON());
      return route.fulfill({
        json: {
          query: "EGFR",
          chunks: [original],
          license_scopes: [],
          warnings: [],
          engine: "controlled-browser-response",
        },
      });
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      unexpectedWrites.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-evidence-user",
          tenant_id: "controlled-evidence-tenant",
          email: "evidence@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === "/api/v1/evidence/datasets") return route.fulfill({ json: [dataset] });
    return route.fulfill({ json: {} });
  });
  await page.goto("/workspace/research?view=evidence");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const query = page.getByRole("textbox", { name: "Research question or evidence query", exact: true });
  await expect(page.getByText("Awaiting evidence search", { exact: true })).toBeVisible();
  await query.fill("未提交 EGFR 查询");
  await page.getByRole("button", { name: dataset.display_name, exact: true }).click();
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("textbox", { name: "研究问题或查证内容", exact: true })).toHaveValue("未提交 EGFR 查询");
  await expect(page.getByRole("button", { name: dataset.display_name, exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(searches).toEqual([]);
  await selectInterfaceLanguage(page, "en");
  await query.fill("EGFR");
  await page.getByRole("button", { name: "Search source evidence", exact: true }).click();
  await expect(page.getByRole("heading", { name: original.document_name, exact: true })).toBeVisible();
  expect(searches).toEqual([{ query: "EGFR", dataset_keys: [dataset.dataset_key], limit: 20 }]);
  await page.getByRole("button", { name: "Locate citation 01", exact: true }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("document")).toBe(original.document_id);
  const selectedUrl = page.url(),
    beforeLanguageReads = searches.length;
  await expect(page.getByLabel("Current citation location", { exact: true })).toContainText(
    "Page 7 · Characters 0-120",
  );
  await page.getByRole("button", { name: "Expand full citation", exact: true }).click();
  await expect(page.locator("article[aria-current='true'] blockquote > span")).toHaveText(content);
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByLabel("当前引用定位", { exact: true })).toContainText("页 7 · 字符 0-120");
  await expect(page.getByRole("button", { name: "收起完整引用", exact: true })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await expect(page.locator("article[aria-current='true'] blockquote > span")).toHaveText(content);
  expect(searches.length).toBe(beforeLanguageReads);
  expect(page.url()).toBe(selectedUrl);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(page.getByLabel("当前引用定位", { exact: true })).toContainText(original.document_name);
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("link", { name: "Open original source", exact: true })).toHaveAttribute(
    "href",
    "https://example.test/original",
  );
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
  ).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    await page.evaluate(() => innerWidth),
  );
  await page.screenshot({ path: testInfo.outputPath("controlled-evidence-en.png"), animations: "disabled" });
  await selectInterfaceLanguage(page, "zh-CN");
  await page.screenshot({ path: testInfo.outputPath("controlled-evidence-zh.png"), animations: "disabled" });
  expect(unexpectedWrites).toEqual([]);
  expect(errors).toEqual([]);
});
