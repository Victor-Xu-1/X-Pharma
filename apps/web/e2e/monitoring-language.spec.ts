import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { monitoringLanguageFixture } from "./fixtures/monitoring-language";
import { selectInterfaceLanguage } from "./interface-language";

test("[monitoring-language] preserves original conditions, pending metadata, pinned queries and access recovery", async ({
  page,
  context,
}, testInfo) => {
  const fixture = monitoringLanguageFixture(),
    saved = fixture.searches[0];
  const errors: string[] = [],
    writes: string[] = [];
  let reads = 0,
    simulatedUpdates = 0,
    denied = false,
    finishSave: (() => void) | undefined;
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname;
    if (path === "/api/v1/workspace/web-vitals" && request.method() === "POST")
      return route.fulfill({ status: 202, json: {} });
    // Only the exact browser-only metadata update is simulated. No actual writes.
    if (path === `/api/v1/monitoring/saved-searches/${saved.id}` && request.method() === "PATCH") {
      expect(Object.keys(request.postDataJSON()).sort()).toEqual(["description", "name"]);
      simulatedUpdates++;
      await new Promise<void>((resolve) => {
        finishSave = resolve;
      });
      return route.fulfill({ status: 503, json: { detail: "原始更新诊断 / unavailable" } });
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      writes.push(`${request.method()} ${path}`);
      return route.abort("blockedbyclient");
    }
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me")
      return route.fulfill({
        json: {
          id: saved.owner_user_id,
          tenant_id: "controlled-monitor-tenant",
          role: "analyst",
          email: "monitoring-language@example.test",
          display_name: "Controlled browser fixture",
        },
      });
    if (path.startsWith("/api/v1/monitoring/") && request.frame().page() === page) reads++;
    if (denied && path === "/api/v1/monitoring/saved-searches")
      return route.fulfill({ status: 403, json: { detail: "Read access denied / 原始诊断" } });
    if (path === "/api/v1/monitoring/saved-searches") return route.fulfill({ json: fixture.searches });
    if (path === "/api/v1/monitoring/topics") return route.fulfill({ json: fixture.topics });
    if (path === "/api/v1/monitoring/alerts") return route.fulfill({ json: fixture.alerts });
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
  await page.goto("/workspace/research?view=monitoring&monitor_tab=searches");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const savedRow = page.getByRole("row").filter({ has: page.getByText(saved.name, { exact: true }) });
  const disclosure = savedRow.locator("details.monitoring-record-conditions");
  await disclosure.locator("summary").click();
  await expect(disclosure.getByRole("list", { name: "All saved query conditions", exact: true })).toContainText(
    "Trial status=Recruiting",
  );
  await expect(disclosure).toContainText("Trial phase=Phase II");
  await expect(disclosure).toContainText("Results posted=No");
  await expect(disclosure).toContainText("Disclosure from=2026-02-01");
  await expect(disclosure).toContainText("FUTURE_MODALITY");
  await expect(disclosure).toContainText("Sort direction=desc");
  await expect(disclosure).not.toContainText("opaque-fixture-one");
  await savedRow.locator("details.monitoring-record-description:not(.monitoring-record-conditions) > summary").click();
  await expect(savedRow).toContainText(saved.description);
  const before = reads,
    url = page.url();
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(disclosure).toHaveAttribute("open", "");
  await expect(disclosure.getByRole("list", { name: "全部检索条件", exact: true })).toContainText("结果披露=否");
  await expect(savedRow).toContainText(saved.description);
  expect(reads).toBe(before);
  expect(page.url()).toBe(url);
  await audit("monitoring-conditions-zh");
  await selectInterfaceLanguage(page, "en");
  const languagePage = await context.newPage();
  await languagePage.goto(url);
  await languagePage.waitForLoadState("networkidle");
  await savedRow.getByRole("button", { name: `Edit ${saved.name}`, exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Edit saved search", exact: true });
  await dialog.getByRole("textbox", { name: "Name", exact: true }).fill("编辑中的监控草稿");
  await dialog.getByRole("button", { name: "Save changes", exact: true }).click();
  await expect(dialog.getByRole("textbox", { name: "Name", exact: true })).toBeDisabled();
  await selectInterfaceLanguage(languagePage, "zh-CN");
  const chinese = page.getByRole("dialog", { name: "编辑已保存检索", exact: true });
  await expect(chinese.getByRole("textbox", { name: "名称", exact: true })).toHaveValue("编辑中的监控草稿");
  await expect(chinese.getByRole("button", { name: "保存中", exact: true })).toBeDisabled();
  await audit("monitoring-pending-zh");
  expect(finishSave).toBeDefined();
  finishSave?.();
  await expect(chinese.getByRole("alert")).toContainText("原始更新诊断 / unavailable");
  await expect(chinese.getByRole("textbox", { name: "名称", exact: true })).toBeEnabled();
  await selectInterfaceLanguage(languagePage, "en");
  await expect(dialog.getByRole("alert")).toContainText("原始更新诊断 / unavailable");
  await expect(dialog.getByRole("textbox", { name: "Name", exact: true })).toHaveValue("编辑中的监控草稿");
  await dialog.getByRole("button", { name: "Cancel", exact: true }).click();
  await languagePage.close();
  await page.getByRole("tab", { name: "Monitoring topics", exact: true }).click();
  await expect(page.getByText("Pinned to v1", { exact: true })).toHaveCount(2);
  await expect(page.getByText("Monitoring", { exact: true })).toBeVisible();
  await expect(page.getByText("Paused", { exact: true })).toBeVisible();
  await expect(
    page
      .getByRole("combobox", { name: "Choose a saved search", exact: true })
      .getByRole("option", { name: "Controlled structure search", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("textbox", { name: "Monitoring topic name", exact: true }).fill("未提交主题草稿");
  await audit("monitoring-topics-en");
  denied = true;
  await page.getByRole("button", { name: "Refresh current results", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Read access denied / 原始诊断");
  await expect(page.getByText("原始固定主题", { exact: true })).toHaveCount(0);
  await expect(page.getByText(saved.name, { exact: true })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Monitoring topic name", exact: true })).toHaveCount(0);
  await audit("monitoring-access-denied-en");
  denied = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "Monitoring topic name", exact: true })).toHaveValue("未提交主题草稿");
  await expect(page.getByRole("tab", { name: "Monitoring topics", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await audit("monitoring-recovered-en");
  await page.getByRole("tab", { name: "Alert center", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "Unread only", exact: true })).toBeVisible();
  await expect(page.getByText(fixture.alerts[0].summary, { exact: true })).toBeVisible();
  await audit("monitoring-alerts-en");
  expect(simulatedUpdates).toBe(1);
  expect(writes).toEqual([]);
});
