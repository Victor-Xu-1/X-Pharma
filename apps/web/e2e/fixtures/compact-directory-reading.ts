import { expect, type Page, type TestInfo } from "@playwright/test";

/** Exercise the gap between the 760px shell and 900px directory boundaries once. */
export async function expectIntermediateDirectoryReading(
  page: Page,
  testInfo: TestInfo,
  kind: "knowledge" | "collections",
  title: "Topic directory" | "List directory",
) {
  if (testInfo.project.name !== "desktop-1440") return;
  const originalViewport = page.viewportSize();
  if (!originalViewport) throw new Error("The reviewed browser viewport is required");
  const originalUrl = page.url();
  try {
    await page.setViewportSize({ width: 768, height: 900 });
    const directory = page.locator(kind === "knowledge" ? ".knowledge-index" : ".collections-list");
    const toggle = directory.getByRole("button", { name: `Expand ${title}`, exact: true });
    await expect(toggle).toBeVisible();
    await expect(directory.locator(".responsive-directory-content")).toBeHidden();
    const layout = page.locator(kind === "knowledge" ? ".knowledge-layout" : ".collections-layout");
    const geometry = await layout.evaluate((node) => ({
      width: node.clientWidth,
      readingWidth: node.lastElementChild?.getBoundingClientRect().width ?? 0,
    }));
    expect(geometry.readingWidth).toBeGreaterThanOrEqual(geometry.width);
    await page.screenshot({ path: testInfo.outputPath(`${kind}-reading-768.png`), animations: "disabled" });
    await toggle.click();
    await expect(directory.locator(".responsive-directory-content")).toBeVisible();
    await directory.getByRole("button", { name: `Collapse ${title}`, exact: true }).click();
    await expect(directory.locator(".responsive-directory-content")).toBeHidden();
    expect(page.url()).toBe(originalUrl);
  } finally {
    await page.setViewportSize(originalViewport);
  }
}
