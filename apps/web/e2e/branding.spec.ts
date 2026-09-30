import { expect, test } from "@playwright/test";

for (const entry of ["/", "/workspace/research", "/workspace/internal"]) {
  test(`loads the supplied X-Pharma logo and browser icons at ${entry}`, async ({ page }) => {
    const failedAssets: string[] = [];
    page.on("response", (response) => {
      if (response.url().includes("X-Pharma-") && !response.ok()) failedAssets.push(response.url());
    });
    await page.goto(entry);
    const mark = page.locator(".brand-symbol img");
    await expect(mark).toBeVisible();
    await expect(page.locator(".brand-lockup strong")).toHaveText("X-Pharma");
    await expect(mark).toHaveAttribute("src", /\/assets\/X-Pharma-logo-128-[\w-]+\.png$/);
    await expect.poll(() => mark.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBe(128);
    expect(await page.title()).toMatch(/^X-Pharma(?: Operations)?$/);
    const icons = await page
      .locator('link[rel="icon"], link[rel="apple-touch-icon"]')
      .evaluateAll((links) =>
        links.map((link) => ({ href: link.getAttribute("href") ?? "", type: link.getAttribute("type") })),
      );
    expect(icons).toHaveLength(4);
    for (const icon of icons) {
      expect(icon.href).toMatch(/^\/assets\/X-Pharma-[\w-]+\.(png|ico)$/);
      const response = await page.request.get(icon.href);
      expect(response.status()).toBe(200);
      expect(response.headers()["content-type"]).toMatch(/image\/(png|x-icon|vnd.microsoft.icon)/);
      expect(response.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
      expect((await response.body()).length).toBeGreaterThan(100);
    }
    await page.reload();
    await expect(mark).toBeVisible();
    await expect.poll(() => mark.evaluate((image: HTMLImageElement) => image.complete && image.naturalWidth)).toBe(128);
    expect(failedAssets).toEqual([]);
  });
}
