import { expect, test } from "@playwright/test";

test("[browser-identity] runs the configured commercial browser binary", async ({ browser, page }) => {
  const expectedProduct = process.env.E2E_EXPECTED_BROWSER_PRODUCT;
  const expectedVersion = process.env.E2E_EXPECTED_BROWSER_VERSION;
  test.skip(
    !expectedProduct || !expectedVersion,
    "Browser identity evidence is only required by the acceptance runner",
  );
  if (!expectedProduct || !expectedVersion) return;

  expect(browser.version()).toBe(expectedVersion);
  await page.goto("/");
  const brands = await page.evaluate(() => {
    const navigatorWithBrands = navigator as Navigator & {
      userAgentData?: { brands?: Array<{ brand: string; version: string }> };
    };
    return navigatorWithBrands.userAgentData?.brands?.map(({ brand }) => brand) ?? [];
  });
  expect(brands).toContain(expectedProduct);
});
