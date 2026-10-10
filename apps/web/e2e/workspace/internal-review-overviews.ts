import { expect, type Page, type TestInfo } from "@playwright/test";

/** The unchanged internal-overview contract, reusable independently of unrelated research tasks. */
export async function verifyInternalReviewOverviews(page: Page, testInfo: Pick<TestInfo, "outputPath">) {
  const origin = new URL(page.url()).origin;
  for (const view of ["factory", "governance", "commercial", "enterprise"]) {
    await page.goto(`${origin}/workspace/internal?view=${view}`);
    await expect(page.locator(".page-heading h1")).toBeVisible();
    if (view === "factory") await expect(page.getByRole("heading", { name: "自动数据源", exact: true })).toBeVisible();
    else {
      const label = view === "governance" ? "治理队列" : view === "commercial" ? "商业运营视图" : "企业管理视图";
      await expect(page.getByRole("tablist", { name: label, exact: true })).toBeVisible();
    }
    await expect(page.locator("main .spinner"), `${view} overview must finish loading`).toHaveCount(0);
    const alerts = page.locator("main [role=alert]");
    try {
      await expect(alerts, `${view} overview must contain no error alerts`).toHaveCount(0);
    } catch (cause) {
      throw new Error(`${view} overview (${page.url()}): ${(await alerts.allTextContents()).join(" | ")}`, { cause });
    }
    const layout = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(layout.scrollWidth, `${view} overflow: ${JSON.stringify(layout)}`).toBeLessThanOrEqual(layout.width);
    await page.screenshot({ path: testInfo.outputPath(`researcher-${view}.png`), fullPage: true });
  }
}
