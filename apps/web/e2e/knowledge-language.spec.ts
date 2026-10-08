import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { knowledgeLanguageFixture } from "./fixtures/knowledge-language";
import { selectInterfaceLanguage } from "./interface-language";

test("[knowledge-language] retains drafts, original values, version selection and retry across language switching", async ({
  page,
}, testInfo) => {
  const fixture = knowledgeLanguageFixture();
  const reads: string[] = [],
    writes: string[] = [],
    errors: string[] = [];
  let failCoverage = true;
  page.on("pageerror", (error) => errors.push(error.message));
  // Every API response is browser-only. No source, account, installation or provider writes.
  await page.route("**/api/v1/**", (route) => {
    const request = route.request(),
      url = new URL(request.url()),
      path = url.pathname;
    if (path === "/api/v1/workspace/web-vitals" && request.method() === "POST")
      return route.fulfill({ status: 202, json: {} });
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: "controlled-knowledge-user",
          tenant_id: "controlled-knowledge-tenant",
          email: "knowledge-language@example.test",
          display_name: "Controlled fixture",
          role: "analyst",
        },
      });
    if (path.startsWith("/api/v1/knowledge/")) reads.push(path);
    if (path.endsWith("/knowledge/pages/search"))
      return route.fulfill({
        json: url.searchParams.get("q") === "empty" ? { ...fixture.search, items: [], total: 0 } : fixture.search,
      });
    if (path.endsWith(`/pages/${fixture.detail.id}`)) return route.fulfill({ json: fixture.detail });
    if (path.endsWith("/coverage"))
      return failCoverage
        ? route.fulfill({ status: 503, json: { detail: "原始诊断 / coverage unavailable" } })
        : route.fulfill({ json: fixture.coverage });
    if (path.endsWith("/versions")) return route.fulfill({ json: fixture.versions });
    if (path.endsWith("/diff")) {
      const first = path.endsWith("/versions/1/diff");
      return route.fulfill({
        json: { ...fixture.diff, from_version_number: first ? null : 1, to_version_number: first ? 1 : 2 },
      });
    }
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
  await page.goto(`/workspace/research?view=knowledge&page=${fixture.detail.id}`);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { name: fixture.detail.title, exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Show 1 supplementary fields", exact: true }).click();
  await expect(page.locator(".knowledge-value-field-value").filter({ hasText: /^false$/ })).toBeVisible();
  await expect(page.locator(".knowledge-value-field-value").filter({ hasText: /^2028-02$/ })).toBeVisible();
  await expect(
    page.locator(".knowledge-value-field-value").filter({ hasText: /^Phase II, FUTURE_PHASE$/ }),
  ).toBeVisible();
  await page.locator("details.knowledge-original-document > summary").click();
  await expect(
    page.getByRole("textbox", { name: "Complete public original for this version", exact: true }),
  ).toHaveValue(fixture.detail.rendered_markdown);
  await audit("knowledge-original-en");
  if ((page.viewportSize()?.width ?? 1440) < 900)
    await page.getByRole("button", { name: "Expand Topic directory", exact: true }).click();
  const titleLayout = await page
    .locator(".knowledge-page-list strong")
    .first()
    .evaluate((node) => {
      const range = document.createRange();
      range.selectNodeContents(node);
      const bounds = node.getBoundingClientRect();
      return [...range.getClientRects()].map((rect) => ({
        right: rect.right,
        bottom: rect.bottom,
        ownerRight: bounds.right,
        ownerBottom: bounds.bottom,
      }));
    });
  for (const rect of titleLayout) {
    expect(rect.right).toBeLessThanOrEqual(rect.ownerRight + 1);
    expect(rect.bottom).toBeLessThanOrEqual(rect.ownerBottom + 1);
  }
  await page.getByRole("textbox", { name: "Search knowledge topics", exact: true }).fill("未提交研究草稿");
  const selectedUrl = page.url(),
    before = reads.length;
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("textbox", { name: "检索知识专题", exact: true })).toHaveValue("未提交研究草稿");
  await expect(page.getByRole("button", { name: "收起补充字段", exact: true })).toHaveAttribute(
    "aria-expanded",
    "true",
  );
  await expect(page.getByRole("textbox", { name: "此版本的完整公开原文", exact: true })).toHaveValue(
    fixture.detail.rendered_markdown,
  );
  expect(reads).toHaveLength(before);
  expect(page.url()).toBe(selectedUrl);
  if ((page.viewportSize()?.width ?? 1440) < 900)
    await page.getByRole("button", { name: "收起专题目录", exact: true }).click();
  await page.getByRole("tab", { name: "覆盖与版本", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("原始诊断 / coverage unavailable");
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("alert")).toContainText("原始诊断 / coverage unavailable");
  failCoverage = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("table", { name: "Knowledge fact coverage", exact: true })).toBeVisible();
  const history = page.getByRole("list", { name: "Topic versions", exact: true });
  await history.getByRole("button").filter({ hasText: "v1" }).click();
  await expect(page).toHaveURL(/panel=coverage.*version=1/);
  await expect(page.getByRole("heading", { name: "Initial version v1", exact: true })).toBeVisible();
  await expect(page.locator(".knowledge-change-list")).toContainText("FUTURE_PHASE");
  await expect(page.locator(".knowledge-change-list")).toContainText("page=4;paragraph=2");
  await audit("knowledge-version-en");
  const versionUrl = page.url(),
    cached = reads.length;
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("heading", { name: "初始版本 v1", exact: true })).toBeVisible();
  expect(reads).toHaveLength(cached);
  expect(page.url()).toBe(versionUrl);
  await audit("knowledge-version-zh");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "zh-CN");
  await expect(
    page.getByRole("list", { name: "专题版本", exact: true }).getByRole("button").filter({ hasText: "v1" }),
  ).toHaveAttribute("aria-current", "true");
  await selectInterfaceLanguage(page, "en");
  await page.goto("/workspace/research?view=knowledge&q=empty");
  await expect(page.getByText("No knowledge topics", { exact: true })).toBeVisible();
  await expect(page.getByText("Select a knowledge topic", { exact: true })).toBeVisible();
  await audit("knowledge-empty-en");
  expect(writes).toEqual([]);
});
