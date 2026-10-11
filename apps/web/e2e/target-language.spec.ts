import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { targetLanguageFixture, targetPipelineLanguageFixture } from "./fixtures/target-language";
import { selectInterfaceLanguage } from "./interface-language";

test("[target-language] preserves target narratives, complete counts, filters, registry identity and cached reads", async ({
  page,
}, testInfo) => {
  const fixture = targetLanguageFixture();
  let dossierReads = 0;
  let pipelineReads = 0;
  let nextPipelineReply: Promise<number> | undefined;
  let failedPipelineUrl: string | undefined;
  let failedPipelineReplies = 0;
  function holdNextPipelineReply() {
    let release!: (status: number) => void;
    nextPipelineReply = new Promise((resolve) => {
      release = resolve;
    });
    return release;
  }
  const writes: string[] = [];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // Only controlled API fixtures. No real identity, facts, provider calls or server mutations.
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    // The existing UI emits bounded performance telemetry; fulfill it locally too.
    // This is not a scientific/account write and never reaches a real service.
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
          id: "controlled-target-user",
          tenant_id: "controlled-target-tenant",
          email: "target-language@example.test",
          display_name: "Controlled browser fixture",
          role: "analyst",
        },
      });
    if (path === `/api/v1/entities/${fixture.entity.id}`) return route.fulfill({ json: fixture.entity });
    if (path === `/api/v1/targets/${fixture.entity.id}/dossier`) {
      dossierReads++;
      return route.fulfill({ json: fixture });
    }
    if (path === "/api/v1/pipelines") {
      pipelineReads++;
      const held = nextPipelineReply;
      nextPipelineReply = undefined;
      const status = request.url() === failedPipelineUrl ? 503 : held ? await held : 200;
      if (status !== 200) {
        failedPipelineUrl = request.url();
        failedPipelineReplies++;
        return route.fulfill({ status, json: { detail: "Controlled pipeline refinement failed" } });
      }
      return route.fulfill({ json: targetPipelineLanguageFixture() });
    }
    return route.fulfill({ json: [] });
  });
  async function audit(name: string) {
    const rail = page.getByRole("tablist").filter({ has: page.locator('[data-tab-key="pipeline"]') });
    const horizontalBounds = await rail.evaluate((node) => {
      const selected = node.querySelector('[aria-selected="true"]');
      if (!selected) throw new Error("An active dossier tab is required");
      const visible = node.getBoundingClientRect(),
        active = selected.getBoundingClientRect();
      return {
        left: visible.left,
        right: visible.right,
        selectedLeft: active.left,
        selectedRight: active.right,
        scrollLeft: node.scrollLeft,
      };
    });
    expect(horizontalBounds.selectedLeft).toBeGreaterThanOrEqual(horizontalBounds.left - 1);
    expect(horizontalBounds.selectedRight).toBeLessThanOrEqual(horizontalBounds.right + 1);
    expect(
      (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze()).violations,
    ).toEqual([]);
    const afterAuditScroll = await rail.evaluate((node) => node.scrollLeft);
    await testInfo.attach(`${name}-tab-geometry`, {
      body: JSON.stringify({ beforeAccessibility: horizontalBounds, afterAccessibilityScrollLeft: afterAuditScroll }),
      contentType: "application/json",
    });
    const bounds = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
    }));
    expect(bounds.document).toBeLessThanOrEqual(bounds.viewport);
    expect(errors).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: false, animations: "disabled" });
  }
  await page.goto(`/workspace/research?view=target&entity=${fixture.entity.id}&section=overview`);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("heading", { name: "Function summary", exact: true })).toBeVisible();
  await expect(page.locator(".narrative-section p")).toHaveText(fixture.entity.description ?? "");
  await expect(page.getByText("1,200 related records; 50 currently shown", { exact: true })).toBeVisible();
  await expect(page.getByText("137 recruiting trials", { exact: true })).toBeVisible();
  await audit("target-overview-en");
  await page.getByRole("tab", { name: "Translational evidence", exact: true }).click();
  const filterLayout = await page.locator(".target-evidence-filters").evaluate((node) => {
    const style = getComputedStyle(node);
    const labels = [...node.querySelectorAll("label")].map((label) => {
      const bounds = label.getBoundingClientRect();
      return { y: bounds.y, bottom: bounds.bottom };
    });
    return {
      borderTop: style.borderTopStyle,
      borderLeft: style.borderLeftStyle,
      borderRight: style.borderRightStyle,
      labels,
    };
  });
  expect([filterLayout.borderTop, filterLayout.borderLeft, filterLayout.borderRight]).toEqual(["none", "none", "none"]);
  if ((page.viewportSize()?.width ?? 1440) < 500)
    expect(filterLayout.labels[1].y).toBeGreaterThanOrEqual(filterLayout.labels[0].bottom);
  await page.getByRole("combobox", { name: "Evidence type", exact: true }).selectOption("expression");
  await expect(page.getByText("No evidence matches the current filters", { exact: true })).toBeVisible();
  const emptyUrl = page.url();
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("combobox", { name: "证据类型", exact: true })).toHaveValue("expression");
  await expect(page.getByText("当前筛选条件下无匹配证据", { exact: true })).toBeVisible();
  expect(page.url()).toBe(emptyUrl);
  await page.getByRole("combobox", { name: "证据类型", exact: true }).selectOption("genetic_association");
  await page.getByRole("combobox", { name: "证据方向", exact: true }).selectOption("supports");
  await selectInterfaceLanguage(page, "en");
  await expect(page.getByRole("combobox", { name: "Evidence direction", exact: true })).toHaveValue("supports");
  const evidence = page.getByRole("table", { name: "Target translational evidence", exact: true });
  await expect(evidence).toContainText(fixture.target_evidence[0].summary);
  await expect(evidence).toContainText("Supports the target hypothesis");
  await audit("target-evidence-en");
  await page.getByRole("tab", { name: "Relationship network", exact: true }).click();
  const relationships = page.getByRole("table", { name: "Target entity relationships", exact: true });
  await expect(relationships).toContainText("Registry sponsor");
  await expect(relationships).toContainText("原始登记申办方 — browser fixture");
  await audit("target-relationships-en");
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("tab", { name: "关系网络", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("table", { name: "靶点实体关系", exact: true })).toContainText("登记申办方");
  expect(dossierReads).toBe(1);
  expect(writes).toEqual([]);
  await audit("target-relationships-zh");
  await selectInterfaceLanguage(page, "en");
  await page.getByRole("tab", { name: "Competitive pipeline", exact: true }).click();
  const panel = page.locator(".target-pipeline-panel");
  await expect(panel.getByRole("button", { name: "Drug overview", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect.poll(() => pipelineReads).toBe(1);
  await expect(
    panel.getByText(
      "Missing records do not imply that none exist globally. Results depend on source access, update time and visibility.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(panel.getByText("原始管线警告 / Unchanged pipeline source warning", { exact: true })).toBeVisible();
  await expect(panel.locator(".target-pipeline-metric")).toHaveCount(2);
  for (const metric of await panel.locator(".target-pipeline-metric").all()) {
    const spacing = await metric.evaluate((node) => {
      const count = node.querySelector("strong"),
        unit = node.querySelector("span");
      if (!count || !unit) throw new Error("Count and unit must be separate readable elements");
      return unit.getBoundingClientRect().left - count.getBoundingClientRect().right;
    });
    expect(spacing).toBeGreaterThanOrEqual(4);
  }
  const group = panel.locator(".pipeline-advanced-filters");
  await expect(group).toHaveClass(/secondary-filter-panel/);
  await group.locator(":scope > summary").focus();
  await page.keyboard.press("Enter");
  await expect(group).toHaveAttribute("open", "");
  const releaseDateReply = holdNextPipelineReply();
  const dateInput = panel.getByLabel("Global phase start dates From", { exact: true });
  await dateInput.fill("2026-01-01");
  await expect.poll(() => pipelineReads).toBe(2);
  await expect(panel.locator(".spinner")).toHaveCount(1);
  await expect(dateInput).toBeFocused();
  await expect(dateInput).toHaveValue("2026-01-01");
  await expect(panel.getByRole("table", { name: "Target drug development overview", exact: true })).toHaveCount(0);
  await expect(
    panel.getByText("Filter options are from the last completed query; current results are updating.", { exact: true }),
  ).toBeVisible();
  releaseDateReply(200);
  await expect(panel.locator(".spinner")).toHaveCount(0);
  await expect(dateInput).toBeFocused();
  await panel
    .getByRole("combobox", { name: "Organization location", exact: true })
    .selectOption("原始地区 / Source country");
  await expect.poll(() => pipelineReads).toBe(3);
  await expect(panel.locator(".spinner")).toHaveCount(0);
  const pipelineUrl = page.url(),
    readsBeforeLanguage = pipelineReads;
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(panel.getByLabel("全球阶段开始日期起", { exact: true })).toHaveValue("2026-01-01");
  await expect(panel.getByRole("combobox", { name: "机构所在地区", exact: true })).toHaveValue(
    "原始地区 / Source country",
  );
  await expect(group).toHaveAttribute("open", "");
  expect(pipelineReads).toBe(readsBeforeLanguage);
  await expect(
    panel.getByText("暂无记录不代表全球不存在；结果受来源授权、更新时间和可见范围影响。", { exact: true }),
  ).toBeVisible();
  await expect(panel.getByText("原始管线警告 / Unchanged pipeline source warning", { exact: true })).toBeVisible();
  expect(page.url()).toBe(pipelineUrl);
  await audit("controlled-target-pipeline-zh");
  await selectInterfaceLanguage(page, "en");
  await expect(panel.getByLabel("Global phase start dates From", { exact: true })).toHaveValue("2026-01-01");
  expect(pipelineReads).toBe(readsBeforeLanguage);
  await panel.getByRole("button", { name: "Reset filters", exact: true }).click();
  await expect(panel.locator(".spinner")).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "Reset filters", exact: true })).toBeDisabled();
  await expect(group).toHaveAttribute("data-active-count", "0");
  await expect(group).toHaveAttribute("open", "");
  await expect(panel.getByLabel("Global phase start dates From", { exact: true })).toHaveValue("");
  expect(dossierReads).toBe(1);
  expect(writes).toEqual([]);
  await audit("controlled-target-pipeline-cleared-en");
  const searchInput = panel.getByRole("searchbox", { name: "Drug or organization", exact: true });
  const releaseFailureReply = holdNextPipelineReply();
  await searchInput.fill("Controlled delayed refinement");
  await expect(panel.locator(".spinner")).toHaveCount(1);
  await expect(searchInput).toBeFocused();
  releaseFailureReply(503);
  await expect(panel.getByRole("alert")).toContainText("Controlled pipeline refinement failed");
  await expect(panel.getByRole("alert")).toBeInViewport();
  const feedbackHeight = await panel
    .locator(".target-pipeline-feedback")
    .evaluate((node) => node.getBoundingClientRect().height);
  const inputNotObscured = await searchInput.evaluate((node) => {
    const bounds = node.getBoundingClientRect();
    return document.elementFromPoint(bounds.left + bounds.width / 2, bounds.top + bounds.height / 2) === node;
  });
  expect({ compactFeedback: feedbackHeight <= 160, inputNotObscured }).toEqual({
    compactFeedback: true,
    inputNotObscured: true,
  });
  expect(failedPipelineReplies).toBe(3);
  await expect(searchInput).toBeFocused();
  await expect(searchInput).toHaveValue("Controlled delayed refinement");
  await expect(panel.getByRole("button", { name: "Select this page", exact: true })).toBeDisabled();
  await audit("controlled-target-pipeline-failed-en");
  await panel.getByRole("button", { name: "Reset filters", exact: true }).click();
  await expect(
    panel.getByText(`No development program records for ${fixture.entity.name}`, { exact: true }),
  ).toBeVisible();
  await expect(searchInput).toHaveValue("");
  await expect(panel.getByRole("alert")).toHaveCount(0);
  expect(dossierReads).toBe(1);
  expect(writes).toEqual([]);
});
