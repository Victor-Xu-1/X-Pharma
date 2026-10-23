import { expect } from "@playwright/test";
import { selectInterfaceLanguage } from "../../interface-language";
import {
  expandProfessionalQuery,
  installBrowserQualityProbe,
  navigateResearchView,
  openNavigation,
  readBrowserQualityMetrics,
} from "../helpers";
import type { verifySetup } from "./setup";

type AppearanceContext = Pick<
  Awaited<ReturnType<typeof verifySetup>>,
  "page" | "testInfo" | "credentials" | "fixtureKey" | "rumBatches" | "rumStatuses"
>;

export async function verifyLoginAndAppearance(context: Awaited<ReturnType<typeof verifySetup>>) {
  return { ...context, ...(await verifyResearchAppearance(context)) };
}

export async function verifyResearchAppearance(context: AppearanceContext) {
  const { page, testInfo, credentials, fixtureKey, rumBatches, rumStatuses } = context;
  await installBrowserQualityProbe(page);
  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("research");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await openNavigation(page);
  await page.getByRole("navigation", { name: "账户导航" }).getByRole("button", { name: "用户中心" }).click();
  await expect(page.getByRole("heading", { name: "用户中心", level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "个人资料" })).toBeVisible();
  await expect(page.getByLabel("邮箱", { exact: true })).toHaveValue(credentials.email);
  await expect(page.getByText(/租户|治理状态|权限角色/)).toHaveCount(0);
  await expect(page).toHaveURL(/\/workspace\/research/);
  const initialAssetResources = await page.evaluate(() =>
    (performance.getEntriesByType("resource") as PerformanceResourceTiming[])
      .map((entry) => ({
        pathname: new URL(entry.name).pathname,
        decodedBodySize: entry.decodedBodySize,
        encodedBodySize: entry.encodedBodySize,
      }))
      .filter((entry) => entry.pathname.startsWith("/assets/")),
  );
  const forbiddenInitialAssets = initialAssetResources.filter((entry) =>
    /(?:\.wasm$|rdkit|indigo|ketcher|structureeditor)/i.test(entry.pathname),
  );
  expect(forbiddenInitialAssets).toEqual([]);
  const largestInitialAssetBytes = Math.max(0, ...initialAssetResources.map((entry) => entry.decodedBodySize));
  expect(largestInitialAssetBytes).toBeLessThanOrEqual(600 * 1024);
  testInfo.annotations.push({
    type: "initial-load-boundary",
    description: JSON.stringify({
      asset_count: initialAssetResources.length,
      largest_decoded_asset_bytes: largestInitialAssetBytes,
      encoded_asset_bytes: initialAssetResources.reduce((total, entry) => total + entry.encodedBodySize, 0),
      deferred_professional_assets_loaded: false,
    }),
  });
  const researchNavigation = page.getByRole("navigation", { name: "主导航", includeHidden: true });
  for (const internalView of ["数据工厂", "AI 审核", "商业运营", "企业管理"]) {
    await expect(
      researchNavigation.getByRole("button", { name: internalView, exact: true, includeHidden: true }),
    ).toHaveCount(0);
  }
  await openNavigation(page);
  const professionalLauncher = page.getByRole("navigation", { name: "主导航" });
  for (const domain of ["情报检索", "研发数据", "竞争情报", "研究动态", "我的研究"]) {
    await expect(professionalLauncher.getByRole("button", { name: domain, exact: true })).toBeVisible();
  }
  await expect(professionalLauncher.getByRole("button")).toHaveCount(5);
  await navigateResearchView(page, "patents");
  await expect(page).toHaveURL(/view=patents/);
  await expect(page.getByRole("heading", { name: "专利族与资产关联", level: 1 })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();

  // Reset navigation-scoped Web Vitals after authentication so LCP measures the workbench, not the login page.
  await page.goto("/workspace/research?view=overview");
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();
  await openNavigation(page);
  await page.getByRole("button", { name: "情报检索" }).click();
  await expect(page.getByRole("button", { name: "情报检索", includeHidden: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeFocused();
  await page.getByLabel("情报检索词").fill("visual-baseline-no-match");
  await page.getByLabel("情报检索词").press("Enter");
  const emptyEntityState = page.getByRole("status").filter({ hasText: "未找到匹配实体" });
  await expect(emptyEntityState).toBeVisible();
  await expect(emptyEntityState).toHaveAttribute("aria-live", "polite");
  await expandProfessionalQuery(page);
  await expect(
    page
      .getByRole("region", { name: "专业条件查询" })
      .getByRole("group", { name: "药物模态" })
      .getByLabel("药物模态：全部"),
  ).toBeVisible();
  await expect.soft(page).toHaveScreenshot("research-workbench.png", {
    animations: "disabled",
    caret: "hide",
    fullPage: true,
    maxDiffPixelRatio: 0.001,
  });
  const browserQuality = await readBrowserQualityMetrics(page);
  testInfo.annotations.push({ type: "browser-quality-metrics", description: JSON.stringify(browserQuality) });
  expect(browserQuality.lcp_ms).toBeGreaterThan(0);
  expect(browserQuality.lcp_ms).toBeLessThanOrEqual(2_500);
  expect(browserQuality.interaction_count).toBeGreaterThan(0);
  expect(browserQuality.inp_ms).toBeLessThanOrEqual(200);
  expect(browserQuality.cls).toBeLessThanOrEqual(0.1);
  await expect.poll(() => rumBatches.length).toBeGreaterThan(0);
  await expect.poll(() => rumStatuses.length).toBeGreaterThan(0);
  expect(rumStatuses.every((status) => status === 202)).toBe(true);
  const rumSamples = rumBatches.flatMap((batch) => {
    expect(batch.schema_version).toBe(1);
    expect(batch.samples.length).toBeGreaterThan(0);
    expect(batch.samples.length).toBeLessThanOrEqual(8);
    return batch.samples;
  });
  expect(rumSamples.some((sample) => sample.metric_name === "LCP" || sample.metric_name === "TTFB")).toBe(true);
  for (const sample of rumSamples) {
    expect(Object.keys(sample).sort()).toEqual([
      "metric_name",
      "navigation_sequence",
      "navigation_type",
      "rating",
      "route",
      "value",
      "viewport_class",
    ]);
    expect(sample.route).not.toBe("unknown");
    expect(Number.isFinite(sample.value)).toBe(true);
  }
  const serializedRum = JSON.stringify(rumBatches);
  expect(serializedRum).not.toContain("visual-baseline-no-match");
  expect(serializedRum).not.toContain(fixtureKey);
  expect(serializedRum).not.toMatch(/[0-9a-f]{8}-[0-9a-f-]{27}/i);
  expect(serializedRum).not.toContain("http");
  return {
    ...context,
    initialAssetResources,
    forbiddenInitialAssets,
    largestInitialAssetBytes,
    researchNavigation,
    professionalLauncher,
    emptyEntityState,
    browserQuality,
    rumSamples,
    serializedRum,
  };
}
