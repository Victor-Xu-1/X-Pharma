import { readFile } from "node:fs/promises";

import { expect, type Locator, type Page, type Route, test } from "@playwright/test";

import { resolveBrowserCredentials } from "../src/lib/browserAcceptanceCredentials";
import type { EnterpriseApiKeyCatalogRead, WebVitalBatchCreate } from "../src/lib/generated";

type BrowserQualityMetrics = {
  cls: number;
  inp_ms: number;
  interaction_count: number;
  lcp_ms: number;
};

async function expandProfessionalQuery(page: Page) {
  const filters = page.locator("details.explorer-professional-query");
  if ((await filters.getAttribute("open")) === null) await filters.locator("summary").click();
}

async function installBrowserQualityProbe(page: Page) {
  await page.addInitScript(() => {
    const metrics = {
      cls: 0,
      inp_ms: 0,
      interaction_ids: new Set<number>(),
      lcp_ms: 0,
    };
    Object.defineProperty(window, "__pharmaBrowserQuality", {
      configurable: false,
      enumerable: false,
      value: metrics,
      writable: false,
    });

    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) metrics.lcp_ms = Math.max(metrics.lcp_ms, entry.startTime);
    }).observe({ type: "largest-contentful-paint", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const shift = entry as PerformanceEntry & { hadRecentInput?: boolean; value?: number };
        if (!shift.hadRecentInput) metrics.cls += shift.value ?? 0;
      }
    }).observe({ type: "layout-shift", buffered: true });
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const interaction = entry as PerformanceEntry & { duration: number; interactionId?: number };
        if (!interaction.interactionId) continue;
        metrics.interaction_ids.add(interaction.interactionId);
        metrics.inp_ms = Math.max(metrics.inp_ms, interaction.duration);
      }
    }).observe({ type: "event", buffered: true, durationThreshold: 16 });
  });
}

async function readBrowserQualityMetrics(page: Page): Promise<BrowserQualityMetrics> {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  });
  return page.evaluate(() => {
    const metrics = (
      window as typeof window & {
        __pharmaBrowserQuality: {
          cls: number;
          inp_ms: number;
          interaction_ids: Set<number>;
          lcp_ms: number;
        };
      }
    ).__pharmaBrowserQuality;
    const observedLcp = performance
      .getEntriesByType("largest-contentful-paint")
      .reduce((max, entry) => Math.max(max, entry.startTime), 0);
    if (observedLcp > metrics.lcp_ms) metrics.lcp_ms = observedLcp;
    return {
      cls: metrics.cls,
      inp_ms: metrics.inp_ms,
      interaction_count: metrics.interaction_ids.size,
      lcp_ms: metrics.lcp_ms,
    };
  });
}

async function openNavigation(page: Page) {
  const navigation = page.getByRole("navigation", { name: "主导航" });
  await expect(navigation).toBeAttached();
  const sidebar = page.locator(".workspace-sidebar");
  const openButton = page.getByTitle("打开导航");
  if (
    (await openButton.isVisible()) &&
    !(await sidebar.evaluate((element) => element.classList.contains("mobile-open")))
  ) {
    await openButton.click();
    await expect(sidebar).toHaveClass(/mobile-open/);
  }
}

async function findDataFactoryRunRow(page: Page, workflowId: string): Promise<Locator> {
  const pagination = page.getByRole("navigation", { name: "入库运行记录分页" });
  const pageIndicator = pagination.getByText(/第 \d+ \/ \d+ 页，共 \d+ 条/).first();
  const nextPage = pagination.getByRole("button", { name: "入库运行记录下一页" });
  for (let pageNumber = 0; pageNumber < 20; pageNumber += 1) {
    const row = page.getByRole("row").filter({ hasText: workflowId });
    if (await row.count()) return row.first();
    if (await nextPage.isDisabled()) break;
    const previousIndicator = await pageIndicator.textContent();
    await nextPage.click();
    await expect.poll(() => pageIndicator.textContent()).not.toBe(previousIndicator);
  }
  throw new Error(`入库运行记录未找到：${workflowId}`);
}

async function findSourceAssetRow(page: Page, fileName: string): Promise<Locator> {
  const pagination = page.getByRole("navigation", { name: "源对象分页" });
  const pageIndicator = pagination.getByText(/第 \d+ \/ \d+ 页，共 \d+ 个对象/).first();
  const nextPage = pagination.getByRole("button", { name: "源对象下一页" });
  for (let pageNumber = 0; pageNumber < 100; pageNumber += 1) {
    const row = page.getByRole("row").filter({ hasText: fileName });
    if (await row.count()) return row.first();
    if (await nextPage.isDisabled()) break;
    const previousIndicator = await pageIndicator.textContent();
    await nextPage.click();
    await expect.poll(() => pageIndicator.textContent()).not.toBe(previousIndicator);
  }
  throw new Error(`源对象未找到：${fileName}`);
}

async function verifyProfessionalRefreshLifecycle({
  page,
  endpoint,
  resultSurface,
}: {
  page: Page;
  endpoint: string;
  resultSurface: Locator;
}) {
  let releaseResponse: (() => void) | undefined;
  let markBackendReady: (() => void) | undefined;
  let markHandlerSettled: (() => void) | undefined;
  const responseRelease = new Promise<void>((resolve) => {
    releaseResponse = resolve;
  });
  const backendReady = new Promise<void>((resolve) => {
    markBackendReady = resolve;
  });
  const handlerSettled = new Promise<void>((resolve) => {
    markHandlerSettled = resolve;
  });
  let interceptedStatus = 0;
  const handler = async (route: Route) => {
    const request = route.request();
    if (request.method() !== "GET" || new URL(request.url()).pathname !== endpoint || interceptedStatus !== 0) {
      return route.continue();
    }
    let response: Awaited<ReturnType<Route["fetch"]>> | undefined;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        response = await route.fetch();
        break;
      } catch (caught) {
        const message = caught instanceof Error ? caught.message : String(caught);
        const retryable = /socket hang up|ECONNRESET|connection reset|aborted/i.test(message);
        if (!retryable || attempt === 1) throw caught;
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
    }
    if (!response) throw new Error(`${endpoint} route fetch produced no response`);
    interceptedStatus = response.status();
    markBackendReady?.();
    await responseRelease;
    try {
      await route.fulfill({ response });
    } catch (caught) {
      const failure = request.failure();
      if (!failure || !/abort|cancel/i.test(failure.errorText)) throw caught;
    } finally {
      markHandlerSettled?.();
    }
  };

  await expect(resultSurface).toBeVisible();
  await page.route("**/api/v1/**", handler);
  await page.getByRole("button", { name: "刷新当前结果", exact: true }).click();
  await backendReady;
  expect(interceptedStatus, `${endpoint} must return a real successful backend response before delay`).toBe(200);
  await expect(page.getByText(/^正在刷新/)).toBeVisible();
  await expect(resultSurface).toBeVisible();
  await page.getByRole("button", { name: "取消查询", exact: true }).click();
  await expect(page.getByText("刷新已取消", { exact: true })).toBeVisible();
  await expect(resultSurface).toBeVisible();
  releaseResponse?.();
  await handlerSettled;
  await page.unroute("**/api/v1/**", handler);

  const retryResponse = page.waitForResponse((response) => {
    const request = response.request();
    return request.method() === "GET" && new URL(response.url()).pathname === endpoint;
  });
  await page.getByRole("button", { name: "重新刷新", exact: true }).click();
  expect((await retryResponse).ok(), `${endpoint} retry must complete through the real API`).toBe(true);
  await expect(page.getByText("刷新已取消", { exact: true })).toHaveCount(0);
  await expect(resultSurface).toBeVisible();
}

async function verifyProfessionalErrorPermissionLifecycle({
  page,
  endpoint,
  resultSurface,
}: {
  page: Page;
  endpoint: string;
  resultSurface: Locator;
}) {
  const verifyFaultRecovery = async ({
    status,
    attempts,
    detail,
    heading,
    action,
    preserveResults,
  }: {
    status: 403 | 503;
    attempts: number;
    detail: string;
    heading: string;
    action: string;
    preserveResults: boolean;
  }) => {
    const upstreamStatuses: number[] = [];
    const faultHandler = async (route: Route) => {
      const request = route.request();
      if (
        request.method() !== "GET" ||
        new URL(request.url()).pathname !== endpoint ||
        upstreamStatuses.length >= attempts
      ) {
        return route.continue();
      }
      const response = await route.fetch();
      upstreamStatuses.push(response.status());
      await route.fulfill({
        status,
        json: { detail },
        headers: { "X-Request-ID": `browser-state-${status}-${upstreamStatuses.length}` },
      });
    };

    await page.route("**/api/v1/**", faultHandler);
    await page.getByRole("button", { name: "刷新当前结果", exact: true }).click();
    await expect(page.getByText(heading, { exact: true })).toBeVisible({ timeout: 15_000 });
    expect(upstreamStatuses, `${endpoint} fault injection must follow real successful API responses`).toEqual(
      Array.from({ length: attempts }, () => 200),
    );
    if (preserveResults) await expect(resultSurface).toBeVisible();
    else await expect(resultSurface).toBeHidden();
    await page.unroute("**/api/v1/**", faultHandler);

    const recoveryResponse = page.waitForResponse((response) => {
      const request = response.request();
      return request.method() === "GET" && new URL(response.url()).pathname === endpoint;
    });
    await page.getByRole("button", { name: action, exact: true }).click();
    expect((await recoveryResponse).ok(), `${endpoint} must recover through the real API after ${status}`).toBe(true);
    await expect(page.getByText(heading, { exact: true })).toHaveCount(0);
    await expect(resultSurface).toBeVisible();
  };

  await verifyFaultRecovery({
    status: 503,
    attempts: 3,
    detail: "专业数据服务暂不可用",
    heading: "最新结果刷新失败",
    action: "重新刷新",
    preserveResults: true,
  });
  await verifyFaultRecovery({
    status: 403,
    attempts: 1,
    detail: "当前数据授权不允许读取该结果集",
    heading: "当前账号无权读取这组结果",
    action: "重新校验权限",
    preserveResults: false,
  });
}

test("[public-login][external-login] renders the external research login entry without overflow", async ({ page }) => {
  await page.goto("/");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("research");
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "医药情报工作台" })).toBeVisible();
  await expect(page.getByLabel("X-Pharma", { exact: true })).toBeVisible();
  await expect(page.getByText("内部管理工作台", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("内部管理平台", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "进入工作台" })).toBeVisible();
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[internal-login] renders a distinct internal management entry", async ({ page }) => {
  await page.goto("/workspace/internal");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page.getByRole("heading", { name: "内部管理工作台" })).toBeVisible();
  await expect(page.getByLabel("内部管理平台", { exact: true })).toBeVisible();
  await expect(page.getByText("医药情报工作台", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("X-Pharma", { exact: true })).toHaveCount(0);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[workspace-navigation][workspace-isolation][research-workbench][internal-workbench][ingestion-replay][quarantine-governance][master-data-rollback][publication-governance][quality-operations][stable-deep-link][explorer-quick-detail-continuity][global-search-landscape][data-lifecycle][domain-export][result-pagination][result-to-comparison][cross-page-comparison][pipeline-intelligence][pipeline-cross-domain-signals][pipeline-cross-domain-navigation][pipeline-dense-results][pipeline-relationship-correctness][professional-patent-query][professional-deal-query][professional-regulatory-query][professional-epidemiology-query][professional-news-query][clinical-full-result-landscape][clinical-result-dense-fields][regulatory-intelligence][regulatory-result-correctness][regulatory-subscription][saved-search-maintenance][browser-quality][web-vitals-rum][initial-load-boundary][table-preference-server-continuity][query-cancellation][professional-query-state-matrix] authenticates and navigates both governed workbenches", async ({
  browser,
  page,
}, testInfo) => {
  testInfo.setTimeout(240_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const pipelineTargetId = process.env.E2E_PIPELINE_TARGET_ID;
  const pipelineCombinationTargetId = process.env.E2E_PIPELINE_COMBINATION_TARGET_ID;
  const pipelineDiseaseId = process.env.E2E_PIPELINE_DISEASE_ID;
  const trialProfileId = process.env.E2E_TRIAL_PROFILE_ID;
  const pipelineOrganizationId = process.env.E2E_PIPELINE_ORGANIZATION_ID;
  const pipelineCollaboratorId = process.env.E2E_PIPELINE_COLLABORATOR_ID;
  const regulatorySubjectId = process.env.E2E_REGULATORY_SUBJECT_ID;
  const regulatoryIndicationId = process.env.E2E_REGULATORY_INDICATION_ID;
  const regulatoryEventId = process.env.E2E_REGULATORY_EVENT_ID;
  const regulatoryNegativeEventId = process.env.E2E_REGULATORY_NEGATIVE_EVENT_ID;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  const epidemiologyPatientPopulationId = process.env.E2E_EPIDEMIOLOGY_PATIENT_POPULATION_ID;
  const epidemiologyObservationId = process.env.E2E_EPIDEMIOLOGY_OBSERVATION_ID;
  const patentFamilyId = process.env.E2E_PATENT_FAMILY_ID;
  const newsEventId = process.env.E2E_NEWS_EVENT_ID;
  const dealEntityId = process.env.E2E_DEAL_ENTITY_ID;
  const dealProfileId = process.env.E2E_DEAL_PROFILE_ID;
  const ingestionRunId =
    process.env[`E2E_INGESTION_RUN_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const quarantineVersionId =
    process.env[`E2E_QUARANTINE_VERSION_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const resolutionCaseId =
    process.env[`E2E_RESOLUTION_CASE_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const qualityIssueId =
    process.env[`E2E_QUALITY_ISSUE_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  const qualityOwnerId =
    process.env[`E2E_QUALITY_OWNER_ID_${testInfo.project.name.replaceAll("-", "_").toUpperCase()}`];
  test.skip(
    !credentials ||
      !fixtureKeyBase ||
      !pipelineTargetId ||
      !pipelineCombinationTargetId ||
      !pipelineDiseaseId ||
      !trialProfileId ||
      !pipelineOrganizationId ||
      !pipelineCollaboratorId ||
      !regulatorySubjectId ||
      !regulatoryIndicationId ||
      !regulatoryEventId ||
      !regulatoryNegativeEventId ||
      !epidemiologyDiseaseId ||
      !epidemiologyPatientPopulationId ||
      !epidemiologyObservationId ||
      !patentFamilyId ||
      !newsEventId ||
      !dealEntityId ||
      !dealProfileId ||
      !ingestionRunId ||
      !quarantineVersionId ||
      !resolutionCaseId ||
      !qualityIssueId ||
      !qualityOwnerId,
    "Authenticated browser fixture credentials and cross-domain entity IDs are required",
  );
  if (
    !credentials ||
    !fixtureKeyBase ||
    !pipelineTargetId ||
    !pipelineCombinationTargetId ||
    !pipelineDiseaseId ||
    !trialProfileId ||
    !pipelineOrganizationId ||
    !pipelineCollaboratorId ||
    !regulatorySubjectId ||
    !regulatoryIndicationId ||
    !regulatoryEventId ||
    !regulatoryNegativeEventId ||
    !epidemiologyDiseaseId ||
    !epidemiologyPatientPopulationId ||
    !epidemiologyObservationId ||
    !patentFamilyId ||
    !newsEventId ||
    !dealEntityId ||
    !dealProfileId ||
    !ingestionRunId ||
    !quarantineVersionId ||
    !resolutionCaseId ||
    !qualityIssueId ||
    !qualityOwnerId
  ) {
    return;
  }
  const fixtureKey = `${fixtureKeyBase}-${testInfo.project.name}`;
  const fixtureName = `Browser acceptance target ${fixtureKey}`;
  const rumBatches: WebVitalBatchCreate[] = [];
  const rumStatuses: number[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname !== "/api/v1/workspace/web-vitals" || request.method() !== "POST") return;
    const body = request.postData();
    if (!body) throw new Error("Web Vitals RUM request did not contain a body");
    rumBatches.push(JSON.parse(body) as WebVitalBatchCreate);
  });
  page.on("response", (response) => {
    if (new URL(response.url()).pathname === "/api/v1/workspace/web-vitals") {
      rumStatuses.push(response.status());
    }
  });

  await installBrowserQualityProbe(page);
  await page.goto("/");
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
  const researchNavigation = page.getByRole("navigation", { name: "主导航" });
  for (const internalView of ["数据工厂", "AI 审核", "商业运营", "企业管理"]) {
    await expect(researchNavigation.getByRole("button", { name: internalView, exact: true })).toHaveCount(0);
  }
  await openNavigation(page);
  const professionalLauncher = page.getByRole("navigation", { name: "主导航" });
  for (const domain of [
    "药物与管线",
    "临床试验",
    "专利情报",
    "交易与公司",
    "监管与安全",
    "流行病学",
    "新闻与会议",
    "结构检索",
  ]) {
    await expect(professionalLauncher.getByRole("button", { name: domain, exact: true })).toBeVisible();
  }
  await professionalLauncher.getByRole("button", { name: "专利情报", exact: true }).click();
  await expect(page).toHaveURL(/view=patents/);
  await expect(page.getByRole("heading", { name: "专利族与资产关联", level: 1 })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();

  // Reset navigation-scoped Web Vitals after authentication so LCP measures the workbench, not the login page.
  await page.goto("/workspace/research?view=overview");
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();
  await openNavigation(page);
  await page.getByRole("button", { name: "情报检索" }).click();
  await expect(page.getByRole("button", { name: "情报检索" })).toHaveAttribute("aria-current", "page");
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
  await expect(page).toHaveScreenshot("research-workbench.png", {
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

  const paginationQuery = `Browser pagination ${fixtureKeyBase}`;
  let releaseDelayedSearch: (() => void) | undefined;
  let markBackendResponseReady: (() => void) | undefined;
  let markDelayedHandlerSettled: (() => void) | undefined;
  const delayedSearch = new Promise<void>((resolve) => {
    releaseDelayedSearch = resolve;
  });
  const backendResponseReady = new Promise<void>((resolve) => {
    markBackendResponseReady = resolve;
  });
  const delayedHandlerSettled = new Promise<void>((resolve) => {
    markDelayedHandlerSettled = resolve;
  });
  let delayedSearchStatus = 0;
  const delayedSearchRoute = async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("q") !== paginationQuery || delayedSearchStatus !== 0) return route.continue();
    const response = await route.fetch();
    delayedSearchStatus = response.status();
    markBackendResponseReady?.();
    await delayedSearch;
    try {
      await route.fulfill({ response });
    } catch (caught) {
      const failure = route.request().failure();
      if (!failure || !/abort|cancel/i.test(failure.errorText)) throw caught;
    } finally {
      markDelayedHandlerSettled?.();
    }
  };
  await page.route("**/api/v1/entities?**", delayedSearchRoute);
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}`);
  await backendResponseReady;
  expect(delayedSearchStatus).toBe(200);
  await expect(page.getByText("正在检索结构化情报", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "取消查询" }).click();
  await expect(page.getByText("查询已取消", { exact: true })).toBeVisible();
  releaseDelayedSearch?.();
  await delayedHandlerSettled;
  await page.unroute("**/api/v1/entities?**", delayedSearchRoute);
  await page.getByRole("button", { name: "重新查询" }).click();
  await expect(page.getByRole("navigation", { name: "实体检索结果分页" }).getByText("共 205 条")).toBeVisible();
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/entities",
    resultSurface: page.getByRole("table", { name: "实体检索结果" }),
  });

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}`);
  const entityPagination = page.getByRole("navigation", { name: "实体检索结果分页" });
  await expect(entityPagination.getByText("第 1 / 3 页")).toBeVisible();
  await expect(entityPagination.getByText("共 205 条")).toBeVisible();
  const paginationJump = entityPagination.getByRole("form", { name: "跳转页码" });
  await paginationJump.getByLabel("目标页码").fill("4");
  await paginationJump.getByRole("button", { name: "跳转" }).click();
  await expect(entityPagination.getByRole("alert")).toContainText("请输入 1 到 3 之间的页码");
  await expect(page).not.toHaveURL(/offset=/);

  const thirdPageResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/v1/entities" && url.searchParams.get("offset") === "200";
  });
  await paginationJump.getByLabel("目标页码").fill("3");
  await paginationJump.getByRole("button", { name: "跳转" }).click();
  const thirdPageResponse = await thirdPageResponsePromise;
  expect(thirdPageResponse.ok()).toBe(true);
  const thirdPagePayload = (await thirdPageResponse.json()) as {
    items: Array<{ name: string }>;
    offset: number;
    total: number;
  };
  expect(thirdPagePayload).toMatchObject({ offset: 200, total: 205 });
  expect(thirdPagePayload.items).toHaveLength(5);
  await expect(page).toHaveURL(/offset=200/);
  await expect(entityPagination.getByText("第 3 / 3 页")).toBeVisible();
  await expect(entityPagination.getByRole("button", { name: "第 3 页" })).toHaveAttribute("aria-current", "page");
  await page.reload();
  await expect(entityPagination.getByLabel("目标页码")).toHaveValue("3");
  await expect(entityPagination.getByRole("button", { name: "末页" })).toBeDisabled();

  const normalizedPageResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/v1/entities" && url.searchParams.get("offset") === "200";
  });
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}&offset=999`);
  const normalizedPageResponse = await normalizedPageResponsePromise;
  expect(normalizedPageResponse.ok()).toBe(true);
  await expect(page).toHaveURL(/offset=200/);

  await expect(entityPagination.getByText("第 3 / 3 页")).toBeVisible();
  await expect(entityPagination.getByLabel("目标页码")).toHaveValue("3");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  // Dense-result performance budget: a fresh navigation into the 205-record fixture page
  // (init script resets navigation-scoped vitals) with a real sort interaction, so LCP,
  // INP and CLS are measured on the dense professional table, not only the empty state.
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(paginationQuery)}`);
  const denseTable = page.getByRole("table", { name: "实体检索结果" });
  await expect(denseTable).toBeVisible();
  await expect(page.getByRole("navigation", { name: "实体检索结果分页" }).getByText("共 205 条")).toBeVisible();
  await denseTable.locator("th").filter({ hasText: "名称" }).first().getByRole("button").click();
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["name:asc"]);
  await expect(denseTable.locator('th[aria-sort="ascending"]')).toContainText("名称");
  const denseQuality = await readBrowserQualityMetrics(page);
  testInfo.annotations.push({ type: "dense-results-quality-metrics", description: JSON.stringify(denseQuality) });
  expect(denseQuality.lcp_ms).toBeGreaterThan(0);
  expect(denseQuality.lcp_ms).toBeLessThanOrEqual(2_500);
  expect(denseQuality.interaction_count).toBeGreaterThan(0);
  expect(denseQuality.inp_ms).toBeLessThanOrEqual(200);
  expect(denseQuality.cls).toBeLessThanOrEqual(0.1);
  const denseTableShell = page.locator(".virtual-table-shell").filter({ has: denseTable });
  await expect(denseTableShell).toHaveCount(1);
  // Keep the pointer outside the viewport so row hover styling cannot make the
  // repository-owned visual baseline depend on the previous interaction target.
  await page.mouse.move(-10, -10);
  await expect(denseTableShell).toHaveScreenshot("research-dense-results.png", {
    animations: "disabled",
    caret: "hide",
    mask: [denseTableShell.locator(".entity-match-context")],
    maskColor: "#dce4e7",
    maxDiffPixelRatio: 0.001,
  });

  const csrfCookie = (await page.context().cookies()).find((cookie) => cookie.name === "pharma_csrf");
  if (!csrfCookie?.value) throw new Error("Authenticated session did not issue the CSRF cookie");
  const denseQuery = new URLSearchParams({
    q: paginationQuery,
    sort: "name:asc",
    limit: "100",
  });
  const firstDensePageResponse = await page.request.get(`/api/v1/entities?${denseQuery}`);
  expect(firstDensePageResponse.ok()).toBe(true);
  const firstDensePage = (await firstDensePageResponse.json()) as {
    items: Array<{ id: string; name: string }>;
  };
  denseQuery.set("offset", "200");
  const lastDensePageResponse = await page.request.get(`/api/v1/entities?${denseQuery}`);
  expect(lastDensePageResponse.ok()).toBe(true);
  const lastDensePage = (await lastDensePageResponse.json()) as {
    items: Array<{ id: string; name: string }>;
  };
  const firstDenseEntity = firstDensePage.items[0];
  const lastDenseEntity = lastDensePage.items[0];
  if (!firstDenseEntity || !lastDenseEntity) throw new Error("Dense pagination fixtures are incomplete");

  const crossPageComparisonName = `Browser cross-page list ${fixtureKey}`;
  const createCrossPageComparison = await page.request.post("/api/v1/comparison-sets", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: { name: crossPageComparisonName, visibility: "private" },
  });
  expect(createCrossPageComparison.status()).toBe(201);
  const crossPageComparison = (await createCrossPageComparison.json()) as { id: string };
  await page.getByRole("checkbox", { name: `选择对比 ${firstDenseEntity.name}` }).click();
  const densePagination = page.getByRole("navigation", { name: "实体检索结果分页" });
  await densePagination.getByRole("button", { name: "末页" }).click();
  await expect(page).toHaveURL(/offset=200/);
  await expect(page.getByText("已选 1/20 项", { exact: true })).toBeVisible();
  await page.getByRole("checkbox", { name: `选择对比 ${lastDenseEntity.name}` }).click();
  await expect(page.getByText("已选 2/20 项", { exact: true })).toBeVisible();
  const crossPageAddTrigger = page.getByRole("button", { name: "加入列表" });
  await crossPageAddTrigger.click();
  const crossPagePicker = page.getByRole("dialog", { name: "加入对比列表" });
  const crossPageSetSelect = crossPagePicker.getByLabel("目标列表");
  const crossPagePickerClose = crossPagePicker.getByRole("button", { name: "关闭" });
  const crossPagePickerSubmit = crossPagePicker.getByRole("button", { name: "确认加入" });
  await expect(crossPagePickerClose).toBeFocused();
  await expect(crossPageSetSelect).toBeVisible();
  await expect(crossPagePickerSubmit).toBeEnabled();
  await crossPagePickerClose.focus();
  await page.keyboard.press("Shift+Tab");
  await expect(crossPagePickerSubmit).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(crossPagePickerClose).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(crossPagePicker).toHaveCount(0);
  await expect(crossPageAddTrigger).toBeFocused();
  await crossPageAddTrigger.click();
  await expect(crossPageSetSelect).toBeVisible();
  await crossPageSetSelect.selectOption(crossPageComparison.id);
  const crossPageBatchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/comparison-sets/${crossPageComparison.id}/members/batch`) &&
      response.request().method() === "POST",
  );
  await crossPagePicker.getByRole("button", { name: "确认加入" }).click();
  const crossPageBatch = await crossPageBatchResponse;
  expect(crossPageBatch.status()).toBe(200);
  expect(crossPageBatch.request().postDataJSON()).toEqual({
    entity_ids: [firstDenseEntity.id, lastDenseEntity.id],
    expected_version: 1,
  });
  await expect(page.getByText(`2 个实体已加入 ${crossPageComparisonName}`, { exact: true })).toBeVisible();

  const createEntity = await page.request.post("/api/v1/entities", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: {
      entity_type: "target",
      name: fixtureName,
      description: "Isolated browser acceptance search projection",
      aliases: [`Acceptance ${fixtureKey}`],
      external_ids: { acceptance: fixtureKey },
      attributes: { organism: "Homo sapiens", acceptance_fixture: true, acceptance_fixture_key: fixtureKey },
    },
  });
  expect(createEntity.status()).toBe(201);
  const createdEntity = (await createEntity.json()) as { id: string };
  const companyName = `Browser acceptance company ${fixtureKey}`;
  const createCompany = await page.request.post("/api/v1/entities", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: {
      entity_type: "organization",
      name: companyName,
      description: "Isolated browser acceptance company dossier",
      external_ids: { acceptance: `${fixtureKey}-company` },
      attributes: { acceptance_fixture: true, acceptance_fixture_key: fixtureKey },
    },
  });
  expect(createCompany.status()).toBe(201);
  const createdCompany = (await createCompany.json()) as { id: string };

  await expect
    .poll(async () => {
      const response = await page.request.get(`/api/v1/entities?q=${encodeURIComponent(fixtureKey)}&limit=25`);
      if (!response.ok()) return null;
      const body = (await response.json()) as { engine: string; total: number };
      return { engine: body.engine, total: body.total };
    })
    .toEqual({ engine: "opensearch", total: 2 });

  await openNavigation(page);
  await page.getByRole("button", { name: "情报检索" }).click();
  await page.getByLabel("情报检索词").fill(fixtureKey);
  await page.getByRole("button", { name: "检索", exact: true }).click();
  await expect(page.locator("tbody").getByText(fixtureName, { exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "实体类型筛选" })).toBeVisible();
  await expect(page.getByRole("button", { name: "靶点 1" })).toBeVisible();
  await page.getByRole("button", { name: /对象类型：靶点/ }).click();
  await expect(page).toHaveURL(/type=target/);
  await page.getByRole("button", { name: /对象类型：研发机构/ }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("types")).toBe("target,organization");
  await expect(page.locator("tbody").getByText(fixtureName, { exact: true })).toBeVisible();
  await expect(page.locator("tbody").getByText(companyName, { exact: true })).toBeVisible();
  await expect(page.getByText(`外部标识精确命中：acceptance · ${fixtureKey}`, { exact: true })).toBeVisible();
  await expect(page.getByText(`规范名称部分命中：${companyName}`, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "统计", exact: true }).click();
  await expect(page).toHaveURL(/display=landscape/);
  const entityLandscape = page.getByRole("region", { name: "实体检索统计分析" });
  await expect(entityLandscape).toContainText("完整命中集");
  await entityLandscape.getByRole("button", { name: "列表", exact: true }).click();
  const entityTypeStats = entityLandscape.getByRole("table", { name: "实体类型统计表" });
  await expect(entityTypeStats).toContainText("靶点");
  await expect(entityTypeStats).toContainText("机构");
  const savedLandscapeName = `Browser entity statistics ${fixtureKey}`;
  await page.getByRole("button", { name: "保存检索" }).click();
  const savedLandscapeDialog = page.getByRole("dialog", { name: "保存当前检索" });
  await savedLandscapeDialog.getByLabel("名称").fill(savedLandscapeName);
  await savedLandscapeDialog.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("基础查询检索已保存并启用监控", { exact: true })).toBeVisible();
  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  await expect(page).toHaveURL(/monitor_tab=searches/);
  await page.reload();
  await expect(page.getByRole("tab", { name: "已保存检索" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).toHaveURL(/view=monitoring/);
  await expect(page.getByRole("tab", { name: "提醒中心" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedLandscapeRow = page.getByRole("row").filter({ hasText: savedLandscapeName });
  await expect(savedLandscapeRow).toBeVisible();
  await expect(savedLandscapeRow).toContainText("基础查询 · 靶点、机构");
  await expect(savedLandscapeRow).toContainText("统计表");
  await savedLandscapeRow.getByRole("button", { name: `运行 ${savedLandscapeName}` }).click();
  await expect(page).toHaveURL(/display=landscape/);
  await expect(page).toHaveURL(/analysis_view=table/);
  const replayedEntityLandscape = page.getByRole("region", { name: "实体检索统计分析" });
  await expect(replayedEntityLandscape).toBeVisible();
  await replayedEntityLandscape
    .getByRole("table", { name: "实体类型统计表" })
    .locator("tbody tr")
    .filter({ hasText: "靶点" })
    .getByRole("button", { name: "筛选" })
    .click();
  await expect(page).toHaveURL(/type=target/);
  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKey)}&types=target%2Corganization`);
  await page.reload();
  await expect(page.getByRole("button", { name: /对象类型：靶点/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("button", { name: /对象类型：研发机构/ })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("tbody").getByText(fixtureName, { exact: true })).toBeVisible();
  await expect(page.locator("tbody").getByText(companyName, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "紧凑" }).click();
  await expect(page.getByRole("button", { name: "紧凑" })).toHaveAttribute("aria-pressed", "true");
  await page.getByText("列", { exact: true }).click();
  await page.getByRole("button", { name: "上移列：类型" }).click();
  const configuredEntityTable = page.getByRole("table", { name: "实体检索结果" });
  expect(
    (await configuredEntityTable.getByRole("columnheader").allTextContents())
      .map((label) => label.trim())
      .filter(Boolean)
      .slice(0, 2),
  ).toEqual(["类型", "名称"]);
  await page.getByRole("checkbox", { name: "显示列：外部标识" }).click();
  await expect(
    page.getByRole("table", { name: "实体检索结果" }).getByRole("columnheader", { name: "外部标识" }),
  ).toHaveCount(0);
  await expect
    .poll(async () => {
      const response = await page.request.get("/api/v1/workspace/table-preferences/entity-search");
      if (!response.ok()) return null;
      const preference = (await response.json()) as {
        column_order: string[];
        column_visibility: Record<string, boolean>;
        density: string;
        persisted: boolean;
        version: number;
      };
      return {
        columnOrder: preference.column_order.slice(0, 2),
        density: preference.density,
        externalIdsVisible: preference.column_visibility.external_ids,
        persisted: preference.persisted,
        versioned: preference.version > 0,
      };
    })
    .toEqual({
      columnOrder: ["entity_type", "name"],
      density: "compact",
      externalIdsVisible: false,
      persisted: true,
      versioned: true,
    });
  await page.evaluate(() => window.localStorage.clear());
  if (testInfo.project.name === "desktop-1440") {
    const baseURL = testInfo.project.use.baseURL;
    if (typeof baseURL !== "string") throw new Error("Desktop browser project must define a base URL");
    const secondContext = await browser.newContext({ baseURL, viewport: { width: 1440, height: 900 } });
    try {
      const secondPage = await secondContext.newPage();
      await secondPage.goto(
        `/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKey)}&types=target%2Corganization`,
      );
      await secondPage.getByLabel("工作邮箱").fill(credentials.email);
      await secondPage.getByLabel("密码").fill(credentials.password);
      await secondPage.getByRole("button", { name: "进入工作台" }).click();
      await expect(secondPage.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
      await expect(secondPage.getByRole("button", { name: "紧凑" })).toHaveAttribute("aria-pressed", "true");
      const secondTable = secondPage.getByRole("table", { name: "实体检索结果" });
      expect(
        (await secondTable.getByRole("columnheader").allTextContents())
          .map((label) => label.trim())
          .filter(Boolean)
          .slice(0, 2),
      ).toEqual(["类型", "名称"]);
      await expect(secondTable.getByRole("columnheader", { name: "外部标识" })).toHaveCount(0);
    } finally {
      await secondContext.close();
    }
  }
  await expect(page.getByRole("button", { name: fixtureName, exact: true })).toBeVisible();
  await page.getByRole("button", { name: fixtureName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`view=explorer.*entity=${createdEntity.id}`));
  await expect(page.getByRole("dialog", { name: fixtureName })).toBeVisible();
  await expect(page.getByRole("button", { name: "关闭实体详情" })).toBeFocused();
  await page.reload();
  await expect(page.getByRole("dialog", { name: fixtureName })).toBeVisible();
  await page.getByRole("button", { name: "关闭实体详情" }).click();
  await expect(page).not.toHaveURL(/entity=/);
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=explorer.*entity=${createdEntity.id}`));
  await expect(page.getByRole("dialog", { name: fixtureName })).toBeVisible();
  await page.getByRole("button", { name: "打开靶点全景" }).click();
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${createdEntity.id}`));
  await expect(page.getByRole("heading", { name: fixtureName, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: fixtureName, exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await expect(page.getByLabel("情报检索词")).toHaveValue(fixtureKey);
  await expect(page.getByRole("dialog", { name: fixtureName })).toBeVisible();
  await page.getByRole("button", { name: "关闭实体详情" }).click();
  await expect(page.getByRole("dialog", { name: fixtureName })).toHaveCount(0);
  await expect(page).not.toHaveURL(/entity=/);
  const restoredEntityTable = page.getByRole("table", { name: "实体检索结果" });
  await expect(page.getByRole("button", { name: "紧凑" })).toHaveAttribute("aria-pressed", "true");
  expect(
    (await restoredEntityTable.getByRole("columnheader").allTextContents())
      .map((label) => label.trim())
      .filter(Boolean)
      .slice(0, 2),
  ).toEqual(["类型", "名称"]);
  await expect(restoredEntityTable.getByRole("columnheader", { name: "外部标识" })).toHaveCount(0);
  const entityNameHeader = restoredEntityTable.getByRole("columnheader", { name: /名称/ });
  await entityNameHeader.getByRole("button").click();
  await expect(page.getByText(/全部结果按名称升序/)).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["name:asc"]);
  await page.reload();
  await expect(page.getByRole("button", { name: "紧凑" })).toHaveAttribute("aria-pressed", "true");
  await expect(restoredEntityTable.getByRole("columnheader", { name: /名称/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
  await expect(restoredEntityTable.getByRole("columnheader", { name: "外部标识" })).toHaveCount(0);
  await page.getByRole("button", { name: "恢复表格默认视图" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual([]);
  await expect(page.getByText(/全部结果按相关性降序/)).toBeVisible();
  await expect(page.getByRole("button", { name: "标准" })).toHaveAttribute("aria-pressed", "true");
  await expect(restoredEntityTable.getByRole("columnheader", { name: "外部标识" })).toBeVisible();
  expect(
    (await restoredEntityTable.getByRole("columnheader").allTextContents())
      .map((label) => label.trim())
      .filter(Boolean)
      .slice(0, 2),
  ).toEqual(["名称", "类型"]);
  const domainExport = page.locator("details.domain-export-menu");
  await expect(domainExport).toBeVisible();
  await domainExport.locator("summary").click();
  await expect(domainExport.getByRole("checkbox", { name: "稳定 ID" })).toBeDisabled();
  await expect(domainExport.getByRole("checkbox", { name: "名称" })).toBeChecked();
  const exportResponsePromise = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/workspace/domain-exports") && response.request().method() === "POST",
  );
  const domainDownloadPromise = page.waitForEvent("download");
  await domainExport.getByRole("button", { name: "下载" }).click();
  const [exportResponse, domainDownload] = await Promise.all([exportResponsePromise, domainDownloadPromise]);
  expect(exportResponse.status()).toBe(200);
  expect(exportResponse.headers()["x-export-event-id"]).toMatch(/^[0-9a-f-]{36}$/);
  expect(exportResponse.request().postDataJSON()).toMatchObject({
    dataset: "entities",
    query: { q: fixtureKey, entity_types: ["target", "organization"] },
    export_format: "json",
    max_records: 2,
  });
  expect(domainDownload.suggestedFilename()).toBe("entities-query.json");
  const downloadedPath = await domainDownload.path();
  if (!downloadedPath) throw new Error("Google Chrome did not persist the governed domain export");
  const exportedDocument = JSON.parse(await readFile(downloadedPath, "utf8")) as {
    schema: string;
    dataset: string;
    query: Record<string, string | string[]>;
    records: Array<Record<string, unknown>>;
  };
  expect(exportedDocument.schema).toBe("pharma.workspace-domain-export.v1");
  expect(exportedDocument.dataset).toBe("entities");
  expect(exportedDocument.query).toEqual({ q: fixtureKey, entity_types: ["target", "organization"] });
  expect(exportedDocument.records).toHaveLength(2);
  expect(exportedDocument.records.map((record) => record.name)).toEqual(
    expect.arrayContaining([fixtureName, companyName]),
  );
  const comparisonName = `Browser result list ${fixtureKey}`;
  const createComparison = await page.request.post("/api/v1/comparison-sets", {
    headers: { "X-CSRF-Token": csrfCookie.value },
    data: { name: comparisonName, visibility: "private" },
  });
  expect(createComparison.status()).toBe(201);
  const comparison = (await createComparison.json()) as { id: string; version: number };
  await page.getByRole("checkbox", { name: `选择对比 ${fixtureName}` }).click();
  await page.getByRole("checkbox", { name: `选择对比 ${companyName}` }).click();
  await expect(page.getByText("已选 2/20 项", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "加入列表" }).click();
  const comparisonPicker = page.getByRole("dialog", { name: "加入对比列表" });
  await expect(comparisonPicker.getByLabel("目标列表")).toHaveValue(comparison.id);
  await expect(comparisonPicker.getByText("完成后共 2/20 个实体", { exact: true })).toBeVisible();
  const comparisonBatchResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/comparison-sets/${comparison.id}/members/batch`) &&
      response.request().method() === "POST",
  );
  await comparisonPicker.getByRole("button", { name: "确认加入" }).click();
  const batchResponse = await comparisonBatchResponse;
  expect(batchResponse.status()).toBe(200);
  expect(batchResponse.request().postDataJSON()).toEqual({
    entity_ids: [createdEntity.id, createdCompany.id],
    expected_version: 1,
  });
  await expect(page.getByText(`2 个实体已加入 ${comparisonName}`, { exact: true })).toBeVisible();
  await page.goto("/workspace/research?view=collections");
  const comparisonTable = page.locator(".comparison-table");
  await expect(comparisonTable.getByText(fixtureName, { exact: true })).toBeVisible();
  await expect(comparisonTable.getByText(companyName, { exact: true })).toBeVisible();
  await expect.poll(() => new URL(page.url()).searchParams.get("collection")).toBe(comparison.id);
  await page.getByRole("checkbox", { name: `纳入情报对比：${fixtureName}` }).check();
  await page.getByRole("checkbox", { name: `纳入情报对比：${companyName}` }).check();
  await expect
    .poll(() => new URL(page.url()).searchParams.get("compare"))
    .toBe(`${createdEntity.id},${createdCompany.id}`);
  const dossierMatrix = page.getByRole("table", { name: "实体情报对比矩阵" });
  await expect(dossierMatrix).toBeVisible();
  await expect(dossierMatrix.getByRole("columnheader", { name: new RegExp(fixtureName) })).toBeVisible();
  await expect(dossierMatrix.getByRole("columnheader", { name: new RegExp(companyName) })).toBeVisible();
  await expect(dossierMatrix.getByRole("rowheader", { name: "数据时点" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("checkbox", { name: `纳入情报对比：${fixtureName}` })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: `纳入情报对比：${companyName}` })).toBeChecked();
  await expect(dossierMatrix).toBeVisible();
  await dossierMatrix.getByRole("button", { name: `打开 ${fixtureName} 专业档案` }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("entity")).toBe(createdEntity.id);
  await page.goBack();
  await expect(dossierMatrix).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.goBack();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  const professionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await expect(professionalQuery).toContainText("已选 1 项");
  const modalityFacet = professionalQuery.getByRole("group", { name: "药物模态" });
  await modalityFacet.getByLabel("药物模态：全部").click();
  await modalityFacet.getByRole("checkbox", { name: /antibody/ }).check();
  await modalityFacet.getByRole("checkbox", { name: /small molecule/ }).check();
  const innovationTypeFacet = professionalQuery.getByRole("group", { name: "创新类型" });
  await innovationTypeFacet.getByLabel("创新类型：全部").click();
  await innovationTypeFacet.getByRole("checkbox", { name: /First-in-class/ }).check();
  const therapeuticAreaFacet = professionalQuery.getByRole("group", { name: "治疗领域" });
  await therapeuticAreaFacet.getByLabel("治疗领域：全部").click();
  await therapeuticAreaFacet.getByRole("checkbox", { name: /Oncology/ }).check();
  const drugCategoryFacet = professionalQuery.getByRole("group", { name: "药品类别" });
  await drugCategoryFacet.getByLabel("药品类别：全部").click();
  await drugCategoryFacet.getByRole("checkbox", { name: /Small molecule/ }).check();
  await professionalQuery.getByLabel("项目状态").selectOption("active");
  await professionalQuery.getByLabel("记录地区").selectOption("US");
  await professionalQuery.getByText("更多管线条件", { exact: true }).click();
  await professionalQuery.getByLabel("全球最高阶段").selectOption("phase_2");
  await professionalQuery.getByLabel("中国最高阶段").selectOption("phase_1");
  await professionalQuery.getByLabel("研发权益地区").selectOption("Global");
  await professionalQuery.getByLabel("商业化权益地区").selectOption("Greater China");
  await professionalQuery.getByLabel("机构角色").selectOption("originator");
  await professionalQuery.getByLabel("机构类型").selectOption("biopharma");
  await professionalQuery.getByLabel("机构所在地区").selectOption("CN");
  const programTagFacet = professionalQuery.getByRole("group", { name: "项目标签" });
  await programTagFacet.getByLabel("项目标签：全部").click();
  await programTagFacet.getByRole("checkbox", { name: /first_in_class/ }).check();
  await programTagFacet.getByRole("checkbox", { name: /best_in_class/ }).check();
  await professionalQuery.getByLabel("里程碑类型").selectOption("first_patient_in");
  await professionalQuery.getByLabel("全球阶段开始日期时间范围").selectOption("custom");
  const globalPhaseRange = professionalQuery.getByRole("group", { name: "全球阶段开始日期" });
  await globalPhaseRange.getByLabel("起").fill("2026-01-01");
  await globalPhaseRange.getByLabel("止").fill("2026-06-30");
  await professionalQuery.getByLabel("里程碑日期时间范围").selectOption("custom");
  const professionalMilestoneRange = professionalQuery.getByRole("group", { name: "里程碑日期" });
  await professionalMilestoneRange.getByLabel("起").fill("2026-05-01");
  await professionalMilestoneRange.getByLabel("止").fill("2026-06-30");
  await professionalQuery.getByText("临床结果与交易信号", { exact: true }).click();
  await professionalQuery.getByLabel("是否已有临床结果").selectOption("true");
  await professionalQuery.getByLabel("临床结果评价").selectOption("positive");
  await professionalQuery.getByLabel("是否存在交易记录").selectOption("true");
  await professionalQuery.getByLabel("交易币种").selectOption("USD");
  await professionalQuery.getByLabel("潜在总额下限").fill("100000000");
  await professionalQuery.getByLabel("潜在总额上限").fill("500000000");
  const advancedPipelineResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/pipelines" &&
      url.searchParams.get("geography") === "US" &&
      url.searchParams.get("global_phase") === "phase_2" &&
      url.searchParams.get("china_phase") === "phase_1" &&
      url.searchParams.get("development_rights_region") === "Global" &&
      url.searchParams.get("commercialization_rights_region") === "Greater China" &&
      url.searchParams.getAll("modality").includes("antibody") &&
      url.searchParams.getAll("modality").includes("small molecule") &&
      url.searchParams.getAll("innovation_type").includes("First-in-class") &&
      url.searchParams.getAll("therapeutic_area").includes("Oncology") &&
      url.searchParams.getAll("drug_category").includes("Small molecule") &&
      url.searchParams.get("program_status") === "active" &&
      url.searchParams.get("organization_role") === "originator" &&
      url.searchParams.get("organization_type") === "biopharma" &&
      url.searchParams.get("organization_country_region") === "CN" &&
      url.searchParams.get("has_clinical_results") === "true" &&
      url.searchParams.get("clinical_result_evaluation") === "positive" &&
      url.searchParams.get("has_deal") === "true" &&
      url.searchParams.get("deal_currency") === "USD" &&
      url.searchParams.get("deal_total_potential_amount_min") === "100000000" &&
      url.searchParams.get("deal_total_potential_amount_max") === "500000000" &&
      url.searchParams.getAll("program_tag").includes("first_in_class") &&
      url.searchParams.getAll("program_tag").includes("best_in_class") &&
      url.searchParams.get("milestone_type") === "first_patient_in"
    );
  });
  await professionalQuery.getByRole("button", { name: "查询 药物与管线" }).click();
  expect((await advancedPipelineResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/global_phase=phase_2/);
  await expect(page).toHaveURL(/china_phase=phase_1/);
  await expect(page).toHaveURL(/geography=US/);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("modality")).toEqual(["antibody", "small molecule"]);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("innovation_type")).toEqual(["First-in-class"]);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("therapeutic_area")).toEqual(["Oncology"]);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("drug_category")).toEqual(["Small molecule"]);
  await expect(page).toHaveURL(/program_status=active/);
  await expect(page).toHaveURL(/organization_role=originator/);
  await expect(page).toHaveURL(/organization_type=biopharma/);
  await expect(page).toHaveURL(/organization_country_region=CN/);
  await expect(page).toHaveURL(/has_clinical_results=true/);
  await expect(page).toHaveURL(/clinical_result_evaluation=positive/);
  await expect(page).toHaveURL(/has_deal=true/);
  await expect(page).toHaveURL(/deal_currency=USD/);
  await expect(page).toHaveURL(/deal_total_potential_amount_min=100000000/);
  await expect(page).toHaveURL(/deal_total_potential_amount_max=500000000/);
  await expect
    .poll(() => new URL(page.url()).searchParams.getAll("program_tag"))
    .toEqual(["first_in_class", "best_in_class"]);
  await expect(page).toHaveURL(/development_rights_region=Global/);
  await expect(page).toHaveURL(/commercialization_rights_region=Greater\+China/);
  await expect(page).toHaveURL(/global_phase_started_from=2026-01-01/);
  await expect(page).toHaveURL(/milestone_from=2026-05-01/);
  await page.goBack();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await professionalQuery.getByRole("button", { name: "临床试验", exact: true }).click();
  await professionalQuery.getByLabel("注册平台").selectOption("ClinicalTrials.gov");
  await professionalQuery.getByLabel("招募状态").selectOption("RECRUITING");
  await professionalQuery.getByLabel("临床分期").selectOption("PHASE2");
  await professionalQuery.getByLabel("结果发布", { exact: true }).selectOption("true");
  await professionalQuery.getByLabel("结果发布日期时间范围").selectOption("last_6_months");
  await professionalQuery.getByText("试验属性与结果评价", { exact: true }).click();
  await professionalQuery.getByLabel("试验简称").fill(`BRIDGE-${fixtureKeyBase}`);
  await professionalQuery.getByLabel("发起类型").selectOption("ist");
  await professionalQuery.getByLabel("治疗线次").selectOption("first_line");
  await professionalQuery.getByLabel("结果最优评价").selectOption("positive");
  await professionalQuery.getByText("关键结果与发表证据", { exact: true }).click();
  await professionalQuery.getByLabel("关键结果").selectOption("true");
  await professionalQuery.getByLabel("发表编号").fill("PMID:12345678");
  await professionalQuery.getByLabel("会议").fill("ASCO 2026");
  await professionalQuery.getByLabel("结果披露日期时间范围").selectOption("last_month");
  const trialPresetText = await professionalQuery
    .getByRole("group", { name: "结果发布日期" })
    .locator("output")
    .textContent();
  const trialPresetMatch = trialPresetText?.match(/(\d{4}-\d{2}-\d{2})\s+至\s+(\d{4}-\d{2}-\d{2})/);
  expect(trialPresetMatch).not.toBeNull();
  if (!trialPresetMatch) throw new Error("The visible trial date preset did not expose an explicit range");
  const trialPresetRange = { from: trialPresetMatch[1], to: trialPresetMatch[2] };
  const trialDisclosureText = await professionalQuery
    .getByRole("group", { name: "结果披露日期" })
    .locator("output")
    .textContent();
  const trialDisclosureMatch = trialDisclosureText?.match(/(\d{4}-\d{2}-\d{2})\s+至\s+(\d{4}-\d{2}-\d{2})/);
  expect(trialDisclosureMatch).not.toBeNull();
  if (!trialDisclosureMatch) throw new Error("The visible disclosure date preset did not expose an explicit range");
  const trialDisclosureRange = { from: trialDisclosureMatch[1], to: trialDisclosureMatch[2] };
  const presetTrialResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      url.searchParams.get("acronym") === `BRIDGE-${fixtureKeyBase}` &&
      url.searchParams.get("initiation_type") === "ist" &&
      url.searchParams.get("therapy_line") === "first_line" &&
      url.searchParams.get("result_evaluation") === "positive" &&
      url.searchParams.get("has_key_result") === "true" &&
      url.searchParams.get("publication_id") === "PMID:12345678" &&
      url.searchParams.get("conference") === "ASCO 2026" &&
      url.searchParams.get("disclosed_from") === `${trialDisclosureRange.from}T00:00:00.000Z` &&
      url.searchParams.get("disclosed_to") === `${trialDisclosureRange.to}T23:59:59.999Z` &&
      url.searchParams.get("results_posted_from") === `${trialPresetRange.from}T00:00:00.000Z` &&
      url.searchParams.get("results_posted_to") === `${trialPresetRange.to}T23:59:59.999Z`
    );
  });
  await professionalQuery.getByRole("button", { name: "查询 临床试验" }).click();
  expect((await presetTrialResponse).ok()).toBe(true);
  await expect(page).toHaveURL(new RegExp(`view=trials&q=${encodeURIComponent(fixtureKey)}`));
  await expect(page).toHaveURL(/registry=ClinicalTrials.gov/);
  await expect(page).toHaveURL(/status=RECRUITING/);
  await expect(page).toHaveURL(/phase=PHASE2/);
  await expect(page).toHaveURL(/has_results=true/);
  await expect(page).toHaveURL(new RegExp(`acronym=BRIDGE-${fixtureKeyBase}`));
  await expect(page).toHaveURL(/initiation_type=ist/);
  await expect(page).toHaveURL(/therapy_line=first_line/);
  await expect(page).toHaveURL(/result_evaluation=positive/);
  await expect(page).toHaveURL(/has_key_result=true/);
  await expect(page).toHaveURL(/publication_id=PMID%3A12345678/);
  await expect(page).toHaveURL(/conference=ASCO\+2026/);
  await expect(page).toHaveURL(new RegExp(`disclosed_from=${trialDisclosureRange.from}`));
  await expect(page).toHaveURL(new RegExp(`disclosed_to=${trialDisclosureRange.to}`));
  await expect(page).toHaveURL(new RegExp(`results_posted_from=${trialPresetRange.from}`));
  await expect(page).toHaveURL(new RegExp(`results_posted_to=${trialPresetRange.to}`));
  const trialFilters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(trialFilters.getByLabel("关键词")).toHaveValue(fixtureKey);
  await expect(trialFilters.getByLabel("注册平台")).toHaveValue("ClinicalTrials.gov");
  await expect(trialFilters.getByLabel("招募状态")).toHaveValue("RECRUITING");
  await expect(trialFilters.getByLabel("临床分期")).toHaveValue("PHASE2");
  await expect(trialFilters.getByLabel("结果发布", { exact: true })).toHaveValue("true");
  await expect(trialFilters.getByLabel("关键结果")).toHaveValue("true");
  await expect(trialFilters.getByLabel("发表编号")).toHaveValue("PMID:12345678");
  await expect(trialFilters.getByLabel("会议")).toHaveValue("ASCO 2026");
  await expect(trialFilters.getByLabel("披露日期起")).toHaveValue(trialDisclosureRange.from);
  await expect(trialFilters.getByLabel("披露日期止")).toHaveValue(trialDisclosureRange.to);
  const trialKeyword = fixtureKeyBase;
  await trialFilters.getByLabel("关键词").fill(trialKeyword);
  await trialFilters.getByRole("button", { name: "查询" }).click();
  await expect(page).toHaveURL(new RegExp(`view=trials&q=${encodeURIComponent(trialKeyword)}`));
  const trialTitle = `Browser clinical trial ${trialKeyword}`;
  const trialRegistryId = `NCT-E2E-${trialKeyword}`;
  const trialResults = page.getByRole("table", { name: "临床试验结果" });
  await expect(trialResults).toContainText(trialTitle);
  await expect(trialResults).toContainText(`BRIDGE-${trialKeyword}`);
  await expect(trialResults).toContainText("IST（申办方发起）");
  await expect(trialResults).toContainText("一线治疗");
  await expect(trialResults).toContainText("Objective response rate: 42 %");
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/trials",
    resultSurface: trialResults,
  });
  await trialResults.getByRole("button", { name: `${trialRegistryId} ${trialTitle}`, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`trial=${trialProfileId}`));
  await expect(page.getByRole("heading", { name: trialTitle })).toBeVisible();
  await expect(page.getByText("临床试验专业档案", { exact: false })).toBeVisible();
  await expect(page.getByText("128", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(`BRIDGE-${trialKeyword}`, { exact: true }).first()).toBeVisible();

  await page.getByRole("tab", { name: "设计与入组" }).click();
  await expect(page).toHaveURL(new RegExp(`trial=${trialProfileId}.*section=design`));
  await expect(page.getByText("Controlled single-arm phase 2 cohort")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("tab", { name: "设计与入组" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Adults with confirmed browser disease")).toBeVisible();

  await page.getByRole("tab", { name: "终点与结果" }).click();
  await expect(page).toHaveURL(new RegExp(`trial=${trialProfileId}.*section=outcomes`));
  await expect(page.getByText("Objective response rate")).toBeVisible();
  await expect(page.getByText(/p=0\.01/)).toBeVisible();
  const trialOutcomesVisual = page.locator(".trial-professional-body");
  await expect(trialOutcomesVisual).toHaveCount(1);
  await expect(trialOutcomesVisual).toHaveScreenshot("research-trial-outcomes.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.001,
  });
  await page.getByRole("tab", { name: "时间线与中心" }).click();
  await expect(page.getByText("Shanghai Oncology Center")).toBeVisible();
  await expect(page.getByText("First site opened")).toBeVisible();

  await page.getByRole("button", { name: "返回试验列表" }).click();
  await expect(page).not.toHaveURL(/trial=/);
  await expect(trialFilters.getByLabel("关键词")).toHaveValue(trialKeyword);
  await expect(trialFilters.getByLabel("注册平台")).toHaveValue("ClinicalTrials.gov");
  await expect(trialFilters.getByLabel("临床分期")).toHaveValue("PHASE2");
  const trialDisplay = page.getByRole("group", { name: "临床结果展示方式" });
  await trialDisplay.getByRole("button", { name: "可视化" }).click();
  await expect(page).toHaveURL(/display=landscape/);
  const trialLandscape = page.getByLabel("临床结果可视化");
  await expect(trialLandscape).toContainText("完整命中集");
  await expect(trialLandscape.getByRole("img", { name: "试验数量完整命中集分布" })).toBeVisible();
  const trialCountSection = trialLandscape.getByRole("heading", { name: "试验数量" }).locator("..").locator("..");
  await trialCountSection.getByRole("button", { name: "列表" }).click();
  await expect(trialLandscape.getByRole("table", { name: "试验数量统计表" })).toBeVisible();
  await expect(trialLandscape.getByRole("heading", { name: "总体评价" })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/display=landscape/);
  await expect(page.getByLabel("临床结果可视化")).toBeVisible();
  await trialDisplay.getByRole("button", { name: "列表" }).click();
  await expect(page).not.toHaveURL(/display=landscape/);
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(trialTitle);
  await trialFilters.getByLabel("结果最优评价").selectOption("positive");
  await trialFilters.getByLabel("试验简称").fill(`BRIDGE-${trialKeyword}`);
  await trialFilters.getByLabel("发起类型").selectOption("ist");
  await trialFilters.getByLabel("治疗线次").selectOption("first_line");
  await trialFilters.getByLabel("结果发布日期起").fill("2026-01-01");
  await trialFilters.getByLabel("结果发布日期止").fill("2026-07-31");
  await trialFilters.getByLabel("关键结果").selectOption("true");
  await trialFilters.getByLabel("发表编号").fill("PMID:12345678");
  await trialFilters.getByLabel("会议").fill("ASCO 2026");
  await trialFilters.getByLabel("披露日期起").fill("2026-06-01");
  await trialFilters.getByLabel("披露日期止").fill("2026-07-31");
  await trialFilters.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL(/results_posted_from=2026-01-01/);
  await expect(page).toHaveURL(/results_posted_to=2026-07-31/);
  await expect(page).toHaveURL(/result_evaluation=positive/);
  await expect(page).toHaveURL(new RegExp(`acronym=BRIDGE-${trialKeyword}`));
  await expect(page).toHaveURL(/initiation_type=ist/);
  await expect(page).toHaveURL(/therapy_line=first_line/);
  await expect(page).toHaveURL(/has_key_result=true/);
  await expect(page).toHaveURL(/publication_id=PMID%3A12345678/);
  await expect(page).toHaveURL(/conference=ASCO/);
  await expect(page).toHaveURL(/disclosed_from=2026-06-01/);
  await expect(page).toHaveURL(/disclosed_to=2026-07-31/);
  const appliedTrialFilters = page.getByRole("region", { name: "已应用查询条件" });
  await expect(appliedTrialFilters).toContainText("2026-01-01");
  await expect(appliedTrialFilters).toContainText("2026-07-31");
  await expect(appliedTrialFilters).toContainText("积极");
  await expect(appliedTrialFilters).toContainText(`BRIDGE-${trialKeyword}`);
  await expect(appliedTrialFilters).toContainText("IST（申办方发起）");
  await expect(appliedTrialFilters).toContainText("一线治疗");
  await expect(appliedTrialFilters).toContainText("PMID:12345678");
  await page.reload();
  await expect(trialFilters.getByLabel("结果发布日期起")).toHaveValue("2026-01-01");
  await expect(trialFilters.getByLabel("结果发布日期止")).toHaveValue("2026-07-31");
  await expect(trialFilters.getByLabel("结果最优评价")).toHaveValue("positive");
  await expect(trialFilters.getByLabel("试验简称")).toHaveValue(`BRIDGE-${trialKeyword}`);
  await expect(trialFilters.getByLabel("发起类型")).toHaveValue("ist");
  await expect(trialFilters.getByLabel("治疗线次")).toHaveValue("first_line");
  await expect(trialFilters.getByLabel("关键结果")).toHaveValue("true");
  await expect(trialFilters.getByLabel("发表编号")).toHaveValue("PMID:12345678");
  await expect(trialFilters.getByLabel("会议")).toHaveValue("ASCO 2026");
  await expect(trialFilters.getByLabel("披露日期起")).toHaveValue("2026-06-01");
  await expect(trialFilters.getByLabel("披露日期止")).toHaveValue("2026-07-31");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const patentProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await patentProfessionalQuery.getByRole("button", { name: "专利情报", exact: true }).click();
  await expect(patentProfessionalQuery.getByLabel("法律状态")).toContainText("有效");
  await expect(patentProfessionalQuery.getByLabel("关联实体类型")).toHaveValue("target");
  const patentLinkedEntityName = `Browser pipeline target ${fixtureKeyBase}`;
  await patentProfessionalQuery.getByLabel("关联实体筛选").fill(patentLinkedEntityName);
  await patentProfessionalQuery.getByRole("option", { name: new RegExp(patentLinkedEntityName) }).click();
  await patentProfessionalQuery.getByLabel("申请人").fill(`Browser applicant ${fixtureKeyBase}`);
  await patentProfessionalQuery.getByLabel("法律状态").selectOption("ACTIVE");
  await patentProfessionalQuery.getByLabel("优先权日期时间范围").selectOption("custom");
  const professionalPriorityRange = patentProfessionalQuery.getByRole("group", { name: "优先权日期" });
  await professionalPriorityRange.getByLabel("起").fill("2024-01-10");
  await professionalPriorityRange.getByLabel("止").fill("2024-01-10");
  await patentProfessionalQuery.getByLabel("到期日期时间范围").selectOption("custom");
  const professionalExpirationRange = patentProfessionalQuery.getByRole("group", { name: "到期日期" });
  await professionalExpirationRange.getByLabel("起").fill("2044-01-10");
  await professionalExpirationRange.getByLabel("止").fill("2044-01-10");
  const professionalPatentResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/patent-families" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("entity_id") === pipelineTargetId &&
      url.searchParams.get("applicant") === `Browser applicant ${fixtureKeyBase}` &&
      url.searchParams.get("legal_status") === "ACTIVE" &&
      url.searchParams.get("priority_from") === "2024-01-10T00:00:00.000Z" &&
      url.searchParams.get("priority_to") === "2024-01-10T23:59:59.999Z" &&
      url.searchParams.get("expiration_from") === "2044-01-10T00:00:00.000Z" &&
      url.searchParams.get("expiration_to") === "2044-01-10T23:59:59.999Z"
    );
  });
  await patentProfessionalQuery.getByRole("button", { name: "查询 专利情报" }).click();
  expect((await professionalPatentResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/view=patents/);
  await expect(page).toHaveURL(new RegExp(`entity_id=${pipelineTargetId}`));
  await expect(page).toHaveURL(/applicant=Browser\+applicant/);
  await expect(page).toHaveURL(/legal_status=ACTIVE/);
  await expect(page).toHaveURL(/priority_from=2024-01-10/);
  await expect(page).toHaveURL(/expiration_to=2044-01-10/);
  const professionalPatentTable = page.getByRole("table", { name: "专利族结果" });
  await expect(professionalPatentTable).toContainText(`WO-E2E-${fixtureKeyBase}`);
  await page.reload();
  const restoredPatentFilters = page.getByRole("form", { name: "专利族筛选" });
  await expect(restoredPatentFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await expect(restoredPatentFilters.getByLabel("申请人")).toHaveValue(`Browser applicant ${fixtureKeyBase}`);
  await expect(restoredPatentFilters.getByLabel("法律状态")).toHaveValue("ACTIVE");
  const restoredPriorityRange = restoredPatentFilters.getByRole("group", { name: "优先权日期" });
  await expect(restoredPriorityRange.getByLabel("起")).toHaveValue("2024-01-10");
  await expect(restoredPriorityRange.getByLabel("止")).toHaveValue("2024-01-10");
  const restoredExpirationRange = restoredPatentFilters.getByRole("group", { name: "预计到期日期" });
  await expect(restoredExpirationRange.getByLabel("起")).toHaveValue("2044-01-10");
  await expect(restoredExpirationRange.getByLabel("止")).toHaveValue("2044-01-10");
  await expect(professionalPatentTable).toContainText(`WO-E2E-${fixtureKeyBase}`);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/patent-families",
    resultSurface: professionalPatentTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const dealProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await dealProfessionalQuery.getByRole("button", { name: "交易与公司", exact: true }).click();
  await expect(dealProfessionalQuery.getByLabel("交易类型")).toContainText("许可");
  const professionalDealAssetName = `Browser regulatory drug ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("交易药品筛选").fill(professionalDealAssetName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealAssetName) }).click();
  const professionalDealTargetName = `Browser pipeline target ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("关联靶点筛选").fill(professionalDealTargetName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealTargetName) }).click();
  const professionalDealDiseaseName = `Browser regulatory indication ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("关联适应症筛选").fill(professionalDealDiseaseName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealDiseaseName) }).click();
  const professionalDealPartyName = `Browser regulatory company ${fixtureKeyBase}`;
  await dealProfessionalQuery.getByLabel("参与机构筛选").fill(professionalDealPartyName);
  await dealProfessionalQuery.getByRole("option", { name: new RegExp(professionalDealPartyName) }).click();
  await dealProfessionalQuery.getByLabel("交易类型").selectOption("license");
  await dealProfessionalQuery.getByLabel("交易状态").selectOption("active");
  await dealProfessionalQuery.getByLabel("交易方向").selectOption("outbound");
  await dealProfessionalQuery.getByLabel("交易披露日期时间范围").selectOption("custom");
  const professionalDealAnnouncedRange = dealProfessionalQuery.getByRole("group", { name: "交易披露日期" });
  await professionalDealAnnouncedRange.getByLabel("起").fill("2026-01-20");
  await professionalDealAnnouncedRange.getByLabel("止").fill("2026-01-20");
  await dealProfessionalQuery.getByText("更多交易条件").click();
  await dealProfessionalQuery.getByLabel("方向参照地区").fill("US");
  await dealProfessionalQuery.getByLabel("交易地域").selectOption("global");
  const professionalDealModalities = dealProfessionalQuery.getByRole("group", { name: "资产模态" });
  await professionalDealModalities.getByLabel("资产模态：全部").click();
  await professionalDealModalities.getByRole("checkbox", { name: /small molecule/ }).click();
  const professionalDealProgramTags = dealProfessionalQuery.getByRole("group", { name: "资产项目标签" });
  await professionalDealProgramTags.getByLabel("资产项目标签：全部").click();
  await professionalDealProgramTags.getByRole("checkbox", { name: /first_in_class/ }).click();
  await dealProfessionalQuery.getByLabel("参与角色").selectOption("licensor");
  await dealProfessionalQuery.getByLabel("机构所在地区").selectOption("US");
  await dealProfessionalQuery.getByLabel("机构类型").selectOption("biopharma");
  await dealProfessionalQuery.getByLabel("交易时阶段").selectOption("phase_1");
  await dealProfessionalQuery.getByLabel("当前最高阶段").selectOption("phase_2");
  await dealProfessionalQuery.getByLabel("权益类型").selectOption("commercialization");
  await dealProfessionalQuery.getByLabel("权益地区").selectOption("Greater China");
  await dealProfessionalQuery.getByLabel("币种").selectOption("USD");
  await dealProfessionalQuery.getByLabel("信息更新日期时间范围").selectOption("custom");
  const professionalDealUpdatedRange = dealProfessionalQuery.getByRole("group", { name: "信息更新日期" });
  await professionalDealUpdatedRange.getByLabel("起").fill("2026-03-15");
  await professionalDealUpdatedRange.getByLabel("止").fill("2026-03-15");
  await dealProfessionalQuery.getByLabel("首付款下限").fill("10000000");
  await dealProfessionalQuery.getByLabel("首付款上限").fill("30000000");
  await dealProfessionalQuery.getByLabel("潜在总额下限").fill("100000000");
  await dealProfessionalQuery.getByLabel("潜在总额上限").fill("500000000");
  const professionalDealResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/deal-transactions" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("deal_type") === "license" &&
      url.searchParams.get("status") === "active" &&
      url.searchParams.get("direction") === "outbound" &&
      url.searchParams.get("direction_reference_jurisdiction") === "US" &&
      url.searchParams.get("territory") === "global" &&
      url.searchParams.get("asset_entity_id") === regulatorySubjectId &&
      url.searchParams.get("target_entity_id") === pipelineTargetId &&
      url.searchParams.get("disease_entity_id") === regulatoryIndicationId &&
      url.searchParams.get("party_entity_id") === pipelineOrganizationId &&
      url.searchParams.get("party_role") === "licensor" &&
      url.searchParams.get("party_country_region") === "US" &&
      url.searchParams.get("party_organization_type") === "biopharma" &&
      url.searchParams.get("development_phase_at_transaction") === "phase_1" &&
      url.searchParams.get("current_development_phase") === "phase_2" &&
      url.searchParams.get("right_type") === "commercialization" &&
      url.searchParams.get("rights_territory") === "Greater China" &&
      url.searchParams.get("currency") === "USD" &&
      url.searchParams.get("announced_from") === "2026-01-20T00:00:00.000Z" &&
      url.searchParams.get("announced_to") === "2026-01-20T23:59:59.999Z" &&
      url.searchParams.get("source_updated_from") === "2026-03-15T00:00:00.000Z" &&
      url.searchParams.get("source_updated_to") === "2026-03-15T23:59:59.999Z" &&
      url.searchParams.get("upfront_amount_min") === "10000000" &&
      url.searchParams.get("upfront_amount_max") === "30000000" &&
      url.searchParams.get("total_potential_amount_min") === "100000000" &&
      url.searchParams.get("total_potential_amount_max") === "500000000" &&
      url.searchParams.getAll("asset_modality").includes("small molecule") &&
      url.searchParams.getAll("asset_program_tag").includes("first_in_class")
    );
  });
  await dealProfessionalQuery.getByRole("button", { name: "查询 交易与公司" }).click();
  expect((await professionalDealResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/view=deals/);
  await expect(page).toHaveURL(new RegExp(`asset_entity_id=${regulatorySubjectId}`));
  await expect(page).toHaveURL(new RegExp(`target_entity_id=${pipelineTargetId}`));
  await expect(page).toHaveURL(new RegExp(`disease_entity_id=${regulatoryIndicationId}`));
  await expect(page).toHaveURL(new RegExp(`party_entity_id=${pipelineOrganizationId}`));
  await expect(page).toHaveURL(/asset_modality=small\+molecule/);
  await expect(page).toHaveURL(/asset_program_tag=first_in_class/);
  const professionalDealTable = page.getByRole("table", { name: "交易结果" });
  await expect(professionalDealTable).toContainText(`Browser deal ${fixtureKeyBase}`);
  await page.reload();
  const restoredProfessionalDealFilters = page.getByRole("form", { name: "交易筛选" });
  await expect(restoredProfessionalDealFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await expect(restoredProfessionalDealFilters.getByLabel("交易类型")).toHaveValue("license");
  await expect(restoredProfessionalDealFilters.getByLabel("交易状态")).toHaveValue("active");
  await expect(restoredProfessionalDealFilters.getByLabel("交易方向")).toHaveValue("outbound");
  await expect(professionalDealTable).toContainText(`Browser deal ${fixtureKeyBase}`);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/deal-transactions",
    resultSurface: professionalDealTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const regulatoryProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await regulatoryProfessionalQuery.getByRole("button", { name: "监管与安全", exact: true }).click();
  await expect(regulatoryProfessionalQuery.getByLabel("监管机构")).toContainText("FDA (2)");
  await regulatoryProfessionalQuery.getByLabel("监管机构").selectOption("FDA");
  await regulatoryProfessionalQuery.getByLabel("辖区").selectOption("US");
  await regulatoryProfessionalQuery.getByLabel("事件类型").selectOption("approval");
  await regulatoryProfessionalQuery.getByLabel("事件状态").selectOption("approved");
  await regulatoryProfessionalQuery.getByLabel("监管决定日期时间范围").selectOption("custom");
  const professionalDecisionRange = regulatoryProfessionalQuery.getByRole("group", { name: "监管决定日期" });
  await professionalDecisionRange.getByLabel("起").fill("2026-02-20");
  await professionalDecisionRange.getByLabel("止").fill("2026-02-20");
  await regulatoryProfessionalQuery.getByText("更多监管与安全条件").click();
  await regulatoryProfessionalQuery.getByLabel("认定资格").selectOption("breakthrough_therapy");
  await regulatoryProfessionalQuery.getByLabel("标签变更").selectOption("initial_label");
  await regulatoryProfessionalQuery.getByLabel("黑框警告").selectOption("true");
  await regulatoryProfessionalQuery.getByLabel("安全信号").selectOption("adverse_event");
  await regulatoryProfessionalQuery.getByLabel("严重程度").selectOption("serious");
  await regulatoryProfessionalQuery.getByLabel("信号状态").selectOption("confirmed");
  await regulatoryProfessionalQuery.getByLabel("来源更新日期时间范围").selectOption("custom");
  const professionalSourceRange = regulatoryProfessionalQuery.getByRole("group", { name: "来源更新日期" });
  await professionalSourceRange.getByLabel("起").fill("2026-02-22");
  await professionalSourceRange.getByLabel("止").fill("2026-02-22");
  const professionalRegulatoryResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/regulatory-event-timeline" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("agency") === "FDA" &&
      url.searchParams.get("jurisdiction") === "US" &&
      url.searchParams.get("event_type") === "approval" &&
      url.searchParams.get("status") === "approved" &&
      url.searchParams.get("designation_type") === "breakthrough_therapy" &&
      url.searchParams.get("label_change_type") === "initial_label" &&
      url.searchParams.get("has_boxed_warning") === "true" &&
      url.searchParams.get("safety_signal_type") === "adverse_event" &&
      url.searchParams.get("safety_severity") === "serious" &&
      url.searchParams.get("safety_status") === "confirmed" &&
      url.searchParams.get("decision_from") === "2026-02-20T00:00:00.000Z" &&
      url.searchParams.get("decision_to") === "2026-02-20T23:59:59.999Z" &&
      url.searchParams.get("source_updated_from") === "2026-02-22T00:00:00.000Z" &&
      url.searchParams.get("source_updated_to") === "2026-02-22T23:59:59.999Z"
    );
  });
  await regulatoryProfessionalQuery.getByRole("button", { name: "查询 监管与安全" }).click();
  expect((await professionalRegulatoryResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/view=regulatory/);
  await expect(page).toHaveURL(/designation_type=breakthrough_therapy/);
  await expect(page).toHaveURL(/label_change_type=initial_label/);
  await expect(page).toHaveURL(/boxed_warning=true/);
  await expect(page).toHaveURL(/safety_signal_type=adverse_event/);
  await expect(page).toHaveURL(/safety_severity=serious/);
  await expect(page).toHaveURL(/safety_status=confirmed/);
  await expect(page).toHaveURL(/decision_from=2026-02-20/);
  await expect(page).toHaveURL(/source_updated_from=2026-02-22/);
  const professionalRegulatoryTable = page.getByRole("table", { name: "监管事件结果" });
  await expect(professionalRegulatoryTable).toContainText(`Browser regulatory event ${fixtureKeyBase}`);
  await expect(professionalRegulatoryTable).not.toContainText(`Browser regulatory negative event ${fixtureKeyBase}`);
  await page.reload();
  const restoredProfessionalRegulatoryFilters = page.getByRole("form", { name: "监管事件筛选" });
  await expect(restoredProfessionalRegulatoryFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await expect(restoredProfessionalRegulatoryFilters.getByLabel("监管机构")).toHaveValue("FDA");
  await expect(restoredProfessionalRegulatoryFilters.getByLabel("信号状态")).toHaveValue("confirmed");
  await restoredProfessionalRegulatoryFilters.getByText("更多监管与安全条件").click();
  const restoredProfessionalDecisionRange = restoredProfessionalRegulatoryFilters.getByRole("group", {
    name: "决定日期",
  });
  await expect(restoredProfessionalDecisionRange.getByLabel("起")).toHaveValue("2026-02-20");
  await expect(restoredProfessionalDecisionRange.getByLabel("止")).toHaveValue("2026-02-20");
  await expect(professionalRegulatoryTable).toContainText(`Browser regulatory event ${fixtureKeyBase}`);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/regulatory-event-timeline",
    resultSurface: professionalRegulatoryTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const epidemiologyProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await epidemiologyProfessionalQuery.getByRole("button", { name: "流行病学", exact: true }).click();
  const professionalEpidemiologyDiseaseName = `Browser epidemiology disease ${fixtureKeyBase}`;
  await epidemiologyProfessionalQuery.getByLabel("疾病筛选").fill(professionalEpidemiologyDiseaseName);
  await epidemiologyProfessionalQuery
    .getByRole("option", { name: new RegExp(professionalEpidemiologyDiseaseName) })
    .click();
  await expect(epidemiologyProfessionalQuery.getByLabel("统计指标")).toContainText("患病率");
  await epidemiologyProfessionalQuery.getByLabel("统计指标").selectOption("prevalence");
  await epidemiologyProfessionalQuery.getByLabel("地区").selectOption("China");
  await epidemiologyProfessionalQuery.getByLabel("单位").selectOption("patients");
  await epidemiologyProfessionalQuery.getByLabel("标准患者人群").selectOption(epidemiologyPatientPopulationId);
  await epidemiologyProfessionalQuery.getByLabel("人群口径").selectOption("adults");
  await epidemiologyProfessionalQuery.getByLabel("年龄组").selectOption("18+");
  await epidemiologyProfessionalQuery.getByLabel("性别").selectOption("all");
  await epidemiologyProfessionalQuery.getByLabel("统计周期时间范围").selectOption("custom");
  const professionalEpidemiologyPeriod = epidemiologyProfessionalQuery.getByRole("group", { name: "统计周期" });
  await professionalEpidemiologyPeriod.getByLabel("起").fill("2025-01-01");
  await professionalEpidemiologyPeriod.getByLabel("止").fill("2025-12-31");
  const professionalEpidemiologyResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/epidemiology-observations" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("disease_entity_id") === epidemiologyDiseaseId &&
      url.searchParams.get("measure") === "prevalence" &&
      url.searchParams.get("geography") === "China" &&
      url.searchParams.get("unit") === "patients" &&
      url.searchParams.get("patient_population_id") === epidemiologyPatientPopulationId &&
      url.searchParams.get("population_scope") === "adults" &&
      url.searchParams.get("age_group") === "18+" &&
      url.searchParams.get("sex") === "all" &&
      url.searchParams.get("period_start_from") === "2025-01-01T00:00:00Z" &&
      url.searchParams.get("period_end_to") === "2025-12-31T23:59:59Z"
    );
  });
  await epidemiologyProfessionalQuery.getByRole("button", { name: "查询 流行病学" }).click();
  const professionalEpidemiologyPayload = (await professionalEpidemiologyResponse).json() as Promise<{
    total: number;
    items: Array<{ id: string }>;
  }>;
  await expect(professionalEpidemiologyPayload).resolves.toMatchObject({
    total: 1,
    items: [{ id: epidemiologyObservationId }],
  });
  await expect(page).toHaveURL(/view=epidemiology/);
  await expect(page).toHaveURL(new RegExp(`disease_entity_id=${epidemiologyDiseaseId}`));
  await expect(page).toHaveURL(new RegExp(`patient_population_id=${epidemiologyPatientPopulationId}`));
  await expect(page).toHaveURL(/population_scope=adults/);
  await expect(page).toHaveURL(/age_group=18%2B/);
  await expect(page).toHaveURL(/period_start_from=2025-01-01/);
  const professionalEpidemiologyTable = page.getByRole("table", { name: "流行病学结果" });
  await expect(professionalEpidemiologyTable).toContainText(professionalEpidemiologyDiseaseName);
  await page.reload();
  const restoredProfessionalEpidemiologyFilters = page.getByRole("form", { name: "流行病学筛选" });
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("统计指标")).toHaveValue("prevalence");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("地区")).toHaveValue("China");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("单位")).toHaveValue("patients");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("标准患者人群")).toHaveValue(
    epidemiologyPatientPopulationId,
  );
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("人群口径")).toHaveValue("adults");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("年龄组")).toHaveValue("18+");
  await expect(restoredProfessionalEpidemiologyFilters.getByLabel("性别")).toHaveValue("all");
  await expect(professionalEpidemiologyTable).toContainText(professionalEpidemiologyDiseaseName);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/epidemiology-observations",
    resultSurface: professionalEpidemiologyTable,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`);
  const newsProfessionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await newsProfessionalQuery.getByRole("button", { name: "资讯与会议", exact: true }).click();
  const professionalNewsEntityName = `Browser pipeline target ${fixtureKeyBase}`;
  await newsProfessionalQuery.getByLabel("关联实体筛选").fill(professionalNewsEntityName);
  await newsProfessionalQuery.getByRole("option", { name: new RegExp(professionalNewsEntityName) }).click();
  await expect(newsProfessionalQuery.getByLabel("事件类型")).toContainText("会议摘要");
  await newsProfessionalQuery.getByLabel("事件类型").selectOption("conference_abstract");
  await newsProfessionalQuery.getByLabel("发布方").selectOption(`Browser publisher ${fixtureKeyBase}`);
  await newsProfessionalQuery.getByLabel("语言").selectOption("en");
  await newsProfessionalQuery.getByLabel("会议 / 场景").selectOption("ASCO 2026");
  await newsProfessionalQuery.getByLabel("内容范围").selectOption("research");
  await newsProfessionalQuery.getByLabel("发布日期时间范围").selectOption("custom");
  const professionalNewsPublishedRange = newsProfessionalQuery.getByRole("group", { name: "发布日期" });
  await professionalNewsPublishedRange.getByLabel("起").fill("2026-07-01");
  await professionalNewsPublishedRange.getByLabel("止").fill("2026-07-31");
  const professionalNewsResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      response.request().method() === "GET" &&
      url.pathname === "/api/v1/news-events" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("entity_id") === pipelineTargetId &&
      url.searchParams.get("event_type") === "conference_abstract" &&
      url.searchParams.get("publisher") === `Browser publisher ${fixtureKeyBase}` &&
      url.searchParams.get("language") === "en" &&
      url.searchParams.get("venue") === "ASCO 2026" &&
      url.searchParams.get("content_scope") === "research" &&
      url.searchParams.get("published_from") === "2026-07-01" &&
      url.searchParams.get("published_to") === "2026-07-31"
    );
  });
  await newsProfessionalQuery.getByRole("button", { name: "查询 资讯与会议" }).click();
  const professionalNewsPayload = (await professionalNewsResponse).json() as Promise<{
    total: number;
    items: Array<{ id: string }>;
  }>;
  await expect(professionalNewsPayload).resolves.toMatchObject({ total: 1, items: [{ id: newsEventId }] });
  await expect(page).toHaveURL(/view=news/);
  await expect(page).toHaveURL(new RegExp(`entity_id=${pipelineTargetId}`));
  await expect(page).toHaveURL(/event_type=conference_abstract/);
  await expect(page).toHaveURL(/publisher=Browser\+publisher/);
  await expect(page).toHaveURL(/venue=ASCO\+2026/);
  await expect(page).toHaveURL(/content_scope=research/);
  await expect(page.getByRole("region", { name: "研究发布时间线" })).toContainText(
    `Browser news event ${fixtureKeyBase}`,
  );
  await page.reload();
  const restoredProfessionalNewsFilters = page.getByRole("form", { name: "新闻与会议筛选" });
  await expect(restoredProfessionalNewsFilters.getByRole("group", { name: "关联实体规范实体筛选" })).toContainText(
    professionalNewsEntityName,
  );
  await expect(restoredProfessionalNewsFilters.getByLabel("事件类型")).toHaveValue("conference_abstract");
  await expect(restoredProfessionalNewsFilters.getByLabel("发布方")).toHaveValue(`Browser publisher ${fixtureKeyBase}`);
  await expect(restoredProfessionalNewsFilters.getByLabel("语言")).toHaveValue("en");
  await expect(restoredProfessionalNewsFilters.getByLabel("会议 / 场景")).toHaveValue("ASCO 2026");
  const professionalNewsTimeline = page.getByRole("region", { name: "研究发布时间线" });
  await expect(professionalNewsTimeline).toContainText(`Browser news event ${fixtureKeyBase}`);
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/news-events",
    resultSurface: professionalNewsTimeline,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=deals&q=${encodeURIComponent(fixtureKeyBase)}`);
  const governedDealFilters = page.getByRole("form", { name: "交易筛选" });
  const dealTitle = `Browser deal ${fixtureKeyBase}`;
  const governedDealTable = page.getByRole("table", { name: "交易结果" });
  await expect(governedDealTable).toContainText(dealTitle);
  await governedDealTable.getByRole("button", { name: new RegExp(`^${dealTitle}`) }).click();
  await expect(page).toHaveURL(new RegExp(`deal=${dealProfileId}`));
  await expect(page.getByRole("heading", { name: dealTitle })).toBeVisible();
  await expect(page.getByText(/交易专业档案/)).toBeVisible();
  await page.getByRole("tab", { name: "参与方" }).click();
  await expect(page).toHaveURL(new RegExp(`deal=${dealProfileId}.*section=parties`));
  await expect(page.getByRole("button", { name: /Browser regulatory company/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Browser pipeline company B/ })).toBeVisible();
  await page.getByRole("tab", { name: "资产与阶段" }).click();
  await expect(page.getByRole("button", { name: /Browser regulatory drug/ })).toBeVisible();
  await page.getByRole("tab", { name: "地域权益" }).click();
  await expect(page).toHaveURL(new RegExp(`deal=${dealProfileId}.*section=rights`));
  await page.reload();
  await expect(page.getByRole("tab", { name: "地域权益" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Exclusive commercialization rights for the controlled browser asset")).toBeVisible();
  const dealRightsVisual = page.locator(".deal-professional-body");
  await expect(dealRightsVisual).toHaveCount(1);
  await expect(dealRightsVisual).toHaveScreenshot("research-deal-rights.png", {
    animations: "disabled",
    caret: "hide",
    mask: [dealRightsVisual.locator(".deal-rights-table button")],
    maskColor: "#dce4e7",
    maxDiffPixelRatio: 0.001,
  });
  await page.getByRole("tab", { name: "条款与来源" }).click();
  await expect(page.getByText("browser acceptance", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "返回交易列表" }).click();
  await expect(page).not.toHaveURL(/deal=/);
  await expect(governedDealFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(`/workspace/research?view=patents&q=${encodeURIComponent(fixtureKeyBase)}`);
  const patentFilters = page.getByRole("form", { name: "专利族筛选" });
  const patentIdentifier = `WO-E2E-${fixtureKeyBase}`;
  const patentTitle = `Browser patent family ${fixtureKeyBase}`;
  const patentTable = page.getByRole("table", { name: "专利族结果" });
  await expect(patentTable).toContainText(patentTitle);
  await patentTable.getByRole("button", { name: `打开专利族详情：${patentIdentifier}` }).click();
  await expect(page).toHaveURL(new RegExp(`patent=${patentFamilyId}`));
  await expect(page.getByRole("heading", { name: patentTitle })).toBeVisible();
  await expect(page.getByText(`专利族专业档案 · ${patentIdentifier}`)).toBeVisible();
  await page.getByRole("tab", { name: "法律与权利要求" }).click();
  await expect(page).toHaveURL(new RegExp(`patent=${patentFamilyId}.*section=timeline`));
  await page.reload();
  await expect(page.getByRole("tab", { name: "法律与权利要求" })).toHaveAttribute("aria-selected", "true");
  await page.getByText("1 个事件 · 1 项独立权利要求").click();
  await expect(page.getByText("Controlled composition claim for browser acceptance")).toBeVisible();
  const patentTimelineVisual = page.locator(".patent-professional-body");
  await expect(patentTimelineVisual).toHaveCount(1);
  await expect(patentTimelineVisual).toHaveScreenshot("research-patent-timeline.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.001,
  });
  await page.getByRole("tab", { name: "关联资产" }).click();
  await expect(page).toHaveURL(new RegExp(`patent=${patentFamilyId}.*section=relationships`));
  await expect(page.getByRole("button", { name: `Browser pipeline target ${fixtureKeyBase}` })).toBeVisible();
  await page.getByRole("button", { name: "返回专利族列表" }).click();
  await expect(page).not.toHaveURL(/patent=/);
  await expect(patentFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto("/workspace/research?view=deals&q=license");
  const dealFilters = page.getByRole("form", { name: "交易筛选" });
  await expect(dealFilters.getByLabel("关键词")).toHaveValue("license");
  await dealFilters.getByLabel("交易状态").selectOption("active");
  await dealFilters.getByLabel("交易方向").selectOption("outbound");
  await dealFilters.getByLabel("参与机构").fill(companyName);
  await page.getByRole("option", { name: new RegExp(companyName) }).click();
  await dealFilters.getByLabel("参与角色").selectOption("licensor");
  await dealFilters.getByText("更多交易条件").click();
  await dealFilters.getByLabel("方向参照地区").fill("US");
  await dealFilters.getByLabel("机构所在地区").fill("US");
  await dealFilters.getByLabel("机构类型").fill("biopharma");
  await dealFilters.getByLabel("交易时阶段").selectOption("phase_2");
  await dealFilters.getByLabel("当前最高阶段").selectOption("phase_3");
  await dealFilters.getByLabel("权益类型").selectOption("commercialization");
  const announcedRange = dealFilters.getByRole("group", { name: "初始披露" });
  await announcedRange.getByLabel("起").fill("2026-01-01");
  await announcedRange.getByLabel("止").fill("2026-12-31");
  const terminatedRange = dealFilters.getByRole("group", { name: "终止日期" });
  await terminatedRange.getByLabel("起").fill("2026-02-01");
  await terminatedRange.getByLabel("止").fill("2026-12-31");
  const updatedRange = dealFilters.getByRole("group", { name: "信息更新" });
  await updatedRange.getByLabel("起").fill("2026-03-01");
  await updatedRange.getByLabel("止").fill("2026-12-31");
  const upfrontRange = dealFilters.getByRole("group", { name: "首付款" });
  await upfrontRange.getByLabel("下限").fill("10000000");
  await upfrontRange.getByLabel("上限").fill("30000000");
  const totalRange = dealFilters.getByRole("group", { name: "潜在总额" });
  await totalRange.getByLabel("下限").fill("100000000");
  await totalRange.getByLabel("上限").fill("500000000");
  await dealFilters.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL(/status=active/);
  await expect(page).toHaveURL(/direction=outbound/);
  await expect(page).toHaveURL(/direction_reference_jurisdiction=US/);
  await expect(page).toHaveURL(new RegExp(`party_entity_id=${createdCompany.id}`));
  await expect(page).toHaveURL(/party_role=licensor/);
  await expect(page).toHaveURL(/party_country_region=US/);
  await expect(page).toHaveURL(/party_organization_type=biopharma/);
  await expect(page).toHaveURL(/development_phase_at_transaction=phase_2/);
  await expect(page).toHaveURL(/current_development_phase=phase_3/);
  await expect(page).toHaveURL(/right_type=commercialization/);
  await expect(page).toHaveURL(/announced_from=2026-01-01/);
  await expect(page).toHaveURL(/terminated_from=2026-02-01/);
  await expect(page).toHaveURL(/source_updated_from=2026-03-01/);
  await expect(page).toHaveURL(/upfront_amount_min=10000000/);
  await expect(page).toHaveURL(/total_potential_amount_max=500000000/);
  const appliedDealFilters = page.getByRole("region", { name: "已应用查询条件" });
  await expect(appliedDealFilters).toContainText("active");
  await expect(appliedDealFilters).toContainText("licensor");
  await expect(appliedDealFilters).toContainText("phase_2");
  await page.reload();
  await expect(dealFilters.getByLabel("交易状态")).toHaveValue("active");
  await expect(dealFilters.getByLabel("交易方向")).toHaveValue("outbound");
  await expect(dealFilters.getByLabel("参与机构")).toHaveValue(companyName);
  await expect(dealFilters.getByLabel("参与角色")).toHaveValue("licensor");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&display=landscape`,
  );
  const pipelineFilters = page.getByRole("form", { name: "药物与管线筛选" });
  await expect(pipelineFilters.getByRole("group", { name: "靶点规范实体筛选" })).toContainText(
    `Browser pipeline target ${fixtureKeyBase}`,
  );
  await expect(pipelineFilters.getByRole("group", { name: "适应症规范实体筛选" })).toContainText(
    `Browser regulatory indication ${fixtureKeyBase}`,
  );
  const pipelineLandscape = page.getByLabel("管线竞争格局");
  await expect(page.getByRole("button", { name: "格局" })).toHaveAttribute("aria-pressed", "true");
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发项目$/ })
      .locator(".."),
  ).toContainText("3");
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^药物$/ })
      .locator(".."),
  ).toContainText("3");
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发机构$/ })
      .locator(".."),
  ).toContainText("2");
  await expect(pipelineLandscape.getByRole("img", { name: "药物模态项目数量分布" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("img", { name: "靶点项目数量分布" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("img", { name: "靶点组合项目数量分布" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("img", { name: "适应症项目数量分布" })).toBeVisible();
  await expect(page.getByText("导出", { exact: true })).toBeVisible();
  await expect(
    pipelineLandscape.getByRole("button", { name: `打开Browser regulatory company ${fixtureKeyBase}档案` }),
  ).toBeVisible();
  const analysisControls = pipelineLandscape.getByRole("group", { name: "竞争格局分析控制" });
  await analysisControls.getByLabel("分析维度").selectOption("targets");
  await expect(page).toHaveURL(/analysis_dimension=targets/);
  await analysisControls.getByRole("button", { name: "表格" }).click();
  await expect(page).toHaveURL(/analysis_view=table/);
  await analysisControls.getByLabel("分析显示范围").selectOption("50");
  await expect(page).toHaveURL(/analysis_top=50/);
  await analysisControls.getByLabel("阶段分析口径").selectOption("global");
  await expect(page).toHaveURL(/analysis_stage=global/);
  await analysisControls.getByLabel("靶点聚合口径").selectOption("primary");
  await expect(page).toHaveURL(/target_aggregation=primary/);
  await expect(pipelineLandscape.getByRole("table", { name: "靶点统计表" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("columnheader", { name: "阶段构成" })).toBeVisible();
  await expect(pipelineLandscape.getByRole("heading", { name: "适应症", exact: true })).toHaveCount(0);
  const pipelineSubscriptionName = `Browser pipeline subscription ${fixtureKeyBase}`;
  const savePipelineTrigger = page.getByRole("button", { name: "保存/订阅" });
  await savePipelineTrigger.click();
  const savePipelineDialog = page.getByRole("dialog", { name: "保存当前管线检索" });
  const savePipelineName = savePipelineDialog.getByLabel("名称");
  await expect(savePipelineName).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(savePipelineDialog).toHaveCount(0);
  await expect(savePipelineTrigger).toBeFocused();
  await savePipelineTrigger.click();
  await expect(savePipelineName).toBeFocused();
  await savePipelineName.fill(pipelineSubscriptionName);
  await savePipelineDialog.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("管线检索已保存并启用监控")).toBeVisible();
  await expect(savePipelineTrigger).toBeFocused();
  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedPipelineRow = page.getByRole("row").filter({ hasText: pipelineSubscriptionName });
  await expect(savedPipelineRow).toContainText("药物与管线");
  await expect(savedPipelineRow).toContainText("统计表");
  await expect(savedPipelineRow).toContainText("条件：靶点=已选");
  const editSavedPipelineTrigger = savedPipelineRow.getByRole("button", { name: `编辑 ${pipelineSubscriptionName}` });
  await editSavedPipelineTrigger.click();
  const savedSearchEditor = page.getByRole("dialog", { name: "编辑已保存检索" });
  const maintainedPipelineSubscriptionName = `${pipelineSubscriptionName} curated`;
  const savedSearchName = savedSearchEditor.getByLabel("名称");
  await expect(savedSearchName).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(savedSearchEditor).toHaveCount(0);
  await expect(editSavedPipelineTrigger).toBeFocused();
  await editSavedPipelineTrigger.click();
  await expect(savedSearchName).toBeFocused();
  await savedSearchName.fill(maintainedPipelineSubscriptionName);
  await savedSearchEditor.getByLabel("业务说明").fill("季度竞争格局复核口径");
  await savedSearchEditor.getByRole("button", { name: "保存修改" }).click();
  await expect(savedSearchEditor).toHaveCount(0);
  const maintainedPipelineRow = page.getByRole("row").filter({ hasText: maintainedPipelineSubscriptionName });
  await expect(maintainedPipelineRow).toContainText("季度竞争格局复核口径");
  await expect(maintainedPipelineRow).toContainText("v1");
  await maintainedPipelineRow.getByRole("button", { name: `运行 ${maintainedPipelineSubscriptionName}` }).click();
  await expect(page).toHaveURL(/view=pipeline/);
  await expect(page).toHaveURL(/analysis_dimension=targets/);
  await expect(page).toHaveURL(/analysis_view=table/);
  await expect(page).toHaveURL(/analysis_top=50/);
  await expect(page).toHaveURL(/analysis_stage=global/);
  await expect(page).toHaveURL(/target_aggregation=primary/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&display=landscape`,
  );
  await expect(page).not.toHaveURL(/analysis_/);
  const targetCombinationDistribution = pipelineLandscape
    .locator(".pipeline-landscape-distribution")
    .filter({ has: page.getByRole("heading", { name: "靶点组合", exact: true }) });
  const dualTargetCombination = targetCombinationDistribution
    .locator("li")
    .filter({ hasText: `Browser combination target ${fixtureKeyBase}` });
  await expect(dualTargetCombination).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await dualTargetCombination.getByRole("button").click();
  await expect(page).toHaveURL(new RegExp(`target_combination_key=.*${pipelineCombinationTargetId}`));
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发项目$/ })
      .locator(".."),
  ).toContainText("1");
  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&display=landscape`,
  );
  await pipelineLandscape.getByTitle("按antibody筛选").click();
  await expect(page).toHaveURL(/modality=antibody/);
  await expect(
    pipelineLandscape
      .locator("dt")
      .filter({ hasText: /^研发项目$/ })
      .locator(".."),
  ).toContainText("1");
  await page.reload();
  await expect(page.getByRole("button", { name: "格局" })).toHaveAttribute("aria-pressed", "true");
  await pipelineFilters.getByLabel(/药物模态：/).click();
  await expect(pipelineFilters.getByRole("checkbox", { name: /antibody/ })).toBeChecked();

  await page.goto(
    `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}` +
      `&disease_entity_id=${pipelineDiseaseId}&organization_entity_id=${pipelineCollaboratorId}`,
  );
  await expect(pipelineFilters.getByRole("group", { name: "研发机构规范实体筛选" })).toContainText(
    `Browser pipeline company B ${fixtureKeyBase}`,
  );
  await pipelineFilters.getByText("机构、区域阶段、权益与里程碑").click();
  await pipelineFilters.getByLabel("机构角色").selectOption("collaborator");
  await pipelineFilters.getByLabel("机构类型").selectOption("biotech");
  await pipelineFilters.getByLabel("机构所在地区").selectOption("US");
  await pipelineFilters.getByLabel("全球最高阶段").selectOption("phase_2");
  await pipelineFilters.getByLabel("中国最高阶段").selectOption("phase_1");
  await pipelineFilters.getByLabel("研发权益地区").selectOption("Global");
  await pipelineFilters.getByLabel("商业化权益地区").selectOption("Greater China");
  await pipelineFilters.getByLabel(/项目标签：/).click();
  await pipelineFilters.getByRole("checkbox", { name: /first_in_class/ }).click();
  await pipelineFilters.getByLabel("里程碑类型").selectOption("first_patient_in");
  const milestoneRange = pipelineFilters.getByRole("group", { name: "里程碑日期" });
  await milestoneRange.getByLabel("起").fill("2026-06-01");
  await milestoneRange.getByLabel("止").fill("2026-06-30");
  await pipelineFilters.getByText("临床结果与交易信号").click();
  await pipelineFilters.getByLabel("是否已有临床结果").selectOption("true");
  await pipelineFilters.getByLabel("临床结果评价").selectOption("positive");
  await pipelineFilters.getByLabel("是否存在交易记录").selectOption("true");
  await pipelineFilters.getByLabel("交易币种").selectOption("USD");
  await pipelineFilters.getByLabel("潜在总额下限").fill("400000000");
  await pipelineFilters.getByLabel("潜在总额上限").fill("600000000");
  const exactOrganizationRelationshipResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/pipelines" &&
      url.searchParams.get("organization_entity_id") === pipelineCollaboratorId &&
      url.searchParams.get("organization_role") === "collaborator" &&
      url.searchParams.get("organization_type") === "biotech" &&
      url.searchParams.get("organization_country_region") === "US"
    );
  });
  await pipelineFilters.getByRole("button", { name: "查询", exact: true }).click();
  const exactOrganizationRelationship = await exactOrganizationRelationshipResponse;
  expect(exactOrganizationRelationship.ok()).toBe(true);
  const exactOrganizationPayload = (await exactOrganizationRelationship.json()) as {
    total: number;
    items: Array<{ drug_entity_id: string }>;
  };
  expect(exactOrganizationPayload.total).toBe(1);
  expect(exactOrganizationPayload.items.map((item) => item.drug_entity_id)).toEqual([regulatorySubjectId]);
  await expect(page).toHaveURL(/global_phase=phase_2/);
  await expect(page).toHaveURL(/organization_role=collaborator/);
  await expect(page).toHaveURL(/organization_type=biotech/);
  await expect(page).toHaveURL(/organization_country_region=US/);
  await expect(page).toHaveURL(/china_phase=phase_1/);
  await expect(page).toHaveURL(/commercialization_rights_region=Greater\+China/);
  await expect(page).toHaveURL(/milestone_type=first_patient_in/);
  await expect(page).toHaveURL(/milestone_from=2026-06-01/);
  await expect(page).toHaveURL(/has_clinical_results=true/);
  await expect(page).toHaveURL(/clinical_result_evaluation=positive/);
  await expect(page).toHaveURL(/has_deal=true/);
  await expect(page).toHaveURL(/deal_currency=USD/);
  await expect(page).toHaveURL(/deal_total_potential_amount_min=400000000/);
  const pipelineResultsUrl = new URL(page.url());
  const pipelineTable = page.getByRole("table", { name: "药物与研发管线结果" });
  await expect(pipelineTable).toContainText(`Browser regulatory drug ${fixtureKeyBase}`);
  await expect(pipelineTable).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(pipelineTable).toContainText("合作方");
  await expect(pipelineTable).toContainText(`Global Phase II first patient in ${fixtureKeyBase}`);
  await expect(pipelineTable).toContainText("2 项试验");
  await expect(pipelineTable).toContainText("积极");
  await expect(pipelineTable).toContainText("1 笔交易");
  await expect(pipelineTable).toContainText("USD");
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/pipelines",
    resultSurface: pipelineTable,
  });
  await expect(pipelineTable.getByRole("columnheader", { name: /作用机制/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /总体阶段/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /项目状态/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /全球阶段起始/ })).toBeVisible();
  await expect(pipelineTable.getByRole("columnheader", { name: /中国阶段起始/ })).toBeVisible();
  await expect(pipelineTable).toContainText("covalent inhibitor");
  await expect(pipelineTable).toContainText("进行中");
  await expect(pipelineTable).toContainText("2026/06/01");
  await expect(pipelineTable).toContainText("2025/03/01");
  const pipelineResearchUrl = page.url();
  await pipelineTable
    .getByRole("button", { name: `查看 Browser regulatory drug ${fixtureKeyBase} 的 2 项临床试验` })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=trials.*role_entity_id=${regulatorySubjectId}`));
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("关联规范药物");
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await page.goBack();
  await expect(page).toHaveURL(pipelineResearchUrl);
  await expect(page.getByRole("table", { name: "药物与研发管线结果" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await page
    .getByRole("table", { name: "药物与研发管线结果" })
    .getByRole("button", { name: `查看 Browser regulatory drug ${fixtureKeyBase} 的 1 笔交易` })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=deals.*asset_entity_id=${regulatorySubjectId}`));
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("交易药品");
  await expect(page.getByRole("table", { name: "交易结果" })).toContainText(`Browser deal ${fixtureKeyBase}`);
  await page.goBack();
  await expect(page).toHaveURL(pipelineResearchUrl);
  await expect(page.getByRole("table", { name: "药物与研发管线结果" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await expect(page.getByText(/全部结果按状态日期降序/)).toBeVisible();
  const sortedPipelineResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/pipelines" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["mechanism_of_action:asc", "drug_name:desc"])
    );
  });
  const pipelineSortMenu = page.locator(".table-sort-menu");
  await pipelineSortMenu.getByText("排序", { exact: true }).click();
  await expect(pipelineSortMenu.getByLabel("第 1 排序字段", { exact: true })).toHaveValue("status_date");
  await pipelineSortMenu.getByLabel("第 1 排序字段", { exact: true }).selectOption("mechanism_of_action");
  await pipelineSortMenu.getByRole("button", { name: "第 1 排序方向：升序" }).click();
  await pipelineSortMenu.getByRole("button", { name: "添加排序字段" }).click();
  await pipelineSortMenu.getByLabel("第 2 排序字段", { exact: true }).selectOption("drug_name");
  await pipelineSortMenu.getByRole("button", { name: "第 2 排序方向：降序" }).click();
  expect(new URL(page.url()).searchParams.getAll("sort")).toEqual([]);
  await pipelineSortMenu.getByRole("button", { name: "应用排序" }).click();
  const pipelineSortResponse = await sortedPipelineResponse;
  expect(pipelineSortResponse.ok()).toBe(true);
  const pipelineSortPayload = (await pipelineSortResponse.json()) as {
    sort_by: string;
    sort_direction: string;
    sort: Array<{ field: string; direction: string }>;
  };
  expect(pipelineSortPayload).toMatchObject({
    sort_by: "mechanism_of_action",
    sort_direction: "asc",
    sort: [
      { field: "mechanism_of_action", direction: "asc" },
      { field: "drug_name", direction: "desc" },
    ],
  });
  expect(new URL(page.url()).searchParams.getAll("sort")).toEqual(["mechanism_of_action:asc", "drug_name:desc"]);
  await expect(page.getByText(/全部结果按作用机制升序、药物降序/)).toBeVisible();
  await page.reload();
  await expect(pipelineFilters.getByLabel("是否已有临床结果")).toHaveValue("true");
  await expect(pipelineFilters.getByLabel("临床结果评价")).toHaveValue("positive");
  await expect(pipelineFilters.getByLabel("是否存在交易记录")).toHaveValue("true");
  await expect(pipelineFilters.getByLabel("交易币种")).toHaveValue("USD");
  await expect(pipelineFilters.getByLabel("机构角色")).toHaveValue("collaborator");
  await expect(pipelineFilters.getByLabel("机构类型")).toHaveValue("biotech");
  await expect(pipelineFilters.getByLabel("机构所在地区")).toHaveValue("US");
  await pipelineSortMenu.getByText("排序", { exact: true }).click();
  await expect(pipelineSortMenu.getByLabel("第 1 排序字段", { exact: true })).toHaveValue("mechanism_of_action");
  await expect(pipelineSortMenu.getByRole("button", { name: "第 1 排序方向：升序" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(pipelineSortMenu.getByLabel("第 2 排序字段", { exact: true })).toHaveValue("drug_name");
  await expect(pipelineSortMenu.getByRole("button", { name: "第 2 排序方向：降序" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(pipelineTable.getByRole("columnheader", { name: /作用机制/ })).toHaveAttribute("aria-sort", "ascending");
  await expect(pipelineTable.getByRole("columnheader", { name: /药物/ }).locator(".sort-priority")).toHaveText("2");
  const pipelineColumnMenu = page.locator(".table-column-menu");
  await pipelineColumnMenu.locator("summary").click();
  await pipelineColumnMenu.getByRole("checkbox", { name: "显示列：记录地区" }).uncheck();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toHaveCount(0);
  await page.reload();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toHaveCount(0);
  await pipelineColumnMenu.locator("summary").click();
  await pipelineColumnMenu.getByRole("checkbox", { name: "显示列：记录地区" }).check();
  await expect(pipelineTable.getByRole("columnheader", { name: /记录地区/ })).toBeVisible();
  const pipelineViewport = page.getByRole("region", { name: "药物与研发管线结果滚动区域" });
  await pipelineViewport.evaluate((element) => {
    element.scrollLeft = element.scrollWidth;
  });
  const stickyIdentityColumn = await pipelineViewport.evaluate((element) => {
    const firstCell = element.querySelector<HTMLElement>(".virtual-table-cell:first-child");
    if (!firstCell) return null;
    const viewportRect = element.getBoundingClientRect();
    const cellRect = firstCell.getBoundingClientRect();
    return {
      cellLeft: Math.round(cellRect.left),
      viewportLeft: Math.round(viewportRect.left),
      overflow: element.scrollWidth > element.clientWidth,
    };
  });
  expect(stickyIdentityColumn).not.toBeNull();
  expect(
    Math.abs((stickyIdentityColumn?.cellLeft ?? 0) - (stickyIdentityColumn?.viewportLeft ?? 0)),
  ).toBeLessThanOrEqual(2);
  await page.reload();
  await expect(pipelineFilters.getByLabel("里程碑类型")).toHaveValue("first_patient_in");
  await expect(pipelineTable).toContainText(`Global Phase II first patient in ${fixtureKeyBase}`);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  const regulatoryDrugName = `Browser regulatory drug ${fixtureKeyBase}`;
  await pipelineTable.scrollIntoViewIfNeeded();
  await pipelineTable.getByRole("button", { name: new RegExp(`^${regulatoryDrugName}`) }).click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await expect(page.getByRole("heading", { name: regulatoryDrugName, exact: true })).toBeVisible();
  await expect(
    page
      .locator("dt")
      .filter({ hasText: /^全球 \/ 中国$/ })
      .locator(".."),
  ).toContainText("II 期临床 / I 期临床");
  await expect(page.getByRole("button", { name: `Browser pipeline target ${fixtureKeyBase}` })).toBeVisible();
  await page.locator(".drug-profile-structure").scrollIntoViewIfNeeded();
  await expect(page.getByRole("img", { name: `${regulatoryDrugName} 2D 结构` })).toBeVisible();
  await page.getByRole("tab", { name: "研发管线" }).click();
  await expect(page).toHaveURL(/section=pipeline/);
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  const drugProgramProgress = page.getByRole("table", { name: "药物适应症与地区进度" });
  await expect(drugProgramProgress).toContainText(`Browser regulatory indication ${fixtureKeyBase}`);
  await expect(drugProgramProgress).toContainText("II 期临床");
  await expect(drugProgramProgress).toContainText("I 期临床");
  await expect(drugProgramProgress).toContainText("在研");
  await expect(drugProgramProgress).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  const drugProgramRights = page.getByRole("table", { name: "药物研发机构与权益" });
  await expect(drugProgramRights).toContainText(`Browser regulatory company ${fixtureKeyBase}`);
  await expect(drugProgramRights).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(drugProgramRights).toContainText("原研 · 中国 · biopharma");
  await expect(drugProgramRights).toContainText("合作研发 · 美国 · biotech");
  await expect(drugProgramRights).toContainText("全球");
  await expect(drugProgramRights).toContainText("大中华区");
  await expect(drugProgramRights).toContainText("First-in-Class");
  await expect(drugProgramRights).toContainText(`Global Phase II first patient in ${fixtureKeyBase}`);
  await drugProgramProgress
    .getByRole("button", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${regulatoryIndicationId}`));
  await expect(
    page.getByRole("heading", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "临床结果与试验" }).click();
  await expect(page).toHaveURL(/section=trials/);
  const drugClinicalResults = page.getByRole("table", { name: "药物临床结果" });
  await expect(drugClinicalResults).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await expect(drugClinicalResults).toContainText("Objective response rate");
  await expect(drugClinicalResults).toContainText("Cohort A: 42 %");
  await expect(drugClinicalResults).toContainText("积极");
  await expect(drugClinicalResults).toContainText("一线");
  await expect(drugClinicalResults).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await expect(drugClinicalResults).toContainText(`Browser combination target ${fixtureKeyBase}`);
  const drugClinicalTrials = page.getByRole("table", { name: "药物关联临床试验" });
  await expect(drugClinicalTrials).toContainText("招募中");
  await expect(drugClinicalTrials).toContainText("申办方发起（IST）");
  await expect(drugClinicalTrials).toContainText(`Browser intervention ${fixtureKeyBase}`);
  await expect(drugClinicalTrials).toContainText(`Browser sponsor ${fixtureKeyBase}`);
  await expect(drugClinicalTrials).toContainText("128");
  await drugClinicalResults
    .getByRole("button", { name: `打开临床试验详情：NCT-E2E-${fixtureKeyBase}` })
    .first()
    .click();
  await expect(page).toHaveURL(new RegExp(`view=trials.*trial=${trialProfileId}`));
  await expect(
    page.getByRole("heading", { name: `Browser clinical trial ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "临床结果与试验" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "交易" }).click();
  await expect(page).toHaveURL(/section=deals/);
  const drugDeals = page.getByRole("table", { name: "药物关联交易" });
  await expect(drugDeals).toContainText(`Browser deal ${fixtureKeyBase}`);
  await expect(drugDeals).toContainText("许可");
  await expect(drugDeals).toContainText("进行中");
  await expect(drugDeals).toContainText("对外许可");
  await expect(drugDeals).toContainText(`Browser regulatory company ${fixtureKeyBase}`);
  await expect(drugDeals).toContainText("许可方 · 美国 · biopharma");
  await expect(drugDeals).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(drugDeals).toContainText("被许可方 · 中国 · biotech");
  await expect(drugDeals).toContainText("交易时 I 期临床 · 当前 II 期临床");
  await expect(drugDeals).toContainText("首付款 USD 25.0M");
  await expect(drugDeals).toContainText("潜在总额 USD 500.0M");
  const drugDealRights = page.getByRole("table", { name: "药物交易权益归属" });
  await expect(drugDealRights).toContainText(`Browser pipeline company B ${fixtureKeyBase}`);
  await expect(drugDealRights).toContainText("商业化");
  await expect(drugDealRights).toContainText("大中华区");
  await expect(drugDealRights).toContainText("独占");
  await expect(drugDealRights).toContainText("Exclusive commercialization rights for the controlled browser asset");
  await drugDeals.getByRole("button", { name: regulatoryDrugName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await expect(page.getByRole("heading", { name: regulatoryDrugName, exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await drugDeals.getByRole("button", { name: `打开交易详情：Browser deal ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=deals.*deal=${dealProfileId}`));
  await expect(page.getByRole("heading", { name: `Browser deal ${fixtureKeyBase}`, exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await drugDealRights
    .getByRole("button", { name: `Browser pipeline company B ${fixtureKeyBase}`, exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineCollaboratorId}`));
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "临床结果与试验" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "药物概览" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).toHaveURL(/view=pipeline/);
  await expect(page).toHaveURL(/milestone_type=first_patient_in/);
  await expect(pipelineTable).toContainText(regulatoryDrugName);

  const regulatoryCompanyName = `Browser regulatory company ${fixtureKeyBase}`;
  await pipelineTable.scrollIntoViewIfNeeded();
  await pipelineTable.getByRole("button", { name: regulatoryCompanyName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineOrganizationId}`));
  await expect(page.getByRole("heading", { name: regulatoryCompanyName, exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "公司专业档案", exact: true })).toBeVisible();
  await expect(
    page
      .locator("dt")
      .filter({ hasText: /^最高阶段$/ })
      .locator(".."),
  ).toContainText("II 期临床");
  await expect(page.getByRole("button", { name: regulatoryDrugName, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "交易" }).click();
  await expect(page).toHaveURL(/section=deals/);
  const companyDeals = page.getByRole("tabpanel");
  await expect(
    companyDeals.getByRole("button", { name: `打开交易详情：Browser deal ${fixtureKeyBase}` }),
  ).toBeVisible();
  const companyDealAsset = companyDeals.getByRole("button", {
    name: new RegExp(`Browser regulatory drug ${fixtureKeyBase} · II期`),
  });
  await expect(companyDealAsset).toBeVisible();
  await companyDealAsset.click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  const companyDealCollaborator = page.getByRole("button", {
    name: new RegExp(`Browser pipeline company B ${fixtureKeyBase} · 被许可方`),
  });
  await expect(companyDealCollaborator).toBeVisible();
  await companyDealCollaborator.click();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineCollaboratorId}`));
  await page.goBack();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.goto(`/workspace/research?view=company&entity=${pipelineOrganizationId}`);
  await expect(page.getByRole("tab", { name: "公司概览" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("tab", { name: "公司时间线" }).click();
  await expect(page).toHaveURL(/section=timeline/);
  await expect(page.getByRole("tab", { name: "公司时间线" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await expect(page.getByRole("tabpanel")).toContainText(regulatoryDrugName);
  await page.reload();
  await expect(page.getByRole("tab", { name: "公司时间线" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page.getByRole("tab", { name: "公司概览" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: regulatoryDrugName, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}`));
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineOrganizationId}`));
  await page.goto(`${pipelineResultsUrl.pathname}${pipelineResultsUrl.search}`);
  await expect(page).toHaveURL(/view=pipeline/);
  await expect(page).toHaveURL(/milestone_type=first_patient_in/);

  await pipelineTable.scrollIntoViewIfNeeded();
  await pipelineTable.getByRole("button", { name: `Browser pipeline target ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}`));
  await expect(
    page.getByRole("heading", { name: `Browser pipeline target ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();

  await page.goto(`/workspace/research?view=regulatory&q=${encodeURIComponent(fixtureKeyBase)}`);
  const regulatoryFilters = page.getByRole("form", { name: "监管事件筛选" });
  await expect(regulatoryFilters.getByLabel("关键词")).toHaveValue(fixtureKeyBase);
  await regulatoryFilters.getByLabel("监管机构").selectOption("FDA");
  await regulatoryFilters.getByLabel("辖区").selectOption("US");
  await regulatoryFilters.getByLabel("事件类型").selectOption("approval");
  await regulatoryFilters.getByLabel("认定资格").selectOption("breakthrough_therapy");
  await regulatoryFilters.getByText("更多监管与安全条件").click();
  await regulatoryFilters.getByLabel("事件状态").selectOption("approved");
  await regulatoryFilters.getByLabel("标签变更").selectOption("initial_label");
  await regulatoryFilters.getByLabel("黑框警告", { exact: true }).selectOption("true");
  await regulatoryFilters.getByLabel("安全信号", { exact: true }).selectOption("adverse_event");
  await regulatoryFilters.getByLabel("严重程度").selectOption("serious");
  await regulatoryFilters.getByLabel("信号状态").selectOption("confirmed");
  const regulatoryDecisionRange = regulatoryFilters.getByRole("group", { name: "决定日期" });
  await regulatoryDecisionRange.getByLabel("起").fill("2026-01-01");
  await regulatoryDecisionRange.getByLabel("止").fill("2026-12-31");
  const regulatorySourceRange = regulatoryFilters.getByRole("group", { name: "来源更新" });
  await regulatorySourceRange.getByLabel("起").fill("2026-01-01");
  await regulatorySourceRange.getByLabel("止").fill("2026-12-31");
  const regulatoryCorrectnessResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/regulatory-event-timeline" &&
      url.searchParams.get("agency") === "FDA" &&
      url.searchParams.get("jurisdiction") === "US" &&
      url.searchParams.get("safety_status") === "confirmed"
    );
  });
  await regulatoryFilters.getByRole("button", { name: "查询", exact: true }).click();
  const regulatoryCorrectnessResponse = await regulatoryCorrectnessResponsePromise;
  const regulatoryCorrectnessPayload = (await regulatoryCorrectnessResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(regulatoryCorrectnessPayload.total).toBe(1);
  expect(regulatoryCorrectnessPayload.items.map((item) => item.id)).toEqual([regulatoryEventId]);
  expect(regulatoryCorrectnessPayload.items.some((item) => item.id === regulatoryNegativeEventId)).toBe(false);
  await expect(page).toHaveURL(/designation_type=breakthrough_therapy/);
  await expect(page).toHaveURL(/label_change_type=initial_label/);
  await expect(page).toHaveURL(/boxed_warning=true/);
  await expect(page).toHaveURL(/safety_signal_type=adverse_event/);
  await expect(page).toHaveURL(/safety_severity=serious/);
  await expect(page).toHaveURL(/safety_status=confirmed/);
  await expect(page).toHaveURL(/decision_from=2026-01-01/);
  await expect(page.getByRole("table", { name: "监管事件结果" })).toContainText(
    `Browser regulatory event ${fixtureKeyBase}`,
  );
  const regulatorySubscriptionName = `Browser regulatory subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const saveRegulatoryForm = page.getByRole("dialog", { name: "保存当前监管检索" });
  await saveRegulatoryForm.getByLabel("名称").fill(regulatorySubscriptionName);
  await saveRegulatoryForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("监管检索已保存并启用监控")).toBeVisible();
  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedRegulatoryRow = page.getByRole("row").filter({ hasText: regulatorySubscriptionName });
  await expect(savedRegulatoryRow).toContainText("监管与安全");
  await savedRegulatoryRow.getByRole("button", { name: `运行 ${regulatorySubscriptionName}` }).click();
  await expect(page).toHaveURL(/view=regulatory/);
  await expect(page).toHaveURL(/designation_type=breakthrough_therapy/);
  await expect(page).toHaveURL(/label_change_type=initial_label/);
  await expect(page).toHaveURL(/boxed_warning=true/);
  await expect(page).toHaveURL(/safety_signal_type=adverse_event/);
  await expect(page).toHaveURL(/safety_severity=serious/);
  await expect(page).toHaveURL(/safety_status=confirmed/);
  await expect(page).toHaveURL(/decision_from=2026-01-01/);
  await expect(page).toHaveURL(/decision_to=2026-12-31/);
  await expect(page).toHaveURL(/source_updated_from=2026-01-01/);
  await expect(page).toHaveURL(/source_updated_to=2026-12-31/);
  await page.reload();
  await expect(regulatoryFilters.getByLabel("认定资格")).toHaveValue("breakthrough_therapy");
  await expect(page.getByRole("table", { name: "监管事件结果" })).toContainText(
    `Browser regulatory event ${fixtureKeyBase}`,
  );
  await page.getByLabel(`选择对比 Browser regulatory event ${fixtureKeyBase}`).click();
  await expect(page).toHaveURL(/compare=[0-9a-f-]{36}/);
  await expect(page.getByText("已选 1/4 项", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "监管事件对比" })).toContainText("Interstitial lung disease");
  await page
    .getByRole("table", { name: "监管事件对比" })
    .getByRole("button", { name: `Browser regulatory drug ${fixtureKeyBase}` })
    .click();
  await expect(page).toHaveURL(/regulatory_event=[0-9a-f-]{36}/);
  await expect(page.getByRole("dialog", { name: `Browser regulatory event ${fixtureKeyBase}` })).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("Monitor pulmonary symptoms");
  await page.reload();
  await expect(page.getByRole("dialog", { name: `Browser regulatory event ${fixtureKeyBase}` })).toBeVisible();
  await expect(regulatoryFilters.getByLabel("认定资格")).toHaveValue("breakthrough_therapy");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("dialog").getByRole("button", { name: "关闭监管事件详情" }).click();
  await page.getByRole("button", { name: "清除已选项" }).click();
  await expect(page).not.toHaveURL(/compare=/);
  await expect(page.getByRole("table", { name: "监管事件对比" })).toHaveCount(0);

  await page.goto(`/workspace/research?view=entity&entity=${regulatorySubjectId}&section=regulatory_events`);
  await expect(page.getByRole("heading", { name: `Browser regulatory drug ${fixtureKeyBase}` })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}.*section=regulatory`));
  await expect(page.getByRole("tab", { name: "获批与监管" })).toHaveAttribute("aria-selected", "true");
  const approvedIndications = page.getByRole("table", { name: "药物获批适应症" });
  await expect(approvedIndications).toContainText(`Browser regulatory indication ${fixtureKeyBase}`);
  await expect(approvedIndications).toContainText("Adults with biomarker-positive disease");
  await expect(approvedIndications).toContainText("EGFR exon 20 insertion");
  await expect(approvedIndications).toContainText("美国");
  await expect(approvedIndications).toContainText("二线");
  await expect(approvedIndications).toContainText("口服");
  await expect(approvedIndications).toContainText("片剂");
  await approvedIndications
    .getByRole("button", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${regulatoryIndicationId}`));
  await expect(
    page.getByRole("heading", { name: `Browser regulatory indication ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("tab", { name: "获批与监管" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: `打开监管事件详情：Browser regulatory event ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=regulatory.*regulatory_event=${regulatoryEventId}`));
  await expect(page.getByRole("dialog", { name: `Browser regulatory event ${fixtureKeyBase}` })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "关闭监管事件详情" }).click();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=drug&entity=${regulatorySubjectId}.*section=regulatory`));
  await expect(page.getByRole("tab", { name: "获批与监管" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${pipelineOrganizationId}&section=programs`);
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${pipelineOrganizationId}.*section=pipeline`));
  await expect(page.getByRole("heading", { name: regulatoryCompanyName, exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "研发管线" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${dealEntityId}&section=deals`);
  await expect(page.getByRole("heading", { name: `Browser deal ${fixtureKeyBase}`, exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: /打开交易详情/ }).click();
  await expect(page).toHaveURL(new RegExp(`view=deals.*deal=${dealProfileId}`));
  await expect(page.getByRole("heading", { name: `Browser deal ${fixtureKeyBase}`, exact: true })).toBeVisible();
  await expect(page.getByText(/交易专业档案/)).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=entity&entity=${dealEntityId}.*section=deals`));
  await expect(page.getByRole("tab", { name: "交易" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=target&entity=${pipelineTargetId}&section=patents`);
  await expect(page.getByRole("heading", { name: `Browser pipeline target ${fixtureKeyBase}` })).toBeVisible();
  await expect(page.getByRole("tab", { name: "专利" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: `打开专利族详情：WO-E2E-${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=patents.*patent=${patentFamilyId}`));
  await expect(page.getByRole("heading", { name: `Browser patent family ${fixtureKeyBase}` })).toBeVisible();
  await expect(page.getByText(`专利族专业档案 · WO-E2E-${fixtureKeyBase}`)).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}.*section=patents`));
  await expect(page.getByRole("tab", { name: "专利" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=target&entity=${pipelineTargetId}&section=news`);
  await expect(page.getByRole("tab", { name: "新闻与会议" })).toHaveAttribute("aria-selected", "true");
  await page.getByRole("button", { name: `打开新闻事件详情：Browser news event ${fixtureKeyBase}` }).click();
  await expect(page).toHaveURL(new RegExp(`view=news.*news_event=${newsEventId}`));
  const newsDialog = page.getByRole("dialog", { name: `Browser news event ${fixtureKeyBase}` });
  const closeNewsDialog = newsDialog.getByRole("button", { name: "关闭新闻事件详情" });
  await expect(closeNewsDialog).toBeFocused();
  const newsProvenanceTrigger = newsDialog.getByRole("button", {
    name: `查看 Browser news event ${fixtureKeyBase} 的原始证据`,
  });
  await newsProvenanceTrigger.click();
  const provenanceDialog = page.getByRole("dialog", { name: "原始证据" });
  await expect(provenanceDialog.getByRole("button", { name: "关闭原始证据" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(provenanceDialog).toHaveCount(0);
  await expect(newsDialog).toBeVisible();
  await expect(newsProvenanceTrigger).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(newsDialog).toHaveCount(0);
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}.*section=news`));
  await expect(page.getByRole("tab", { name: "新闻与会议" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${createdCompany.id}`);
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${createdCompany.id}`));
  await expect(page.getByRole("heading", { name: companyName, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "研发管线" }).click();
  await expect(page.getByText("暂无关联研发管线", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "公司时间线" }).click();
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await expect(page.getByText("暂无带日期的公司事件", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.goto("/workspace/internal");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page).toHaveURL(/\/workspace\/internal/);
  await expect(page.getByRole("heading", { name: "自动数据工厂" })).toBeVisible();
  await openNavigation(page);
  const internalNavigation = page.getByRole("navigation", { name: "主导航" });
  for (const researchView of [
    "用户中心",
    "情报检索",
    "结构检索",
    "靶点全景",
    "原始证据",
    "知识专题",
    "监控与提醒",
    "对比与列表",
  ]) {
    await expect(internalNavigation.getByRole("button", { name: researchView, exact: true })).toHaveCount(0);
  }
  await page.getByRole("button", { name: "数据工厂", exact: true }).click();
  await expect(page.getByRole("heading", { name: "自动数据工厂" })).toBeVisible();
  const quarantineFile = `browser-quarantine-${testInfo.project.name}.md`;
  const quarantineRow = page.getByRole("row").filter({ hasText: quarantineFile });
  await expect(quarantineRow.getByText("Win.Test.EICAR_HDB-1")).toBeVisible();
  await quarantineRow.getByRole("button", { name: "处置" }).click();
  const quarantineDialog = page.getByRole("dialog", { name: "隔离案件处置" });
  await expect(quarantineDialog).toBeVisible();
  await expect(quarantineDialog.getByText(/仍强制经过 ClamAV/)).toBeVisible();
  await expect(quarantineDialog.getByText("扫描发现威胁")).toBeVisible();
  await expect(quarantineDialog.getByLabel("处置动作")).toHaveValue("hold");
  await quarantineDialog.getByLabel("处置原因").fill(`Browser security hold ${testInfo.project.name}`);
  const quarantineResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/admin/quarantine-cases/${quarantineVersionId}/decisions`) &&
      response.request().method() === "POST",
  );
  await quarantineDialog.getByRole("button", { name: "提交处置" }).click();
  const quarantineResponse = await quarantineResponsePromise;
  expect(quarantineResponse.status()).toBe(200);
  expect(await quarantineResponse.json()).toMatchObject({
    source_version_id: quarantineVersionId,
    action: "hold",
    quarantine_status: "held",
    quarantine_version: 2,
  });
  await expect(quarantineDialog.getByText("处置已记录：留置待审")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  const closeQuarantine = quarantineDialog.getByRole("button", { name: "关闭隔离案件" });
  await expect(closeQuarantine).toBeEnabled();
  await closeQuarantine.click();
  const replayWorkflow = `browser-replay-${fixtureKeyBase}-${testInfo.project.name}`;
  const replayRow = await findDataFactoryRunRow(page, replayWorkflow);
  await replayRow.getByRole("button", { name: "运行详情" }).click();
  await expect(page.getByRole("heading", { name: "逐阶段运行图" })).toBeVisible();
  await expect(page.getByText("发现", { exact: true })).toBeVisible();
  await expect(page.getByText("安全扫描", { exact: true })).toBeVisible();
  await expect(page.getByText("AI 治理", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  const recoveryFile = `browser-recovery-${testInfo.project.name}.md`;
  const recoveryAssetRow = await findSourceAssetRow(page, recoveryFile);
  await recoveryAssetRow.getByRole("button", { name: `查看 ${recoveryFile} 版本` }).click();
  const sourceAssetDialog = page.getByRole("dialog", { name: recoveryFile });
  await expect(sourceAssetDialog).toBeVisible();
  await page.getByRole("button", { name: "选择恢复阶段" }).click();
  const stageReplayDialog = page.getByRole("dialog", { name: "重放源版本 1" });
  await expect(stageReplayDialog.getByLabel("恢复起点")).toHaveValue("parse");
  await expect(stageReplayDialog.getByRole("option", { name: "安全扫描" })).toHaveCount(1);
  await expect(stageReplayDialog.getByRole("option", { name: "文档解析" })).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await stageReplayDialog.getByRole("button", { name: "关闭" }).click();
  await sourceAssetDialog.getByRole("button", { name: "关闭源对象详情" }).click();
  const replayResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/admin/ingestion-runs/${ingestionRunId}/replay`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: `重放 ${replayWorkflow}` }).click();
  await page.getByLabel("重放原因").fill(`Browser recovery ${testInfo.project.name}`);
  await page.getByRole("button", { name: "确认重放" }).click();
  const replayResponse = await replayResponsePromise;
  expect(replayResponse.status()).toBe(202);
  await expect(page.getByRole("dialog", { name: "重放入库运行" })).toHaveCount(0);
  await page.getByRole("button", { name: "接入自动数据源" }).click();
  await expect(page.getByLabel("授权生效时间")).toBeVisible();
  await expect(page.getByLabel("授权结束时间（留空表示长期有效）")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("http_manifest");
  await expect(page.getByLabel("Manifest API 地址")).toBeVisible();
  await expect(page.getByLabel("凭据引用")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("s3_snapshot");
  await expect(page.getByLabel("S3 Bucket / Prefix")).toHaveValue("s3://licensed-supplier/research/");
  await expect(page.getByPlaceholder("env://SUPPLIER_S3_CREDENTIALS_JSON")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("sftp_snapshot");
  await expect(page.getByLabel("SFTP 目录地址")).toHaveValue("sftp://supplier.example:22/delivery/");
  await expect(page.getByPlaceholder("env://SUPPLIER_SFTP_CREDENTIALS_JSON")).toBeVisible();
  await page.getByLabel("数据源类型").selectOption("smb_snapshot");
  await expect(page.getByLabel("SMB 共享目录地址")).toHaveValue("smb://fileserver.example:445/research/delivery/");
  await expect(page.getByPlaceholder("env://ENTERPRISE_SMB_CREDENTIALS_JSON")).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();

  await openNavigation(page);
  const governanceRunsResponse = page.waitForResponse(
    (response) => response.url().includes("/api/v1/governance/runs") && response.request().method() === "GET",
  );
  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "AI 审核" }).click();
  await expect(page.getByRole("heading", { name: "AI 信息审核" })).toBeVisible();
  await page.getByText("批次发布与撤回", { exact: true }).click();
  const publicationQuote = `Browser publication evidence ${fixtureKeyBase} ${testInfo.project.name}`;
  const publicationFact = page.locator(".publication-fact-list label").filter({ hasText: publicationQuote });
  await expect(publicationFact).toBeVisible();
  await publicationFact.getByRole("checkbox").check();
  await page.getByRole("textbox", { name: "批次审核依据" }).fill(`Browser publication ${testInfo.project.name}`);
  const publicationPreviewResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/governance/publication-batches/preview") &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().operation === "publish",
  );
  await page.getByRole("button", { name: "生成发布预览 (1)" }).click();
  const publicationPreviewResponse = await publicationPreviewResponsePromise;
  expect(publicationPreviewResponse.status()).toBe(201);
  const publicationPreview = (await publicationPreviewResponse.json()) as {
    id: string;
    operation: string;
    preview_sha256: string;
    status: string;
  };
  expect(publicationPreview).toMatchObject({ operation: "publish", status: "previewed" });
  expect(publicationPreview.preview_sha256).toMatch(/^[0-9a-f]{64}$/);
  const publicationCommitResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/publication-batches/${publicationPreview.id}/commit`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "原子提交发布" }).click();
  const publicationCommitResponse = await publicationCommitResponsePromise;
  expect(publicationCommitResponse.status()).toBe(200);
  expect(await publicationCommitResponse.json()).toMatchObject({
    id: publicationPreview.id,
    operation: "publish",
    status: "committed",
  });
  await page
    .getByRole("textbox", { name: "批次审核依据" })
    .fill(`Browser withdrawal correction ${testInfo.project.name}`);
  const withdrawalPreviewResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/governance/publication-batches/preview") &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().operation === "withdraw",
  );
  await page.getByRole("button", { name: "基于此批次生成撤回预览" }).click();
  const withdrawalPreviewResponse = await withdrawalPreviewResponsePromise;
  expect(withdrawalPreviewResponse.status()).toBe(201);
  const withdrawalPreview = (await withdrawalPreviewResponse.json()) as {
    id: string;
    operation: string;
    blocked_count: number;
    status: string;
  };
  expect(withdrawalPreview).toMatchObject({
    operation: "withdraw",
    blocked_count: 0,
    status: "previewed",
  });
  const withdrawalCommitResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/publication-batches/${withdrawalPreview.id}/commit`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "原子提交撤回" }).click();
  const withdrawalCommitResponse = await withdrawalCommitResponsePromise;
  expect(withdrawalCommitResponse.status()).toBe(200);
  expect(await withdrawalCommitResponse.json()).toMatchObject({
    id: withdrawalPreview.id,
    operation: "withdraw",
    status: "committed",
  });
  await expect(page.getByText("检索投影维护", { exact: true })).toHaveCount(0);
  await expect(publicationFact).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("tab", { name: /实体消歧/ }).click();
  await page.getByRole("tab", { name: /历史与回滚/ }).click();
  const resolutionSourceName = `Browser resolution alias ${testInfo.project.name}`;
  const resolutionCaseRow = page.getByRole("button").filter({ hasText: resolutionSourceName });
  await expect(resolutionCaseRow).toBeVisible();
  await resolutionCaseRow.click();
  await expect(page.getByRole("heading", { name: "跨域影响分析" })).toBeVisible();
  await expect(page.getByText("target_profiles.entity_id", { exact: true })).toBeVisible();
  await expect(page.getByText("不可变决策历史", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "拆分恢复依据" }).fill(`Browser rollback ${testInfo.project.name}`);
  const rollbackResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/entity-resolution-cases/${resolutionCaseId}/decision`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "拆分并恢复独立实体" }).click();
  const rollbackResponse = await rollbackResponsePromise;
  expect(rollbackResponse.status()).toBe(200);
  expect(await rollbackResponse.json()).toMatchObject({ id: resolutionCaseId, status: "reverted" });
  await expect(page.getByText("拆分恢复", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("tab", { name: "质量运营" }).click();
  await expect(page.getByRole("heading", { name: "数据质量运营" })).toBeVisible();
  await expect(page.locator(".quality-metric-grid article")).toHaveCount(6);
  await expect(page.getByRole("heading", { name: "最近 12 次趋势" })).toBeVisible();
  const qualityIssueTitle = `Browser quality issue ${fixtureKey}`;
  const qualityIssue = page.locator(".quality-issue-list button").filter({ hasText: qualityIssueTitle });
  await expect(qualityIssue).toBeVisible();
  await qualityIssue.click();
  await expect(page.getByRole("heading", { name: qualityIssueTitle })).toBeVisible();
  await page.getByLabel("负责人").selectOption(qualityOwnerId);
  const assignmentResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/quality/issues/${qualityIssueId}/actions`) &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().action === "assign",
  );
  await page.getByRole("button", { name: "分配", exact: true }).click();
  const assignmentResponse = await assignmentResponsePromise;
  expect(assignmentResponse.status()).toBe(200);
  expect(await assignmentResponse.json()).toMatchObject({
    id: qualityIssueId,
    owner_user_id: qualityOwnerId,
    status: "open",
  });
  const acknowledgeResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/v1/governance/quality/issues/${qualityIssueId}/actions`) &&
      response.request().method() === "POST" &&
      response.request().postDataJSON().action === "acknowledge",
  );
  await page.getByRole("button", { name: "确认接手", exact: true }).click();
  const acknowledgeResponse = await acknowledgeResponsePromise;
  expect(acknowledgeResponse.status()).toBe(200);
  expect(await acknowledgeResponse.json()).toMatchObject({ id: qualityIssueId, status: "acknowledged" });
  await expect(page.locator(".quality-event-history")).toContainText("assign");
  await expect(page.locator(".quality-event-history")).toContainText("acknowledge");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  await page.getByRole("tab", { name: "运行追踪" }).click();
  expect((await governanceRunsResponse).status()).toBe(200);
  await expect(page.getByLabel("运行状态")).toBeVisible();
  await expect(page.getByText(/共 \d+ 次运行/)).toBeVisible();
  const overflowingElements = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    return Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const bounds = element.getBoundingClientRect();
        return {
          tag: element.tagName.toLowerCase(),
          className: element.className,
          left: Math.round(bounds.left),
          right: Math.round(bounds.right),
          width: Math.round(bounds.width),
        };
      })
      .filter(({ right }) => right > viewportWidth + 1)
      .slice(0, 20);
  });
  expect(overflowingElements).toEqual([]);

  await page.goto("/workspace/research?view=overview");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("research");
  await expect(page).toHaveURL(/\/workspace\/research/);
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();
  await expect(page.getByLabel("邮箱", { exact: true })).toHaveValue(credentials.email);
  await page.goto(`/workspace/research?view=target&entity=${pipelineTargetId}`);
  await expect(page).toHaveURL(new RegExp(`view=target&entity=${pipelineTargetId}`));
  await page.goBack();
  await expect(page.getByRole("heading", { name: "用户中心" })).toBeVisible();
  await page.goto("/workspace/research?view=knowledge");
  await expect(page.getByRole("heading", { name: "版本化知识专题" })).toBeVisible();

  await page.goto("/workspace/research?view=evidence");
  await expect(page.getByRole("heading", { name: "原始资料查证" })).toBeVisible();
  await page.getByPlaceholder("输入靶点、活性值、专利号、试验号或项目事实").fill(`No evidence ${fixtureKey}`);
  await page.getByRole("button", { name: "查证原文" }).click();
  await expect(page.getByText("未找到匹配证据", { exact: true })).toBeVisible();

  await page.goto("/workspace/internal");
  await expect(page).toHaveURL(/\/workspace\/internal/);
  await openNavigation(page);
  await page.getByRole("button", { name: "商业运营" }).click();
  await expect(page.getByRole("heading", { name: "Agent 商业运营" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "合同与额度" })).toBeVisible();
  await page.getByRole("tab", { name: "导出策略" }).click();
  await expect(page.getByText("工作台导出策略", { exact: true })).toBeVisible();
  await expect(page.getByLabel("策略版本")).toBeVisible();
  await page.getByRole("tab", { name: "数据生命周期" }).click();
  await expect(page.getByRole("heading", { name: "导出对象保留策略" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "源资料保留策略" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "创建法律保全" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "法律保全记录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "源资料撤回候选" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "已撤回源资料" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "到期导出对象" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "生命周期审计" })).toBeVisible();
  await page.getByRole("tab", { name: "Agent 客户端" }).click();
  await expect(page.getByRole("columnheader", { name: "客户端" })).toBeVisible();
  await page.getByRole("tab", { name: "账单投递" }).click();
  await expect(page.getByRole("heading", { name: "计费账户映射" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Provider 投递队列" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Provider 客户编号" })).toBeVisible();
  await page.getByLabel("投递状态").selectOption("dead");
  await expect(page.getByLabel("投递状态")).toHaveValue("dead");
  await expect(page.getByRole("columnheader", { name: "最近错误" })).toBeVisible();
  await page.getByRole("tab", { name: "计费争议" }).click();
  await expect(page.getByRole("heading", { name: "计费争议案件" })).toBeVisible();
  await expect(page.getByLabel("争议状态")).toHaveValue("all");
  await expect(page.getByRole("columnheader", { name: "争议额度" })).toBeVisible();
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[professional-error-permission-matrix] fails safely and recovers every professional query domain", async ({
  page,
}, testInfo) => {
  testInfo.setTimeout(180_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const pipelineTargetId = process.env.E2E_PIPELINE_TARGET_ID;
  const regulatorySubjectId = process.env.E2E_REGULATORY_SUBJECT_ID;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  test.skip(
    !credentials || !fixtureKeyBase || !pipelineTargetId || !regulatorySubjectId || !epidemiologyDiseaseId,
    "Authenticated browser fixture credentials and governed professional entities are required",
  );
  if (!credentials || !fixtureKeyBase || !pipelineTargetId || !regulatorySubjectId || !epidemiologyDiseaseId) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const domains: Array<{ endpoint: string; resultSurface: () => Locator; url: string }> = [
    {
      endpoint: "/api/v1/entities",
      resultSurface: () => page.getByRole("table", { name: "实体检索结果" }),
      url: `/workspace/research?view=explorer&q=${encodeURIComponent(fixtureKeyBase)}`,
    },
    {
      endpoint: "/api/v1/pipelines",
      resultSurface: () => page.getByRole("table", { name: "药物与研发管线结果" }),
      url: `/workspace/research?view=pipeline&target_entity_id=${pipelineTargetId}`,
    },
    {
      endpoint: "/api/v1/trials",
      resultSurface: () => page.getByRole("table", { name: "临床试验结果" }),
      url: `/workspace/research?view=trials&investigational_drug_entity_ids=${regulatorySubjectId}`,
    },
    {
      endpoint: "/api/v1/patent-families",
      resultSurface: () => page.getByRole("table", { name: "专利族结果" }),
      url: `/workspace/research?view=patents&q=${encodeURIComponent(fixtureKeyBase)}`,
    },
    {
      endpoint: "/api/v1/deal-transactions",
      resultSurface: () => page.getByRole("table", { name: "交易结果" }),
      url: `/workspace/research?view=deals&asset_entity_id=${regulatorySubjectId}`,
    },
    {
      endpoint: "/api/v1/regulatory-event-timeline",
      resultSurface: () => page.getByRole("table", { name: "监管事件结果" }),
      url: `/workspace/research?view=regulatory&entity_id=${regulatorySubjectId}`,
    },
    {
      endpoint: "/api/v1/epidemiology-observations",
      resultSurface: () => page.getByRole("table", { name: "流行病学结果" }),
      url: `/workspace/research?view=epidemiology&disease_entity_id=${epidemiologyDiseaseId}`,
    },
    {
      endpoint: "/api/v1/news-events",
      resultSurface: () => page.getByRole("region", { name: "研究发布时间线" }),
      url: `/workspace/research?view=news&entity_id=${pipelineTargetId}&display=timeline`,
    },
  ];

  for (const domain of domains) {
    await page.goto(domain.url);
    const resultSurface = domain.resultSurface();
    await expect(resultSurface).toContainText(fixtureKeyBase, { timeout: 15_000 });
    await verifyProfessionalErrorPermissionLifecycle({
      page,
      endpoint: domain.endpoint,
      resultSurface,
    });
  }
});

test("[clinical-normalized-drug-or][clinical-role-groups][clinical-role-correctness][clinical-linked-program-correctness] combines normalized trial roles and linked drug attributes without cross-program matches", async ({
  page,
}, testInfo) => {
  testInfo.setTimeout(60_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const regulatorySubjectId = process.env.E2E_REGULATORY_SUBJECT_ID;
  const pipelineDrugBId = process.env.E2E_PIPELINE_DRUG_B_ID;
  const pipelineTargetId = process.env.E2E_PIPELINE_TARGET_ID;
  const pipelineCombinationTargetId = process.env.E2E_PIPELINE_COMBINATION_TARGET_ID;
  const trialProfileId = process.env.E2E_TRIAL_PROFILE_ID;
  const trialNegativeProfileId = process.env.E2E_TRIAL_NEGATIVE_PROFILE_ID;
  test.skip(
    !credentials ||
      !fixtureKeyBase ||
      !regulatorySubjectId ||
      !pipelineDrugBId ||
      !pipelineTargetId ||
      !pipelineCombinationTargetId ||
      !trialProfileId ||
      !trialNegativeProfileId,
    "Authenticated browser fixture credentials and normalized clinical role IDs are required",
  );
  if (
    !credentials ||
    !fixtureKeyBase ||
    !regulatorySubjectId ||
    !pipelineDrugBId ||
    !pipelineTargetId ||
    !pipelineCombinationTargetId ||
    !trialProfileId ||
    !trialNegativeProfileId
  )
    return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await page.goto(
    `/workspace/research?view=trials&investigational_drug_entity_ids=${regulatorySubjectId}` +
      `&combination_drug_entity_ids=${pipelineDrugBId}` +
      `&investigational_target_entity_ids=${pipelineTargetId}` +
      `&combination_target_entity_ids=${pipelineCombinationTargetId}`,
  );
  const clinicalFilters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(clinicalFilters).toContainText(`Browser regulatory drug ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser combination target ${fixtureKeyBase}`);
  const roleComboboxes = clinicalFilters.locator('input[role="combobox"][aria-controls*="-multi-filter-options-"]');
  const roleListboxes = await roleComboboxes.evaluateAll((inputs) =>
    inputs.map((input) => input.getAttribute("aria-controls")),
  );
  expect(roleListboxes.every(Boolean)).toBe(true);
  expect(new Set(roleListboxes).size).toBe(roleListboxes.length);
  const investigationalDrugCombobox = clinicalFilters.getByLabel("试验药物（任一）筛选");
  await investigationalDrugCombobox.fill(`Browser antibody alias ${fixtureKeyBase}`);
  const disambiguatedCandidate = clinicalFilters.getByRole("option", {
    name: new RegExp(`Browser pipeline antibody ${fixtureKeyBase}`),
  });
  await expect(disambiguatedCandidate).toContainText("别名精确命中");
  await expect(disambiguatedCandidate).toContainText(`Browser antibody alias ${fixtureKeyBase}`);
  await expect(disambiguatedCandidate).toContainText(`英文名 Browser Antibody ${fixtureKeyBase}`);
  await expect(disambiguatedCandidate).toContainText("创新类型 First-in-class");
  await expect(disambiguatedCandidate).toContainText("Modality Monoclonal antibody");
  await investigationalDrugCombobox.press("ArrowDown");
  await expect(investigationalDrugCombobox).toBeFocused();
  await expect(disambiguatedCandidate).toHaveAttribute("aria-selected", "true");
  const disambiguatedCandidateId = await disambiguatedCandidate.getAttribute("id");
  expect(disambiguatedCandidateId).toBeTruthy();
  await expect(investigationalDrugCombobox).toHaveAttribute("aria-activedescendant", disambiguatedCandidateId ?? "");
  await investigationalDrugCombobox.press("Enter");
  await expect(clinicalFilters).toContainText(`Browser pipeline antibody ${fixtureKeyBase}`);
  const normalizedRoleGroupResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    const investigationalDrugIds = url.searchParams.getAll("investigational_drug_entity_ids");
    return (
      url.pathname === "/api/v1/trials" &&
      investigationalDrugIds.length === 2 &&
      investigationalDrugIds.includes(regulatorySubjectId) &&
      investigationalDrugIds.includes(pipelineDrugBId) &&
      url.searchParams.get("combination_drug_entity_ids") === pipelineDrugBId &&
      url.searchParams.get("investigational_target_entity_ids") === pipelineTargetId &&
      url.searchParams.get("combination_target_entity_ids") === pipelineCombinationTargetId
    );
  });
  await clinicalFilters.getByRole("button", { name: "查询", exact: true }).click();
  const roleGroupResponse = await normalizedRoleGroupResponse;
  const roleGroupPayload = (await roleGroupResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(roleGroupPayload.total).toBe(1);
  expect(roleGroupPayload.items.map((item) => item.id)).toEqual([trialProfileId]);
  expect(roleGroupPayload.items.some((item) => item.id === trialNegativeProfileId)).toBe(false);
  await expect(page).toHaveURL(/investigational_drug_entity_ids=.*investigational_drug_entity_ids=/);
  await expect(page).toHaveURL(/combination_drug_entity_ids=/);
  await expect(page).toHaveURL(/investigational_target_entity_ids=/);
  await expect(page).toHaveURL(/combination_target_entity_ids=/);
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await page.reload();
  await expect(clinicalFilters).toContainText(`Browser regulatory drug ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser pipeline antibody ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser combination target ${fixtureKeyBase}`);

  const linkedProgramQuery = new URLSearchParams({ view: "trials" });
  linkedProgramQuery.append("investigational_drug_entity_ids", regulatorySubjectId);
  linkedProgramQuery.append("investigational_drug_entity_ids", pipelineDrugBId);
  linkedProgramQuery.set("combination_drug_entity_ids", pipelineDrugBId);
  linkedProgramQuery.set("investigational_target_entity_ids", pipelineTargetId);
  linkedProgramQuery.set("combination_target_entity_ids", pipelineCombinationTargetId);
  linkedProgramQuery.set("linked_drug_modality", "antibody");
  linkedProgramQuery.set("linked_drug_program_tag", "best_in_class");
  linkedProgramQuery.set("linked_drug_global_phase", "phase_3");
  linkedProgramQuery.set("linked_drug_organization_country_region", "US");
  const linkedPositiveResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      url.searchParams.get("linked_drug_modality") === "antibody" &&
      url.searchParams.get("linked_drug_program_tag") === "best_in_class" &&
      url.searchParams.get("linked_drug_global_phase") === "phase_3" &&
      url.searchParams.get("linked_drug_organization_country_region") === "US"
    );
  });
  await page.goto(`/workspace/research?${linkedProgramQuery.toString()}`);
  const linkedPositivePayload = (await (await linkedPositiveResponse).json()) as {
    total: number;
    items: Array<{ id: string }>;
    query_schema_version: string;
  };
  expect(linkedPositivePayload.query_schema_version).toBe("pharma.clinical_trial.search.v10");
  expect(linkedPositivePayload.total).toBe(1);
  expect(linkedPositivePayload.items.map((item) => item.id)).toEqual([trialProfileId]);
  const linkedProgramFilters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(linkedProgramFilters.locator("details.trial-linked-program-filters")).toHaveAttribute("open", "");
  await expect(linkedProgramFilters.getByLabel("全球最高阶段")).toHaveValue("phase_3");
  await expect(linkedProgramFilters.getByLabel("研发机构国家/地区")).toHaveValue("US");
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await page.reload();
  await expect(linkedProgramFilters.getByLabel("全球最高阶段")).toHaveValue("phase_3");
  await expect(linkedProgramFilters.getByLabel("研发机构国家/地区")).toHaveValue("US");

  linkedProgramQuery.set("linked_drug_program_tag", "first_in_class");
  linkedProgramQuery.delete("linked_drug_global_phase");
  linkedProgramQuery.delete("linked_drug_organization_country_region");
  const linkedNegativeResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      url.searchParams.get("linked_drug_modality") === "antibody" &&
      url.searchParams.get("linked_drug_program_tag") === "first_in_class"
    );
  });
  await page.goto(`/workspace/research?${linkedProgramQuery.toString()}`);
  const linkedNegativePayload = (await (await linkedNegativeResponse).json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(linkedNegativePayload.total).toBe(0);
  expect(linkedNegativePayload.items).toEqual([]);
  await expect(page.getByText("未观察到匹配试验")).toBeVisible();
});

test("[pipeline-drug-entity-filter] keyboard-disambiguates one governed drug into a stable exact pipeline query", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const pipelineDrugId = process.env.E2E_PIPELINE_DRUG_B_ID;
  test.skip(
    !credentials || !fixtureKeyBase || !pipelineDrugId,
    "Authenticated browser fixture credentials and a governed pipeline drug are required",
  );
  if (!credentials || !fixtureKeyBase || !pipelineDrugId) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  await page.goto("/workspace/research?view=pipeline");
  const filters = page.getByRole("form", { name: "药物与管线筛选" });
  const entityComboboxes = filters.getByRole("combobox");
  const controlledListboxes = await entityComboboxes.evaluateAll((inputs) =>
    inputs.map((input) => input.getAttribute("aria-controls")),
  );
  expect(controlledListboxes.every(Boolean)).toBe(true);
  expect(new Set(controlledListboxes).size).toBe(controlledListboxes.length);

  const drugName = `Browser pipeline antibody ${fixtureKeyBase}`;
  const drugCombobox = filters.getByRole("combobox", { name: "药品筛选" });
  await drugCombobox.fill(drugName);
  const candidateOptions = page.getByRole("listbox").getByRole("option");
  await expect(candidateOptions.filter({ hasText: drugName })).toHaveCount(1);
  const optionLabels = await candidateOptions.allTextContents();
  const candidateIndex = optionLabels.findIndex((label) => label.includes(drugName));
  expect(candidateIndex).toBeGreaterThanOrEqual(0);
  for (let index = 0; index <= candidateIndex; index += 1) {
    await drugCombobox.press("ArrowDown");
  }
  const selectedOption = candidateOptions.nth(candidateIndex);
  const selectedOptionId = await selectedOption.getAttribute("id");
  expect(selectedOptionId).toBeTruthy();
  await expect(selectedOption).toHaveAttribute("aria-selected", "true");
  await expect(drugCombobox).toHaveAttribute("aria-activedescendant", selectedOptionId ?? "");
  await drugCombobox.press("Enter");
  await expect(filters.getByRole("group", { name: "药品规范实体筛选" })).toContainText(drugName);

  const exactDrugResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === "/api/v1/pipelines" && url.searchParams.get("drug_entity_id") === pipelineDrugId;
  });
  await filters.getByRole("button", { name: "查询", exact: true }).click();
  const payload = (await (await exactDrugResponse).json()) as {
    total: number;
    items: Array<{ drug_entity_id: string }>;
  };
  expect(payload.total).toBe(1);
  expect(payload.items.map((item) => item.drug_entity_id)).toEqual([pipelineDrugId]);

  await expect(page).toHaveURL(new RegExp(`drug_entity_id=${pipelineDrugId}`));
  await expect(filters.getByRole("group", { name: "药品规范实体筛选" })).toContainText(drugName);
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("药品");
  await expect(page.getByRole("table", { name: "药物与研发管线结果" })).toContainText(drugName);
  await page.reload();
  await expect(filters.getByRole("group", { name: "药品规范实体筛选" })).toContainText(drugName);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
});

test("[clinical-trial-subscription] saves, subscribes and replays the complete applied query", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  test.skip(!credentials || !fixtureKeyBase, "Authenticated browser fixture credentials are required");
  if (!credentials || !fixtureKeyBase) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const query = new URLSearchParams({
    view: "trials",
    q: fixtureKeyBase,
    registry: "ClinicalTrials.gov",
    status: "RECRUITING",
    phase: "PHASE2",
    study_type: "INTERVENTIONAL",
    has_results: "true",
    result_evaluation: "positive",
    results_posted_from: "2026-01-01",
    results_posted_to: "2026-07-31",
    investigational_drug: "VX-101",
    combination_drug: "Pembrolizumab",
    investigational_target: "EGFR",
    combination_target: "PD-1",
    has_key_result: "true",
    publication_id: "PMID:12345678",
    conference: "ASCO 2026",
    disclosed_from: "2026-06-01",
    disclosed_to: "2026-07-31",
    sort: "registry_id:asc",
  });
  await page.goto(`/workspace/research?${query}`);
  await expect(page.getByRole("button", { name: "保存/订阅" })).toBeEnabled();
  const subscriptionName = `Browser trial subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const saveForm = page.getByRole("dialog", { name: "保存当前临床试验检索" });
  await saveForm.getByLabel("名称").fill(subscriptionName);
  await saveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("临床试验检索已保存并启用监控")).toBeVisible();

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const savedRow = page.getByRole("row").filter({ hasText: subscriptionName });
  await expect(savedRow).toContainText("临床试验");
  await savedRow.getByRole("button", { name: `运行 ${subscriptionName}` }).click();
  for (const [name, value] of query.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  const filters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(filters.getByLabel("结果发布", { exact: true })).toHaveValue("true");
  await expect(filters.getByLabel("结果最优评价")).toHaveValue("positive");
  await expect(filters.getByLabel("会议")).toHaveValue("ASCO 2026");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
});

test("[epidemiology-news-subscription][epidemiology-trend-correctness][news-result-correctness] saves, subscribes and replays disease burden and research event queries", async ({
  page,
}, testInfo) => {
  testInfo.setTimeout(90_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  const epidemiologyPatientPopulationId = process.env.E2E_EPIDEMIOLOGY_PATIENT_POPULATION_ID;
  const epidemiologyObservationId = process.env.E2E_EPIDEMIOLOGY_OBSERVATION_ID;
  const epidemiologyComparableObservationId = process.env.E2E_EPIDEMIOLOGY_COMPARABLE_OBSERVATION_ID;
  const epidemiologyIncompatibleObservationId = process.env.E2E_EPIDEMIOLOGY_INCOMPATIBLE_OBSERVATION_ID;
  const newsEventId = process.env.E2E_NEWS_EVENT_ID;
  const newsNegativeEventId = process.env.E2E_NEWS_NEGATIVE_EVENT_ID;
  test.skip(
    !credentials ||
      !fixtureKeyBase ||
      !epidemiologyDiseaseId ||
      !epidemiologyPatientPopulationId ||
      !epidemiologyObservationId ||
      !epidemiologyComparableObservationId ||
      !epidemiologyIncompatibleObservationId ||
      !newsEventId ||
      !newsNegativeEventId,
    "Authenticated browser fixture credentials and epidemiology disease ID are required",
  );
  if (
    !credentials ||
    !fixtureKeyBase ||
    !epidemiologyDiseaseId ||
    !epidemiologyPatientPopulationId ||
    !epidemiologyObservationId ||
    !epidemiologyComparableObservationId ||
    !epidemiologyIncompatibleObservationId ||
    !newsEventId ||
    !newsNegativeEventId
  )
    return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const epidemiologyQuery = new URLSearchParams({
    view: "epidemiology",
    q: fixtureKeyBase,
    disease_entity_id: epidemiologyDiseaseId,
    measure: "prevalence",
    geography: "China",
    unit: "patients",
    patient_population_id: epidemiologyPatientPopulationId,
    population_scope: "adults",
    age_group: "18+",
    sex: "all",
    period_start_from: "2025-01-01",
    period_end_to: "2025-12-31",
    sort: "value:desc",
  });
  await page.goto(`/workspace/research?${epidemiologyQuery}`);
  await expect(page.getByRole("table", { name: "流行病学结果" })).toContainText(
    `Browser epidemiology disease ${fixtureKeyBase}`,
  );
  const trendResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === `/api/v1/epidemiology-trends/${epidemiologyDiseaseId}` &&
      url.searchParams.get("anchor_observation_id") === epidemiologyObservationId
    );
  });
  await page
    .getByRole("table", { name: "流行病学结果" })
    .getByRole("button", { name: `查看 Browser epidemiology disease ${fixtureKeyBase} 同口径趋势` })
    .click();
  const trendResponse = await trendResponsePromise;
  const trendPayload = (await trendResponse.json()) as {
    anchor_observation_id: string | null;
    total: number;
    items: Array<{ id: string }>;
  };
  expect(trendPayload.anchor_observation_id).toBe(epidemiologyObservationId);
  expect(trendPayload.total).toBe(2);
  expect(new Set(trendPayload.items.map((item) => item.id))).toEqual(
    new Set([epidemiologyComparableObservationId, epidemiologyObservationId]),
  );
  expect(trendPayload.items.some((item) => item.id === epidemiologyIncompatibleObservationId)).toBe(false);
  await expect(
    page.getByRole("region", { name: `Browser epidemiology disease ${fixtureKeyBase} 同口径趋势` }),
  ).toBeVisible();
  await page.getByRole("button", { name: "关闭趋势" }).click();
  const epidemiologySubscriptionName = `Browser epidemiology subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const epidemiologySaveForm = page.getByRole("dialog", { name: "保存当前流行病学检索" });
  await epidemiologySaveForm.getByLabel("名称").fill(epidemiologySubscriptionName);
  await epidemiologySaveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("流行病学检索已保存并启用监控")).toBeVisible();

  const newsQuery = new URLSearchParams({
    view: "news",
    q: fixtureKeyBase,
    event_type: "conference_abstract",
    publisher: `Browser publisher ${fixtureKeyBase}`,
    language: "en",
    venue: "ASCO 2026",
    published_from: "2026-07-01",
    published_to: "2026-07-31",
    content_scope: "research",
    display: "timeline",
    sort: "title:asc",
  });
  const newsResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/news-events" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("event_type") === "conference_abstract" &&
      url.searchParams.get("publisher") === `Browser publisher ${fixtureKeyBase}` &&
      url.searchParams.get("language") === "en" &&
      url.searchParams.get("venue") === "ASCO 2026" &&
      url.searchParams.get("content_scope") === "research"
    );
  });
  await page.goto(`/workspace/research?${newsQuery}`);
  const newsResponse = await newsResponsePromise;
  const newsPayload = (await newsResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(newsPayload.total).toBe(1);
  expect(newsPayload.items.map((item) => item.id)).toEqual([newsEventId]);
  expect(newsPayload.items.some((item) => item.id === newsNegativeEventId)).toBe(false);
  await expect(page.getByRole("region", { name: "研究发布时间线" })).toContainText(
    `Browser news event ${fixtureKeyBase}`,
  );
  const newsSubscriptionName = `Browser news subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const newsSaveForm = page.getByRole("dialog", { name: "保存当前新闻与会议检索" });
  await newsSaveForm.getByLabel("名称").fill(newsSubscriptionName);
  await newsSaveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("新闻与会议检索已保存并启用监控")).toBeVisible();

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const epidemiologyRow = page.getByRole("row").filter({ hasText: epidemiologySubscriptionName });
  await expect(epidemiologyRow).toContainText("流行病学");
  await epidemiologyRow.getByRole("button", { name: `运行 ${epidemiologySubscriptionName}` }).click();
  for (const [name, value] of epidemiologyQuery.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  const epidemiologyFilters = page.getByRole("form", { name: "流行病学筛选" });
  await expect(epidemiologyFilters.getByLabel("统计指标")).toHaveValue("prevalence");
  await expect(epidemiologyFilters.getByLabel("地区")).toHaveValue("China");
  await expect(epidemiologyFilters.getByLabel("标准患者人群")).toHaveValue(epidemiologyPatientPopulationId);
  await expect(
    page.getByRole("table", { name: "流行病学结果" }).getByRole("columnheader", { name: /指标 \/ 估计值/ }),
  ).toHaveAttribute("aria-sort", "descending");
  await page.reload();
  await expect(epidemiologyFilters.getByLabel("人群口径")).toHaveValue("adults");
  await expect(page.getByRole("table", { name: "流行病学结果" })).toContainText(
    `Browser epidemiology disease ${fixtureKeyBase}`,
  );

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const newsRow = page.getByRole("row").filter({ hasText: newsSubscriptionName });
  await expect(newsRow).toContainText("新闻与会议");
  await newsRow.getByRole("button", { name: `运行 ${newsSubscriptionName}` }).click();
  for (const [name, value] of newsQuery.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  const newsFilters = page.getByRole("form", { name: "新闻与会议筛选" });
  await expect(newsFilters.getByLabel("事件类型")).toHaveValue("conference_abstract");
  await expect(newsFilters.getByLabel("会议 / 场景")).toHaveValue("ASCO 2026");
  await expect(page.getByRole("button", { name: "研究发布时间线" })).toHaveAttribute("aria-pressed", "true");
  await page.reload();
  await expect(page.getByRole("region", { name: "研究发布时间线" })).toContainText(
    `Browser news event ${fixtureKeyBase}`,
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
});

test("[patent-deal-subscription] [patent-result-correctness] [deal-entity-query] [deal-asset-attributes] [deal-asset-multiselect] [deal-full-result-landscape] [deal-asset-correctness] saves, subscribes and replays both complete applied queries", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const dealAssetEntityId = process.env.E2E_REGULATORY_SUBJECT_ID;
  const dealTargetEntityId = process.env.E2E_PIPELINE_TARGET_ID;
  const dealDiseaseEntityId = process.env.E2E_PIPELINE_DISEASE_ID;
  const dealProfileId = process.env.E2E_DEAL_PROFILE_ID;
  const patentFamilyId = process.env.E2E_PATENT_FAMILY_ID;
  const patentNegativeFamilyId = process.env.E2E_PATENT_NEGATIVE_FAMILY_ID;
  test.skip(
    !credentials ||
      !fixtureKeyBase ||
      !dealAssetEntityId ||
      !dealTargetEntityId ||
      !dealDiseaseEntityId ||
      !dealProfileId ||
      !patentFamilyId ||
      !patentNegativeFamilyId,
    "Authenticated browser fixture credentials and normalized deal entities are required",
  );
  if (
    !credentials ||
    !fixtureKeyBase ||
    !dealAssetEntityId ||
    !dealTargetEntityId ||
    !dealDiseaseEntityId ||
    !dealProfileId ||
    !patentFamilyId ||
    !patentNegativeFamilyId
  )
    return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const crossAssetQuery = new URLSearchParams({
    view: "deals",
    q: fixtureKeyBase,
    asset_entity_id: dealAssetEntityId,
    asset_modality: "antibody",
    asset_program_tag: "best_in_class",
    development_phase_at_transaction: "phase_3",
    current_development_phase: "phase_3",
  });
  const crossAssetResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/deal-transactions" &&
      url.searchParams.get("asset_entity_id") === dealAssetEntityId &&
      url.searchParams.get("asset_modality") === "antibody" &&
      url.searchParams.get("asset_program_tag") === "best_in_class" &&
      url.searchParams.get("development_phase_at_transaction") === "phase_3" &&
      url.searchParams.get("current_development_phase") === "phase_3"
    );
  });
  await page.goto(`/workspace/research?${crossAssetQuery}`);
  const crossAssetResponse = await crossAssetResponsePromise;
  const crossAssetPayload = (await crossAssetResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(crossAssetPayload.total).toBe(0);
  expect(crossAssetPayload.items.some((item) => item.id === dealProfileId)).toBe(false);

  const patentQuery = new URLSearchParams({
    view: "patents",
    q: fixtureKeyBase,
    applicant: `Browser applicant ${fixtureKeyBase}`,
    legal_status: "ACTIVE",
    sort: "family_identifier:asc",
  });
  const patentResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/patent-families" &&
      url.searchParams.get("q") === fixtureKeyBase &&
      url.searchParams.get("applicant") === `Browser applicant ${fixtureKeyBase}` &&
      url.searchParams.get("legal_status") === "ACTIVE"
    );
  });
  await page.goto(`/workspace/research?${patentQuery}`);
  const patentResponse = await patentResponsePromise;
  const patentPayload = (await patentResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(patentPayload.total).toBe(1);
  expect(patentPayload.items.map((item) => item.id)).toEqual([patentFamilyId]);
  expect(patentPayload.items.some((item) => item.id === patentNegativeFamilyId)).toBe(false);
  await expect(page.getByRole("table", { name: "专利族结果" })).toContainText(
    `Browser patent family ${fixtureKeyBase}`,
  );
  const patentSubscriptionName = `Browser patent subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const patentSaveForm = page.getByRole("dialog", { name: "保存当前专利检索" });
  await patentSaveForm.getByLabel("名称").fill(patentSubscriptionName);
  await patentSaveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("专利检索已保存并启用监控")).toBeVisible();

  const dealQuery = new URLSearchParams({
    view: "deals",
    q: fixtureKeyBase,
    deal_type: "license",
    status: "active",
    direction: "outbound",
    direction_reference_jurisdiction: "US",
    territory: "global",
    asset_entity_id: dealAssetEntityId,
    target_entity_id: dealTargetEntityId,
    disease_entity_id: dealDiseaseEntityId,
    asset_modality: "small molecule",
    asset_program_tag: "first_in_class",
    party: `Browser regulatory company ${fixtureKeyBase}`,
    party_role: "licensor",
    party_country_region: "US",
    party_organization_type: "biopharma",
    right_type: "commercialization",
    rights_territory: "Greater China",
    currency: "USD",
    announced_from: "2026-01-01",
    announced_to: "2026-01-31",
    source_updated_from: "2026-03-01",
    source_updated_to: "2026-03-31",
    upfront_amount_min: "20000000",
    upfront_amount_max: "30000000",
    total_potential_amount_min: "400000000",
    total_potential_amount_max: "600000000",
    sort: "upfront_amount:asc",
  });
  dealQuery.append("asset_modality", "antibody");
  dealQuery.append("asset_program_tag", "best_in_class");
  const positiveDealResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/deal-transactions" &&
      url.searchParams.get("asset_entity_id") === dealAssetEntityId &&
      url.searchParams.getAll("asset_modality").length === 2 &&
      url.searchParams.getAll("asset_program_tag").length === 2
    );
  });
  await page.goto(`/workspace/research?${dealQuery}`);
  const positiveDealResponse = await positiveDealResponsePromise;
  const positiveDealPayload = (await positiveDealResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(positiveDealPayload.total).toBe(1);
  expect(positiveDealPayload.items.map((item) => item.id)).toEqual([dealProfileId]);
  await expect(page.getByRole("table", { name: "交易结果" })).toContainText(`Browser deal ${fixtureKeyBase}`);
  await expect(page.getByRole("group", { name: "交易药品规范实体筛选" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await expect(page.getByRole("group", { name: "关联靶点规范实体筛选" })).toContainText(
    `Browser pipeline target ${fixtureKeyBase}`,
  );
  await expect(page.getByRole("group", { name: "关联适应症规范实体筛选" })).toContainText(
    `Browser regulatory indication ${fixtureKeyBase}`,
  );
  await page.getByRole("button", { name: "统计" }).click();
  await expect(page.getByRole("region", { name: "交易数据统计" })).toBeVisible();
  await page.getByLabel("交易分析维度").selectOption("party_country");
  await page.getByRole("button", { name: "表格" }).click();
  await page.getByLabel("交易分析显示范围").selectOption("20");
  await expect(page.getByRole("table", { name: "参与方地区统计表" })).toContainText("US");
  await page.goto(`/workspace/research?${dealQuery}`);
  const dealResultTable = page.getByRole("table", { name: "交易结果" });
  await expect(dealResultTable).toContainText(`Browser deal ${fixtureKeyBase}`);
  const companyLink = dealResultTable.getByRole("button", {
    name: new RegExp(`Browser regulatory company ${fixtureKeyBase}`),
  });
  await companyLink.focus();
  await companyLink.press("Enter");
  await expect(page).toHaveURL(/view=company/);
  await page.goto(`/workspace/research?${dealQuery}`);
  await expect(dealResultTable).toBeVisible();
  const drugLink = dealResultTable.getByRole("button", {
    name: new RegExp(`Browser regulatory drug ${fixtureKeyBase}`),
  });
  await drugLink.focus();
  await drugLink.press("Enter");
  await expect(page).toHaveURL(/view=drug/);
  await page.goto(`/workspace/research?${dealQuery}`);
  await expect(dealResultTable).toBeVisible();
  const dealDossierLink = page.locator('button[aria-label*="Browser deal"]');
  await dealDossierLink.focus();
  await dealDossierLink.press("Enter");
  await expect(page).toHaveURL(/view=deals/);
  await expect(page).toHaveURL(/[?&]deal=[0-9a-f-]{36}(?:&|$)/);
  await page.goto(`/workspace/research?${dealQuery}`);
  await expect(dealResultTable).toBeVisible();
  dealQuery.set("display", "landscape");
  dealQuery.set("analysis_dimension", "party_country");
  dealQuery.set("analysis_view", "table");
  dealQuery.set("analysis_top", "20");
  await page.goto(`/workspace/research?${dealQuery}`);
  await expect(page.getByRole("region", { name: "交易数据统计" })).toBeVisible();
  const dealSubscriptionName = `Browser deal subscription ${fixtureKeyBase}`;
  await page.getByRole("button", { name: "保存/订阅" }).click();
  const dealSaveForm = page.getByRole("dialog", { name: "保存当前交易检索" });
  await dealSaveForm.getByLabel("名称").fill(dealSubscriptionName);
  await dealSaveForm.getByRole("button", { name: "确认保存" }).click();
  await expect(page.getByText("交易检索已保存并启用监控")).toBeVisible();

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const patentRow = page.getByRole("row").filter({ hasText: patentSubscriptionName });
  await expect(patentRow).toContainText("专利情报");
  await patentRow.getByRole("button", { name: `运行 ${patentSubscriptionName}` }).click();
  for (const [name, value] of patentQuery.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  const patentFilters = page.getByRole("form", { name: "专利族筛选" });
  await expect(patentFilters.getByLabel("申请人", { exact: true })).toHaveValue(`Browser applicant ${fixtureKeyBase}`);
  await expect(patentFilters.getByLabel("法律状态", { exact: true })).toHaveValue("ACTIVE");

  await page.goto("/workspace/research?view=monitoring");
  await page.getByRole("tab", { name: "已保存检索" }).click();
  const dealRow = page.getByRole("row").filter({ hasText: dealSubscriptionName });
  await expect(dealRow).toContainText("交易与公司");
  await dealRow.getByRole("button", { name: `运行 ${dealSubscriptionName}` }).click();
  for (const [name, value] of dealQuery.entries()) {
    if (name === "view") continue;
    await expect(page).toHaveURL(new RegExp(`${name}=${encodeURIComponent(value).replace(/%20/g, "(?:%20|\\+)")}`));
  }
  await expect(page.getByRole("region", { name: "交易数据统计" })).toBeVisible();
  await expect(page.getByLabel("交易分析维度")).toHaveValue("party_country");
  await expect(page.getByLabel("交易分析显示范围")).toHaveValue("20");
  await expect(page.getByRole("table", { name: "参与方地区统计表" })).toContainText("US");
  const dealFilters = page.getByRole("form", { name: "交易筛选" });
  await expect(dealFilters.getByLabel("交易方向", { exact: true })).toHaveValue("outbound");
  await expect(dealFilters.getByLabel("参与角色", { exact: true })).toHaveValue("licensor");
  await dealFilters.getByText("更多交易条件", { exact: true }).click();
  await dealFilters.getByLabel(/资产模态：/).click();
  await expect(dealFilters.getByRole("checkbox", { name: /small molecule/ })).toBeChecked();
  await expect(dealFilters.getByRole("checkbox", { name: /antibody/ })).toBeChecked();
  await dealFilters.getByLabel(/资产项目标签：/).click();
  await expect(dealFilters.getByRole("checkbox", { name: /first_in_class/ })).toBeChecked();
  await expect(dealFilters.getByRole("checkbox", { name: /best_in_class/ })).toBeChecked();
  await expect(dealFilters.getByLabel("币种", { exact: true })).toHaveValue("USD");
  await expect(dealFilters.getByRole("group", { name: "交易药品规范实体筛选" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await expect(dealFilters.getByRole("group", { name: "关联靶点规范实体筛选" })).toContainText(
    `Browser pipeline target ${fixtureKeyBase}`,
  );
  await expect(dealFilters.getByRole("group", { name: "关联适应症规范实体筛选" })).toContainText(
    `Browser regulatory indication ${fixtureKeyBase}`,
  );
  await page.reload();
  await expect(page.getByRole("table", { name: "参与方地区统计表" })).toContainText("US");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
});

test("[entity-research-continuity] preserves dossier sections across keyboard, reload and history", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  test.skip(!credentials || !fixtureKeyBase, "Authenticated browser fixture credentials are required");
  if (!credentials || !fixtureKeyBase) return;

  const fixtureKey = `${fixtureKeyBase}-continuity-${testInfo.project.name}`;
  const targetName = `Continuity target ${fixtureKey}`;
  const companyName = `Continuity company ${fixtureKey}`;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const csrfCookie = (await page.context().cookies()).find((cookie) => cookie.name === "pharma_csrf");
  if (!csrfCookie?.value) throw new Error("Authenticated session did not issue the CSRF cookie");
  const createEntity = async (entityType: "target" | "organization", name: string) => {
    const response = await page.request.post("/api/v1/entities", {
      headers: { "X-CSRF-Token": csrfCookie.value },
      data: {
        entity_type: entityType,
        name,
        description: "Controlled dossier continuity browser fixture",
        external_ids: { acceptance: `${fixtureKey}-${entityType}` },
        attributes: { acceptance_fixture: true, acceptance_fixture_key: fixtureKey },
      },
    });
    expect(response.status()).toBe(201);
    return (await response.json()) as { id: string };
  };
  const targetEntity = await createEntity("target", targetName);
  const companyEntity = await createEntity("organization", companyName);

  await page.goto(`/workspace/research?view=target&entity=${targetEntity.id}`);
  await expect(page.getByRole("heading", { name: targetName, exact: true })).toBeVisible();
  const targetOverviewTab = page.getByRole("tab", { name: "概览" });
  await targetOverviewTab.focus();
  await targetOverviewTab.press("ArrowRight");
  await expect(page).toHaveURL(/section=relationships/);
  await expect(page.getByRole("tab", { name: "关系网络" })).toHaveAttribute("aria-selected", "true");
  await page.reload();
  await expect(page.getByRole("tab", { name: "关系网络" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).not.toHaveURL(/section=/);
  await expect(page.getByRole("tab", { name: "概览" })).toHaveAttribute("aria-selected", "true");

  await page.goto(`/workspace/research?view=entity&entity=${companyEntity.id}`);
  await expect(page).toHaveURL(new RegExp(`view=company&entity=${companyEntity.id}`));
  await expect(page.getByRole("heading", { name: companyName, exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "公司时间线" }).click();
  await expect(page).toHaveURL(/section=timeline/);
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("tab", { name: "公司时间线" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "管线状态与交易公告" })).toBeVisible();
  await page.goBack();
  await expect(page).not.toHaveURL(/section=/);
  await expect(page.getByRole("tab", { name: "公司概览" })).toHaveAttribute("aria-selected", "true");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
});

test("[dense-server-sorting][disease-dossier] preserves governed ordering and disease research continuity", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKey = process.env.E2E_FIXTURE_KEY;
  const epidemiologyDiseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  test.skip(
    !credentials || !fixtureKey || !epidemiologyDiseaseId,
    "Authenticated browser fixture credentials and epidemiology disease ID are required",
  );
  if (!credentials || !fixtureKey || !epidemiologyDiseaseId) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  await page.goto(`/workspace/research?view=trials&q=${encodeURIComponent(fixtureKey)}`);
  const trialTable = page.getByRole("table", { name: "临床试验结果" });
  await expect(trialTable).toContainText(`Browser clinical trial ${fixtureKey}`);
  await expect(page.getByText(/全部结果按最近更新降序/)).toBeVisible();
  const sortedTrialResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["registry_id:asc"])
    );
  });
  await trialTable
    .getByRole("columnheader", { name: /注册号与试验/ })
    .getByRole("button")
    .click();
  const trialSortResponse = await sortedTrialResponse;
  expect(trialSortResponse.ok()).toBe(true);
  expect(await trialSortResponse.json()).toMatchObject({
    sort_by: "registry_id",
    sort_direction: "asc",
    sort: [{ field: "registry_id", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["registry_id:asc"]);
  await expect(page.getByText(/全部结果按注册号与试验升序/)).toBeVisible();
  await page.reload();
  await expect(trialTable.getByRole("columnheader", { name: /注册号与试验/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );

  await page.goto(`/workspace/research?view=patents&q=${encodeURIComponent(fixtureKey)}`);
  const patentTable = page.getByRole("table", { name: "专利族结果" });
  await expect(patentTable).toContainText(`Browser patent family ${fixtureKey}`);
  await expect(page.getByText(/全部结果按最早优先权降序/)).toBeVisible();
  const sortedPatentResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/patent-families" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["family_identifier:asc"])
    );
  });
  await patentTable
    .getByRole("columnheader", { name: /专利族与标题/ })
    .getByRole("button")
    .click();
  const patentSortResponse = await sortedPatentResponse;
  expect(patentSortResponse.ok()).toBe(true);
  expect(await patentSortResponse.json()).toMatchObject({
    sort_by: "family_identifier",
    sort_direction: "asc",
    sort: [{ field: "family_identifier", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["family_identifier:asc"]);
  await expect(page.getByText(/全部结果按专利族与标题升序/)).toBeVisible();
  await page.reload();
  await expect(patentTable.getByRole("columnheader", { name: /专利族与标题/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );

  await page.goto(`/workspace/research?view=news&q=${encodeURIComponent(fixtureKey)}`);
  const newsTable = page.getByRole("table", { name: "新闻与会议结果" });
  await expect(newsTable).toContainText(`Browser news event ${fixtureKey}`);
  await expect(page.getByText(/全部结果按发布日期降序/)).toBeVisible();
  const sortedNewsResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/news-events" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["title:asc"])
    );
  });
  await newsTable
    .getByRole("columnheader", { name: /标题与摘要/ })
    .getByRole("button")
    .click();
  const newsSortResponse = await sortedNewsResponse;
  expect(newsSortResponse.ok()).toBe(true);
  expect(await newsSortResponse.json()).toMatchObject({
    sort_by: "title",
    sort_direction: "asc",
    sort: [{ field: "title", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["title:asc"]);
  await expect(page.getByText(/全部结果按标题与摘要升序/)).toBeVisible();
  await page.reload();
  await expect(newsTable.getByRole("columnheader", { name: /标题与摘要/ })).toHaveAttribute("aria-sort", "ascending");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  const diseaseName = `Browser epidemiology disease ${fixtureKey}`;
  await page.goto(`/workspace/research?view=disease&entity=${epidemiologyDiseaseId}`);
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${epidemiologyDiseaseId}`));
  await expect(page.getByRole("heading", { name: diseaseName })).toBeVisible();
  await expect(page.getByText("疾病负担观测", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "最新疾病负担观测" })).toContainText("158,000");

  await page.getByRole("tab", { name: "流行病学" }).click();
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${epidemiologyDiseaseId}&section=epidemiology`));
  await expect(page.getByRole("table", { name: "疾病流行病学观测" })).toContainText(
    "Controlled browser acceptance methodology",
  );
  await page.getByRole("button", { name: "进入完整数据库" }).click();
  await expect(page).toHaveURL(new RegExp(`view=epidemiology&disease_entity_id=${epidemiologyDiseaseId}`));
  await expect(page.getByRole("group", { name: "疾病规范实体筛选" })).toContainText(diseaseName);
  await expect(page.getByRole("table", { name: "流行病学结果" })).toContainText("158,000");

  await page.goto(`/workspace/research?view=entity&entity=${epidemiologyDiseaseId}&section=programs`);
  await expect(page).toHaveURL(new RegExp(`view=disease&entity=${epidemiologyDiseaseId}&section=pipeline`));
  await expect(page.getByRole("heading", { name: diseaseName })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
});

test("[dense-server-sorting-secondary] preserves governed deal, regulatory and epidemiology ordering", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKey = process.env.E2E_FIXTURE_KEY;
  test.skip(!credentials || !fixtureKey, "Authenticated browser fixture credentials are required");
  if (!credentials || !fixtureKey) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  await page.goto(`/workspace/research?view=deals&q=${encodeURIComponent(fixtureKey)}`);
  const dealTable = page.getByRole("table", { name: "交易结果" });
  await expect(dealTable).toContainText(`Browser deal ${fixtureKey}`);
  await expect(page.getByText(/全部结果按初始披露降序/)).toBeVisible();
  const sortedDealResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/deal-transactions" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["name:asc"])
    );
  });
  await dealTable
    .getByRole("columnheader", { name: /交易名称/ })
    .getByRole("button")
    .click();
  const dealSortResponse = await sortedDealResponse;
  expect(dealSortResponse.ok()).toBe(true);
  expect(await dealSortResponse.json()).toMatchObject({
    sort_by: "name",
    sort_direction: "asc",
    sort: [{ field: "name", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["name:asc"]);
  await page.reload();
  await expect(dealTable.getByRole("columnheader", { name: /交易名称/ })).toHaveAttribute("aria-sort", "ascending");

  await page.goto(`/workspace/research?view=regulatory&q=${encodeURIComponent(fixtureKey)}`);
  const regulatoryTable = page.getByRole("table", { name: "监管事件结果" });
  await expect(regulatoryTable).toContainText(`Browser regulatory event ${fixtureKey}`);
  await expect(page.getByText(/全部结果按决定日期降序/)).toBeVisible();
  const sortedRegulatoryResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/regulatory-event-timeline" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["title:asc"])
    );
  });
  await regulatoryTable
    .getByRole("columnheader", { name: /监管事件/ })
    .getByRole("button")
    .click();
  const regulatorySortResponse = await sortedRegulatoryResponse;
  expect(regulatorySortResponse.ok()).toBe(true);
  expect(await regulatorySortResponse.json()).toMatchObject({
    sort_by: "title",
    sort_direction: "asc",
    sort: [{ field: "title", direction: "asc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["title:asc"]);
  await page.reload();
  await expect(regulatoryTable.getByRole("columnheader", { name: /监管事件/ })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );

  await page.goto(`/workspace/research?view=epidemiology&q=${encodeURIComponent(fixtureKey)}`);
  const epidemiologyTable = page.getByRole("table", { name: "流行病学结果" });
  await expect(epidemiologyTable).toContainText(`Browser epidemiology disease ${fixtureKey}`);
  await expect(page.getByText(/全部结果按观察期降序/)).toBeVisible();
  const sortedEpidemiologyResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/epidemiology-observations" &&
      JSON.stringify(url.searchParams.getAll("sort")) === JSON.stringify(["value:desc"])
    );
  });
  await epidemiologyTable
    .getByRole("columnheader", { name: /指标 \/ 估计值/ })
    .getByRole("button")
    .click();
  const epidemiologySortResponse = await sortedEpidemiologyResponse;
  expect(epidemiologySortResponse.ok()).toBe(true);
  expect(await epidemiologySortResponse.json()).toMatchObject({
    sort_by: "value",
    sort_direction: "desc",
    sort: [{ field: "value", direction: "desc" }],
  });
  await expect.poll(() => new URL(page.url()).searchParams.getAll("sort")).toEqual(["value:desc"]);
  await page.reload();
  await expect(epidemiologyTable.getByRole("columnheader", { name: /指标 \/ 估计值/ })).toHaveAttribute(
    "aria-sort",
    "descending",
  );
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
});

test("[billing-dispute] opens and acknowledges a billing dispute in the human workspace", async ({ page }) => {
  let disputeCreated = false;
  const dispute = {
    id: "browser-dispute-1",
    dispute_key: "dispute.browser.0001",
    billing_account_id: "browser-account-1",
    billing_account_key: "account-browser",
    billing_account_name: "Browser Research",
    subscription_id: "browser-subscription-1",
    statement_id: "browser-statement-1",
    statement_key: "statement-browser-2026-07",
    invoice_reference_id: null,
    external_invoice_id: null,
    status: "open",
    category: "usage",
    disputed_units: "2.50000000",
    subject: "Browser metering dispute",
    description: "Validate the browser dispute workflow.",
    opened_by: "browser-admin",
    opened_at: "2026-07-18T10:00:00Z",
    assigned_to: null,
    due_at: "2026-07-23T10:00:00Z",
    overdue: false,
    resolution_code: null,
    resolution_notes: "",
    resolved_by: null,
    resolved_at: null,
    resolution_adjustment_key: null,
    version: 1,
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T10:00:00Z",
  };
  const posts: Array<{ path: string; body: Record<string, unknown> }> = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "browser-admin",
          tenant_id: "browser-tenant",
          email: "browser-admin@example.test",
          display_name: "Browser Admin",
          role: "admin",
        },
      });
    }
    if (path === "/api/v1/commercial/overview") {
      return route.fulfill({
        json: { as_of: "2026-07-18T10:00:00Z", period_start: "2026-07-18T00:00:00Z", subscriptions: [] },
      });
    }
    if (path === "/api/v1/commercial/billing-deliveries") {
      return route.fulfill({
        json: [
          {
            delivery_id: null,
            event_id: "browser-event-1",
            statement_id: dispute.statement_id,
            statement_key: dispute.statement_key,
            billing_account_id: dispute.billing_account_id,
            billing_account_key: dispute.billing_account_key,
            billing_account_name: dispute.billing_account_name,
            state: "pending",
            attempts: 0,
            available_at: "2026-07-18T10:00:00Z",
            lease_expires_at: null,
            processed_at: null,
            last_error: null,
            invoice_provider: null,
            external_invoice_id: null,
            invoice_status: null,
            created_at: "2026-07-18T10:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/commercial/billing-disputes" && request.method() === "GET") {
      return route.fulfill({ json: disputeCreated ? [dispute] : [] });
    }
    if (path.startsWith("/api/v1/commercial/billing-disputes") && request.method() === "POST") {
      posts.push({ path, body: request.postDataJSON() as Record<string, unknown> });
      disputeCreated = true;
      return route.fulfill({
        json: path.endsWith("/transition") ? { ...dispute, status: "investigating", version: 2 } : dispute,
      });
    }
    if (path.startsWith("/api/v1/commercial/")) return route.fulfill({ json: [] });
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await page.goto("/workspace/internal?view=commercial");
  await expect(page.getByRole("heading", { name: "Agent 商业运营" })).toBeVisible();
  await page.getByRole("tab", { name: "账单投递" }).click();
  await page.getByRole("button", { name: `对账期单 ${dispute.statement_key} 发起计费争议` }).click();
  await page.getByLabel("争议额度").fill("2.5");
  await page.getByLabel("争议主题").fill(dispute.subject);
  await page.getByLabel("争议说明").fill(dispute.description);
  await page.getByRole("button", { name: "提交争议" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("tab", { name: "计费争议" }).click();
  await expect(page.getByText(dispute.subject, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: `处理计费争议 ${dispute.dispute_key}` }).click();
  await page.getByLabel("争议处理记录").fill("Finance accepted the browser dispute for investigation.");
  await page.getByRole("button", { name: "提交处理" }).click();
  await expect.poll(() => posts.length).toBe(2);
  expect(posts[0]?.body).toMatchObject({ statement_id: dispute.statement_id, disputed_units: "2.5" });
  expect(posts[1]?.body).toMatchObject({ expected_version: 1, action: "investigate" });
});

test("[enterprise-administration] manages tenant roles through the governed human workspace", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const users = [
    {
      id: "browser-admin",
      tenant_id: "browser-tenant",
      email: "browser-admin@example.test",
      display_name: "Browser Admin",
      role: "admin",
      active: true,
      token_version: 1,
      last_login_at: "2026-07-19T10:00:00Z",
      oidc_issuer: null,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-19T10:00:00Z",
    },
    {
      id: "browser-analyst",
      tenant_id: "browser-tenant",
      email: "browser-analyst@example.test",
      display_name: "Browser Analyst",
      role: "analyst",
      active: true,
      token_version: 4,
      last_login_at: null,
      oidc_issuer: null,
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-19T10:00:00Z",
    },
  ];
  const roleUpdates: Array<Record<string, unknown>> = [];
  const sessionRevocations: Array<Record<string, unknown>> = [];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "browser-admin",
          tenant_id: "browser-tenant",
          email: "browser-admin@example.test",
          display_name: "Browser Admin",
          role: "admin",
        },
      });
    }
    if (path === "/api/v1/enterprise/overview") {
      return route.fulfill({
        json: {
          tenant: {
            id: "browser-tenant",
            slug: "browser",
            name: "Browser Pharma Tenant",
            active: true,
            created_at: "2026-07-01T00:00:00Z",
            updated_at: "2026-07-19T10:00:00Z",
          },
          user_count: 2,
          active_user_count: 2,
          admin_count: 1,
          group_count: 1,
          active_group_count: 1,
          dataset_count: 5,
          active_source_count: 3,
          audit_event_count_24h: 8,
        },
      });
    }
    if (path === "/api/v1/enterprise/platform") {
      return route.fulfill({
        json: {
          generated_at: "2026-07-25T12:00:00Z",
          environment: "test",
          services: [
            {
              service_id: "api",
              owner: "platform-operations",
              escalation_policy: "role://platform-operations/on-call",
              status: "ready",
              detail: "Current authenticated API request completed",
            },
            {
              service_id: "mcp",
              owner: "platform-operations",
              escalation_policy: "role://platform-operations/on-call",
              status: "external",
              detail: "Dedicated Agent entry probe required",
            },
          ],
          queues: {
            ingestion: { pending: 1, running: 1, stale: 0 },
            outbox: { pending: 0, failed: 0 },
            deliveries: { opensearch: { retry: 0, dead: 0 } },
            governance: { review_pending: 2 },
          },
          workflow: {
            engine: "temporal",
            enabled: true,
            namespace: "default",
            task_queue: "pharma-data-factory",
            max_concurrent_activities: 20,
          },
          model_budget: {
            window: "24h",
            run_count: 2,
            input_tokens: 400,
            output_tokens: 100,
            estimated_cost: "0.020000",
            failed_runs: 0,
            max_document_cost: "2.000000",
            provider: "remote_api",
            model: "mimo-v2.5",
          },
          slos: [
            {
              id: "web-availability",
              service: "api",
              metric: "http.server.duration",
              measurement: "success_ratio",
              target: 0.999,
              window: "30d",
              evaluation_status: "external_evidence_required",
              error_budget_policy: "freeze_noncritical_changes",
            },
          ],
          alerts: [],
          migration: {
            current_revision: "fc5e8a1b3d72",
            expected_revision: "fc5e8a1b3d72",
            status: "current",
          },
          evidence: [
            {
              category: "backup_restore",
              status: "passed",
              artifact: "backup_restore/report.json",
              sha256: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
              observed_at: "2026-07-25T11:00:00Z",
              detail: "Machine report status: passed",
            },
            {
              category: "release_candidate",
              status: "missing",
              artifact: "candidate-summary.json",
              sha256: null,
              observed_at: null,
              detail: "No machine-generated evidence is mounted",
            },
            {
              category: "production_topology",
              status: "not_configured",
              artifact: "production_topology/report.json",
              sha256: null,
              observed_at: null,
              detail: "Evidence mount is not configured for this environment",
            },
          ],
          recent_events: [],
        },
      });
    }
    if (path === "/api/v1/enterprise/users" && request.method() === "GET") return route.fulfill({ json: users });
    if (path === "/api/v1/enterprise/api-keys" && request.method() === "GET") {
      const catalog = {
        items: [],
        required_scope: "mcp:connect",
        allowed_scopes: ["mcp:connect", "entities:read", "targets:read"],
        min_ttl_hours: 1,
        max_ttl_days: 366,
      } satisfies EnterpriseApiKeyCatalogRead;
      return route.fulfill({ json: catalog });
    }
    if (path === "/api/v1/enterprise/datasets") {
      return route.fulfill({
        json: [
          {
            id: "browser-dataset",
            dataset_key: "literature",
            display_name: "Browser literature dataset",
            active: true,
            version: 3,
            required_scopes: ["evidence:read"],
            license_id: "browser-license",
            license_policy_version: "browser-v1",
            permitted_channels: ["web", "mcp"],
            license_current: true,
            attribution: "Browser controlled fixture",
          },
        ],
      });
    }
    if (path === "/api/v1/enterprise/sessions" && request.method() === "GET") {
      return route.fulfill({
        json: [
          {
            id: "browser-remote-session",
            user_id: "browser-analyst",
            user_display_name: "Browser Analyst",
            user_email: "browser-analyst@example.test",
            issued_at: "2026-07-19T09:00:00Z",
            expires_at: "2099-07-19T17:00:00Z",
            revoked_at: null,
            revoked_by_user_id: null,
            revoke_reason: null,
            current: false,
          },
        ],
      });
    }
    if (path === "/api/v1/enterprise/sessions/browser-remote-session/revoke" && request.method() === "POST") {
      sessionRevocations.push(request.postDataJSON() as Record<string, unknown>);
      return route.fulfill({
        json: {
          id: "browser-remote-session",
          user_id: "browser-analyst",
          user_display_name: "Browser Analyst",
          user_email: "browser-analyst@example.test",
          issued_at: "2026-07-19T09:00:00Z",
          expires_at: "2099-07-19T17:00:00Z",
          revoked_at: "2026-07-19T10:00:00Z",
          revoked_by_user_id: "browser-admin",
          revoke_reason: "Browser remote session revocation",
          current: false,
        },
      });
    }
    if (path === "/api/v1/commercial/clients") return route.fulfill({ json: [] });
    if (path === "/api/v1/commercial/data-lifecycle/retention-policies") return route.fulfill({ json: [] });
    if (path === "/api/v1/commercial/data-lifecycle/legal-holds") return route.fulfill({ json: [] });
    if (path === "/api/v1/enterprise/groups") {
      return route.fulfill({
        json: [
          {
            id: "browser-group",
            tenant_id: "browser-tenant",
            name: "Research Operations",
            description: "Browser acceptance group",
            active: true,
            version: 2,
            member_ids: ["browser-analyst"],
            member_count: 1,
            created_at: "2026-07-01T00:00:00Z",
            updated_at: "2026-07-19T10:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/enterprise/users/browser-analyst/role" && request.method() === "POST") {
      roleUpdates.push(request.postDataJSON() as Record<string, unknown>);
      return route.fulfill({ json: { ...users[1], role: "admin", token_version: 5 } });
    }
    if (path === "/api/v1/enterprise/audit-events") return route.fulfill({ json: { items: [], next_cursor: null } });
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/internal?view=enterprise");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page.getByRole("heading", { name: "企业账户与审计" })).toBeVisible();
  await expect(page.getByText("Browser Pharma Tenant", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "用户与角色" }).click();
  await expect(page.getByRole("button", { name: "调整 Browser Admin 的角色" })).toBeDisabled();
  await page.getByRole("button", { name: "调整 Browser Analyst 的角色" }).click();
  await page.getByLabel("新角色").selectOption("admin");
  await page.getByLabel("变更原因").fill("Browser acceptance role governance");
  await page.getByRole("button", { name: "确认变更" }).click();
  await expect.poll(() => roleUpdates.length).toBe(1);
  expect(roleUpdates[0]).toEqual({
    expected_token_version: 4,
    role: "admin",
    reason: "Browser acceptance role governance",
  });
  await page.getByRole("tab", { name: "访问与生命周期" }).click();
  await expect(page.getByRole("heading", { name: "数据集与交付授权" })).toBeVisible();
  await expect(page.getByText("WEB / MCP", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "撤销", exact: true }).click();
  await page.getByLabel("变更原因").fill("Browser remote session revocation");
  await page.getByRole("button", { name: "确认变更" }).click();
  await expect.poll(() => sessionRevocations.length).toBe(1);
  expect(sessionRevocations[0]).toEqual({ reason: "Browser remote session revocation" });
  await page.getByRole("tab", { name: "平台运营" }).click();
  await expect(page.getByRole("table", { name: "平台服务状态" })).toContainText("platform-operations");
  await expect(page.getByRole("table", { name: "平台 SLO" })).toContainText("web-availability");
  await expect(page.getByRole("table", { name: "平台发布证据" })).toContainText("backup_restore");
  expect(pageErrors).toEqual([]);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[monitoring] reviews saved searches and acknowledges a durable monitoring alert", async ({ page }, testInfo) => {
  testInfo.setTimeout(60_000);
  let acknowledged = false;
  let savedSearchVisibility: "private" | "tenant" = "tenant";
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "monitoring-user",
          tenant_id: "monitoring-tenant",
          email: "monitoring@example.test",
          display_name: "Monitoring Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/monitoring/saved-searches" && request.method() === "GET") {
      return route.fulfill({
        json: [
          {
            id: "saved-browser-1",
            owner_user_id: "monitoring-user",
            name: "EGFR enterprise watch",
            description: "Shared target watch",
            query_type: "entity_search",
            query_version: 2,
            query_json: { q: "EGFR", entity_type: "target" },
            visibility: savedSearchVisibility,
            created_at: "2026-07-18T10:00:00Z",
            updated_at: "2026-07-18T11:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/monitoring/saved-searches/saved-browser-1" && request.method() === "PATCH") {
      const body = request.postDataJSON() as { visibility: "private" | "tenant" };
      savedSearchVisibility = body.visibility;
      return route.fulfill({
        json: {
          id: "saved-browser-1",
          owner_user_id: "monitoring-user",
          name: "EGFR enterprise watch",
          description: "Shared target watch",
          query_type: "entity_search",
          query_version: 2,
          query_json: { q: "EGFR", entity_type: "target" },
          visibility: savedSearchVisibility,
          created_at: "2026-07-18T10:00:00Z",
          updated_at: "2026-07-18T12:05:00Z",
        },
      });
    }
    if (path === "/api/v1/monitoring/topics") {
      return route.fulfill({
        json: [
          {
            id: "topic-browser-1",
            owner_user_id: "monitoring-user",
            saved_search_id: "saved-browser-1",
            query_version: 2,
            name: "EGFR changes",
            active: true,
            created_at: "2026-07-18T10:00:00Z",
            updated_at: "2026-07-18T11:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/monitoring/alerts" && request.method() === "GET") {
      return route.fulfill({
        json: [
          {
            id: "alert-browser-1",
            topic_id: "topic-browser-1",
            topic_name: "EGFR changes",
            entity_id: "entity-browser-1",
            entity_name: "EGFR",
            event_type: "governance.fact.published",
            title: "EGFR changed",
            summary: "target 实体 EGFR 匹配监控条件。",
            payload_json: { query_version: 2 },
            occurred_at: "2026-07-18T12:00:00Z",
            read_at: acknowledged ? "2026-07-18T12:01:00Z" : null,
          },
        ],
      });
    }
    if (path === "/api/v1/monitoring/alerts/alert-browser-1/read" && request.method() === "POST") {
      acknowledged = true;
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=monitoring");
  await expect(page.getByRole("heading", { name: "情报监控与变更提醒" })).toBeVisible();
  await expect(page.getByText("EGFR changes", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "将 EGFR 提醒标记已读" }).click();
  await expect.poll(() => acknowledged).toBe(true);
  await expect(page.getByText("read", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "已保存检索" }).click();
  await expect(page.getByText("EGFR enterprise watch", { exact: true })).toBeVisible();
  await expect(page.getByText("企业共享", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "将 EGFR enterprise watch 设为私有" }).click();
  await expect.poll(() => savedSearchVisibility).toBe("private");
  await expect(page.getByText("仅自己", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "已保存检索" }).click();
  await expect(page.getByText("仅自己", { exact: true })).toBeVisible();
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[knowledge-governance] inspects governed coverage and traceable version changes", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "knowledge-user",
          tenant_id: "knowledge-tenant",
          email: "knowledge@example.test",
          display_name: "Knowledge Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/knowledge/pages") {
      return route.fulfill({
        json: [
          {
            current_version_id: "knowledge-version-2",
            id: "knowledge-page-1",
            page_key: "entity/target/egfr",
            page_type: "target",
            status: "published",
            subject_entity_id: "target-egfr",
            title: "EGFR competitive landscape",
            updated_at: "2026-07-24T08:00:00Z",
          },
        ],
      });
    }
    if (path === "/api/v1/knowledge/pages/knowledge-page-1") {
      return route.fulfill({
        json: {
          current_version_id: "knowledge-version-2",
          id: "knowledge-page-1",
          page_key: "entity/target/egfr",
          page_type: "target",
          status: "published",
          subject_entity_id: "target-egfr",
          title: "EGFR competitive landscape",
          updated_at: "2026-07-24T08:00:00Z",
          compiler_version: "knowledge-v1",
          content_json: {},
          content_sha256: "a".repeat(64),
          rendered_markdown: "# EGFR\n\nGoverned competitive landscape with source citations.",
          source_snapshot_at: "2026-07-24T08:00:00Z",
          version_number: 2,
        },
      });
    }
    if (path === "/api/v1/knowledge/pages/knowledge-page-1/coverage") {
      return route.fulfill({
        json: {
          cited_fact_count: 3,
          fact_count: 3,
          linked_entity_count: 2,
          page_id: "knowledge-page-1",
          predicates: [
            { cited_fact_count: 2, fact_count: 2, predicate: "has_competitor" },
            { cited_fact_count: 1, fact_count: 1, predicate: "has_target_class" },
          ],
          source_count: 2,
          source_snapshot_at: "2026-07-24T08:00:00Z",
          uncited_fact_count: 0,
          version_id: "knowledge-version-2",
          version_number: 2,
        },
      });
    }
    if (path === "/api/v1/knowledge/pages/knowledge-page-1/versions") {
      return route.fulfill({
        json: [
          {
            added_fact_count: 1,
            added_source_count: 1,
            compiler_version: "knowledge-v1",
            content_sha256: "a".repeat(64),
            created_at: "2026-07-24T08:00:00Z",
            created_by_run_id: "governance-run-2",
            fact_count: 3,
            is_current: true,
            previous_version_number: 1,
            removed_fact_count: 0,
            removed_source_count: 0,
            source_count: 2,
            source_snapshot_at: "2026-07-24T08:00:00Z",
            version_id: "knowledge-version-2",
            version_number: 2,
          },
          {
            added_fact_count: 2,
            added_source_count: 1,
            compiler_version: "knowledge-v1",
            content_sha256: "b".repeat(64),
            created_at: "2026-07-23T08:00:00Z",
            created_by_run_id: "governance-run-1",
            fact_count: 2,
            is_current: false,
            previous_version_number: null,
            removed_fact_count: 0,
            removed_source_count: 0,
            source_count: 1,
            source_snapshot_at: "2026-07-23T08:00:00Z",
            version_id: "knowledge-version-1",
            version_number: 1,
          },
        ],
      });
    }
    if (path.endsWith("/diff")) {
      const versionNumber = path.includes("/versions/1/") ? 1 : 2;
      return route.fulfill({
        json: {
          added_fact_count: versionNumber === 2 ? 1 : 2,
          added_facts: [
            {
              change_key: `knowledge-change-${versionNumber}`,
              citation_number: 2,
              confidence: 0.95,
              fact_id: "fact-competitor",
              object_entity_name: "Drug B",
              predicate: "has_competitor",
              source_document_id: "source-competitive-update",
              source_locator: "page=8",
              source_title: "Competitive landscape update",
              value: { name: "Drug B" },
            },
          ],
          added_source_count: 1,
          added_sources: [
            {
              locator: "page=8",
              source_document_id: "source-competitive-update",
              source_uri: "file:///research/competitive-update.pdf",
              title: "Competitive landscape update",
            },
          ],
          from_version_number: versionNumber === 2 ? 1 : null,
          page_id: "knowledge-page-1",
          removed_fact_count: 0,
          removed_facts: [],
          removed_source_count: 0,
          removed_sources: [],
          to_version_number: versionNumber,
          truncated: false,
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=knowledge");
  await expect(page.getByRole("heading", { name: "版本化知识专题" })).toBeVisible();
  await page.getByRole("button", { name: /EGFR competitive landscape/ }).click();
  await expect(page.getByRole("heading", { name: "EGFR competitive landscape" })).toBeVisible();
  await page.getByRole("tab", { name: "覆盖与版本" }).click();
  await expect(page.getByRole("region", { name: "专题覆盖摘要" })).toContainText("3专题要点");
  await expect(page.getByRole("cell", { name: "has_competitor" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "v1 → v2" })).toBeVisible();
  await expect(page.getByText("Competitive landscape update", { exact: true })).toBeVisible();
  await expect(page.getByText("page=8", { exact: true })).toBeVisible();
  await page.getByRole("list", { name: "专题版本" }).getByRole("button", { name: /v1/ }).click();
  await expect(page.getByRole("heading", { name: "初始版本 v1" })).toBeVisible();
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[knowledge-research-continuity] preserves a real governed topic across URL, reload and history", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  test.skip(!credentials, "Authenticated browser fixture credentials are required");
  if (!credentials) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const pagesResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === "/api/v1/knowledge/pages";
  });
  await page.goto("/workspace/research?view=knowledge");
  const pagesResponse = await pagesResponsePromise;
  expect(pagesResponse.ok()).toBe(true);
  const pages = (await pagesResponse.json()) as Array<{ id: string; title: string }>;
  const topic = pages.find((item) => /^[0-9a-f-]{36}$/i.test(item.id));
  expect(topic, "the authenticated tenant must expose at least one governed knowledge topic").toBeTruthy();
  if (!topic) return;

  const topicButton = page.locator(".knowledge-page-list button").filter({ hasText: topic.title }).first();
  await expect(topicButton).toBeVisible();
  await topicButton.click();
  await expect(page).toHaveURL(new RegExp(`view=knowledge.*page=${topic.id}`));
  await expect(page.getByRole("heading", { name: topic.title, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: topic.title, exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "覆盖与版本" }).click();
  await expect(page).toHaveURL(new RegExp(`page=${topic.id}.*panel=governance`));
  const versionList = page.getByRole("list", { name: "专题版本" });
  const versionButton = versionList.getByRole("button").first();
  await expect(versionButton).toBeVisible();
  const versionLabel = (await versionButton.getByRole("strong").textContent())?.trim() ?? "";
  const versionNumber = Number.parseInt(versionLabel.replace(/^v/, ""), 10);
  expect(versionNumber).toBeGreaterThan(0);
  await versionButton.click();
  await expect(page).toHaveURL(new RegExp(`panel=governance.*version=${versionNumber}`));
  await page.reload();
  await expect(versionButton).toHaveAttribute("aria-current", "true");

  await page.goBack();
  await expect(page).toHaveURL(/panel=governance/);
  await expect(page).not.toHaveURL(/version=/);
  await expect(page.getByRole("tab", { name: "覆盖与版本" })).toHaveAttribute("aria-selected", "true");
  await page.goBack();
  await expect(page).not.toHaveURL(/panel=/);
  await expect(page.getByRole("tab", { name: "专题正文" })).toHaveAttribute("aria-selected", "true");
});

test("[evidence-research-continuity] preserves a real licensed citation across URL, reload and history", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  test.skip(!credentials, "Authenticated browser fixture credentials are required");
  if (!credentials) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const catalogResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "GET" && url.pathname === "/api/v1/evidence/datasets";
  });
  const initialSearchPromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST" && url.pathname === "/api/v1/evidence/search";
  });
  await page.goto("/workspace/research?view=evidence&q=EGFR");
  const [catalogResponse, initialSearchResponse] = await Promise.all([catalogResponsePromise, initialSearchPromise]);
  expect(catalogResponse.ok()).toBe(true);
  expect(initialSearchResponse.ok()).toBe(true);
  const catalog = (await catalogResponse.json()) as Array<{ dataset_key: string; display_name: string }>;
  const initialResult = (await initialSearchResponse.json()) as {
    chunks: Array<{ dataset_id: string; document_id: string; document_name: string }>;
  };
  expect(initialResult.chunks.length).toBeGreaterThan(1);
  const firstInitialChunk = initialResult.chunks[0];
  expect(firstInitialChunk).toBeTruthy();
  if (!firstInitialChunk) return;
  const dataset = catalog.find((item) => item.dataset_key === firstInitialChunk.dataset_id);
  expect(dataset, "the result dataset must be present in the licensed web catalog").toBeTruthy();
  if (!dataset) return;

  const datasetButton = page.getByRole("button", { name: dataset.display_name, exact: true });
  await expect(datasetButton).toBeVisible();
  await datasetButton.click();
  const filteredSearchPromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return response.request().method() === "POST" && url.pathname === "/api/v1/evidence/search";
  });
  await page.getByRole("button", { name: "查证原文" }).click();
  const filteredSearchResponse = await filteredSearchPromise;
  expect(filteredSearchResponse.ok()).toBe(true);
  expect(filteredSearchResponse.request().postDataJSON()).toMatchObject({ dataset_keys: [dataset.dataset_key] });
  const filteredResult = (await filteredSearchResponse.json()) as {
    chunks: Array<{ document_id: string; document_name: string }>;
  };
  expect(filteredResult.chunks.length).toBeGreaterThan(1);

  await page.getByRole("button", { name: "定位引用 01" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("dataset")).toBe(dataset.dataset_key);
  await expect.poll(() => new URL(page.url()).searchParams.get("document")).toBe(filteredResult.chunks[0]?.document_id);
  await expect.poll(() => new URL(page.url()).searchParams.get("chunk")).toBe("1");
  await expect(page.getByLabel("当前引用定位")).toContainText(filteredResult.chunks[0]?.document_name ?? "");

  await page.reload();
  await expect(datasetButton).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("article.evidence-record[aria-current='true']")).toContainText(
    filteredResult.chunks[0]?.document_name ?? "",
  );

  await page.getByRole("button", { name: "定位引用 02" }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get("chunk")).toBe("2");
  await page.goBack();
  await expect.poll(() => new URL(page.url()).searchParams.get("chunk")).toBe("1");
  await expect(page.locator("article.evidence-record[aria-current='true']")).toContainText(
    filteredResult.chunks[0]?.document_name ?? "",
  );
});

test("[research-publication-timeline] switches to governed conference and publication chronology", async ({ page }) => {
  const requestedScopes: Array<string | null> = [];
  await page.route("**/api/v1/**", async (route) => {
    const requestUrl = new URL(route.request().url());
    const path = requestUrl.pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "publication-user",
          tenant_id: "publication-tenant",
          email: "publication@example.test",
          display_name: "Publication Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/news-events") {
      const contentScope = requestUrl.searchParams.get("content_scope");
      requestedScopes.push(contentScope);
      const researchMode = contentScope === "research";
      return route.fulfill({
        json: {
          items: [
            {
              id: researchMode ? "poster-1" : "announcement-1",
              event_identifier: researchMode ? "ASCO-POSTER-1" : "ANNOUNCEMENT-1",
              event_type: researchMode ? "poster" : "corporate_announcement",
              title: researchMode ? "ASCO 2026 EGFR poster" : "EGFR corporate update",
              summary: "Governed source-backed research update.",
              published_at: "2026-06-05T08:00:00Z",
              language: "en",
              publisher_entity_id: "publication-publisher",
              related_entity_ids: ["publication-target"],
              canonical_url: "https://example.test/asco/egfr-poster",
              venue: "ASCO 2026",
              details: {},
              source_document_id: "publication-source",
              publisher_entity: {
                id: "publication-publisher",
                name: "Research Publisher",
                entity_type: "organization",
              },
              related_entities: [{ id: "publication-target", name: "EGFR", entity_type: "target" }],
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
          facets: {
            event_type: researchMode ? { poster: 1 } : { corporate_announcement: 1 },
            publisher: { "Research Publisher": 1 },
            language: { en: 1 },
            venue: { "ASCO 2026": 1 },
          },
          as_of: "2026-07-24T08:00:00Z",
          warnings: [],
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=news");
  await expect(page.getByRole("heading", { name: "新闻、公告与会议动态" })).toBeVisible();
  await expect(page.getByRole("table", { name: "新闻与会议结果" })).toBeVisible();
  await page.getByRole("button", { name: "研究发布时间线" }).click();
  await expect(page).toHaveURL(/content_scope=research/);
  await expect(page).toHaveURL(/display=timeline/);
  await expect(page.getByRole("region", { name: "研究发布时间线" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ASCO 2026 EGFR poster" })).toBeVisible();
  await expect(page.getByText("会议海报", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "原始发布页" })).toHaveAttribute(
    "href",
    "https://example.test/asco/egfr-poster",
  );
  expect(requestedScopes).toContain("research");
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[epidemiology-patient-population] keeps a governed patient population filter stable", async ({ page }) => {
  const populationId = "550e8400-e29b-41d4-a716-446655440003";
  const diseaseId = "550e8400-e29b-41d4-a716-446655440001";
  const requestedPopulationIds: Array<string | null> = [];
  await page.route("**/api/v1/**", async (route) => {
    const requestUrl = new URL(route.request().url());
    const path = requestUrl.pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "epidemiology-user",
          tenant_id: "epidemiology-tenant",
          email: "epidemiology@example.test",
          display_name: "Epidemiology Analyst",
          role: "analyst",
        },
      });
    }
    const observation = {
      id: "550e8400-e29b-41d4-a716-446655440010",
      observation_identifier: "WHO-NSCLC-CN-2025",
      disease_entity_id: diseaseId,
      patient_population_id: populationId,
      measure: "prevalence",
      value: 158000,
      lower_bound: 150000,
      upper_bound: 166000,
      unit: "patients",
      geography: "China",
      population_scope: "adults",
      age_group: "18+",
      sex: "all",
      period_start: "2025-01-01T00:00:00Z",
      period_end: "2025-12-31T00:00:00Z",
      sample_size: 12500,
      methodology: "Registry-calibrated prevalence model",
      publisher_entity_id: null,
      source_document_id: "550e8400-e29b-41d4-a716-446655440011",
      disease_entity: { id: diseaseId, name: "EGFR-positive NSCLC", entity_type: "disease" },
      publisher_entity: null,
      patient_population: {
        id: populationId,
        population_key: "egfr-positive-nsclc-cn",
        name: "中国 EGFR 阳性 NSCLC 患者",
        description: "标准化生物标志物患者人群",
        attributes: { biomarker: "EGFR-positive" },
        disease_entities: [{ id: diseaseId, name: "EGFR-positive NSCLC", entity_type: "disease" }],
        target_entities: [{ id: "550e8400-e29b-41d4-a716-446655440004", name: "EGFR", entity_type: "target" }],
      },
    };
    if (path === "/api/v1/epidemiology-observations") {
      requestedPopulationIds.push(requestUrl.searchParams.get("patient_population_id"));
      return route.fulfill({
        json: {
          items: [observation],
          total: 1,
          limit: 100,
          offset: 0,
          facets: {
            measure: { prevalence: 1 },
            geography: { China: 1 },
            unit: { patients: 1 },
            population_scope: { adults: 1 },
            age_group: { "18+": 1 },
            sex: { all: 1 },
            disease: { "EGFR-positive NSCLC": 1 },
            publisher: {},
          },
          patient_populations: [{ id: populationId, name: "中国 EGFR 阳性 NSCLC 患者", count: 1 }],
          query_schema_version: "pharma.epidemiology.search.v3",
          sort_by: "period_end",
          sort_direction: "desc",
          sort: [{ field: "period_end", direction: "desc" }],
          applied_filters: requestUrl.searchParams.get("patient_population_id")
            ? [{ field: "patient_population_id", operator: "eq", value: populationId }]
            : [],
          as_of: "2026-07-24T08:00:00Z",
          warnings: [],
        },
      });
    }
    if (path === `/api/v1/epidemiology-trends/${diseaseId}`) {
      requestedPopulationIds.push(requestUrl.searchParams.get("patient_population_id"));
      return route.fulfill({
        json: {
          disease: observation.disease_entity,
          items: [observation],
          total: 1,
          truncated: false,
          as_of: "2026-07-24T08:00:00Z",
          warnings: [],
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/research?view=epidemiology");
  await expect(page.getByRole("table", { name: "流行病学结果" })).toBeVisible();
  await expect(page.getByText("中国 EGFR 阳性 NSCLC 患者", { exact: true })).toBeVisible();
  await page.getByLabel("标准患者人群").selectOption(populationId);
  await page.getByRole("button", { name: "查询" }).click();
  await expect(page).toHaveURL(new RegExp(`patient_population_id=${populationId}`));
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText("标准患者人群");
  await expect(page.getByRole("region", { name: "已应用查询条件" })).toContainText(populationId);
  await page.getByRole("button", { name: "查看 EGFR-positive NSCLC 同口径趋势" }).click();
  await expect(page.getByRole("region", { name: "EGFR-positive NSCLC 同口径趋势" })).toBeVisible();
  expect(requestedPopulationIds).toContain(populationId);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[comparison-export] compares stable entities and downloads a governed export", async ({ page }) => {
  const setId = "22222222-2222-4222-8222-222222222222";
  const entity = {
    id: "11111111-1111-4111-8111-111111111111",
    entity_type: "target",
    name: "EGFR",
    description: "Epidermal growth factor receptor",
    external_ids: { uniprot: "P00533" },
    attributes: {},
    review_status: "approved",
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T10:00:00Z",
  };
  const emptySet = {
    id: setId,
    owner_user_id: "comparison-user",
    name: "EGFR competitive landscape",
    description: "",
    visibility: "tenant",
    version: 1,
    member_count: 0,
    editable: true,
    members: [],
    created_at: "2026-07-18T10:00:00Z",
    updated_at: "2026-07-18T10:00:00Z",
  };
  let detail: Record<string, unknown> = emptySet;
  let exportRequested = false;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "comparison-user",
          tenant_id: "comparison-tenant",
          email: "comparison@example.test",
          display_name: "Comparison Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/comparison-sets" && request.method() === "GET") return route.fulfill({ json: [detail] });
    if (path === `/api/v1/comparison-sets/${setId}` && request.method() === "GET")
      return route.fulfill({ json: detail });
    if (path === "/api/v1/workspace/export-policy") {
      return route.fulfill({
        json: {
          id: "policy-browser-1",
          policy_version: "browser-v1",
          enabled: true,
          allowed_formats: ["json", "xlsx"],
          allowed_fields: ["position", "id", "entity_type", "name", "external_ids"],
          max_records_per_export: 20,
          attribution: "Internal browser acceptance",
          configured_by_user_id: "browser-admin",
          policy_sha256: "a".repeat(64),
          created_at: "2026-07-18T10:00:00Z",
          updated_at: "2026-07-18T10:00:00Z",
        },
      });
    }
    if (path === "/api/v1/entities" && request.method() === "GET") {
      return route.fulfill({
        json: {
          items: [entity],
          total: 1,
          limit: 25,
          offset: 0,
          facets: {},
          suggestions: [],
          engine: "opensearch",
          took_ms: 1,
        },
      });
    }
    if (path === `/api/v1/comparison-sets/${setId}/members` && request.method() === "POST") {
      detail = {
        ...emptySet,
        version: 2,
        member_count: 1,
        members: [
          {
            id: "member-browser-1",
            position: 0,
            added_by_user_id: "comparison-user",
            created_at: "2026-07-18T10:00:00Z",
            entity,
          },
        ],
      };
      return route.fulfill({ json: detail });
    }
    if (path === `/api/v1/comparison-sets/${setId}/export` && request.method() === "POST") {
      exportRequested = true;
      return route.fulfill({
        body: JSON.stringify({ schema: "pharma.workspace-comparison-export.v1", records: [entity] }),
        contentType: "application/json",
        headers: { "Content-Disposition": `attachment; filename="comparison-${setId}-v2.json"` },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/?view=collections");
  await expect(page.getByRole("heading", { name: "企业对比与列表" })).toBeVisible();
  await expect(page.getByText("工作台导出策略", { exact: true })).toHaveCount(0);
  await expect(page.getByText("租户导出策略", { exact: true })).toHaveCount(0);
  await page.getByLabel("搜索要加入的实体").fill("EGFR");
  await page.getByRole("button", { name: "检索", exact: true }).click();
  await page.getByRole("button", { name: "加入 EGFR" }).click();
  await expect(page.getByText("P00533", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出", exact: true }).click();
  const artifact = await download;
  expect(artifact.suggestedFilename()).toBe(`comparison-${setId}-v2.json`);
  await expect.poll(() => exportRequested).toBe(true);
  const hasOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasOverflow).toBe(false);
});

test("[session-recovery] presents and recovers from an identity service failure", async ({ page }) => {
  let recovered = false;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") {
      return recovered
        ? route.fulfill({ json: { mode: "local" } })
        : route.fulfill({ status: 503, json: { detail: "Identity service unavailable" } });
    }
    if (path === "/api/v1/auth/me") {
      return route.fulfill({ status: 401, json: { detail: "Authentication required" } });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/");
  await expect(page.getByText("Identity service unavailable", { exact: true })).toBeVisible();
  recovered = true;
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
});

test("[permission-boundary] rejects a protected workspace deep link for a viewer", async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "browser-viewer",
          tenant_id: "browser-tenant",
          email: "viewer@example.test",
          display_name: "Browser Viewer",
          role: "viewer",
        },
      });
    }
    if (path === "/api/v1/entities") {
      return route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 1,
          offset: 0,
          facets: {},
          suggestions: [],
          engine: "opensearch",
          took_ms: 1,
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/workspace/internal?view=governance");
  expect(await page.evaluate(() => document.documentElement.dataset.workbench)).toBe("internal");
  await expect(page.getByText("无权访问该工作区", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "AI 审核" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "数据工厂" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "商业运营" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "企业管理" })).toHaveCount(0);
  await page.getByRole("button", { name: "退出内部工作台" }).click();
  await expect(page).toHaveURL(/\/workspace\/internal/);
  await expect(page.getByRole("heading", { name: "内部管理工作台" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "医药情报工作台" })).toHaveCount(0);
});

test("[real-permission-boundary] keeps external reads and rejects internal operations for a real viewer", async ({
  page,
}, testInfo) => {
  testInfo.setTimeout(120_000);
  const email = process.env.E2E_PERMISSION_EMAIL;
  const password = process.env.E2E_PERMISSION_PASSWORD;
  test.skip(!email || !password, "Real viewer permission credentials are required");
  if (!email || !password) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const externalRead = await page.request.get("/api/v1/entities?limit=1&offset=0");
  expect(externalRead.status()).toBe(200);
  const internalRead = await page.request.get("/api/v1/enterprise/overview");
  expect(internalRead.status()).toBe(403);

  await page.goto("/workspace/internal?view=governance");
  await expect(page.getByText("无权访问该工作区", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "数据工厂" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "商业运营" })).toHaveCount(0);

  await page.goto("/workspace/research?view=explorer");
  await expect(page.getByRole("heading", { name: "全局情报检索", level: 1 })).toBeVisible();
  await expect(page.locator("main")).not.toContainText("无权访问该工作区");
});

test("[real-target-dossier] traverses a target dossier across governed domains through real APIs", async ({
  page,
}, testInfo) => {
  testInfo.setTimeout(120_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const targetId = process.env.E2E_PIPELINE_TARGET_ID;
  test.skip(
    !credentials || !fixtureKeyBase || !targetId,
    "Authenticated browser fixture credentials and a target dossier ID are required",
  );
  if (!credentials || !fixtureKeyBase || !targetId) return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  const dossierResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === `/api/v1/targets/${targetId}/dossier` && response.request().method() === "GET";
  });
  await page.goto(`/workspace/research?view=target&entity=${targetId}&section=overview`);
  const dossierResponse = await dossierResponsePromise;
  expect(dossierResponse.status()).toBe(200);
  const dossier = (await dossierResponse.json()) as {
    entity?: { id?: string };
    programs?: unknown[];
    clinical_trials?: unknown[];
    patents?: unknown[];
    deals?: unknown[];
    regulatory_events?: unknown[];
    news_events?: unknown[];
    activities?: unknown[];
    structures?: unknown[];
  };
  expect(dossier.entity?.id).toBe(targetId);
  const dossierCollections = [
    "programs",
    "clinical_trials",
    "patents",
    "deals",
    "regulatory_events",
    "news_events",
    "activities",
    "structures",
  ] as const;
  for (const collection of dossierCollections) expect(Array.isArray(dossier[collection])).toBe(true);
  for (const collection of [
    "programs",
    "clinical_trials",
    "patents",
    "deals",
    "news_events",
    "activities",
    "structures",
  ] as const) {
    expect(dossier[collection]?.length, `${collection} must contain a governed dossier record`).toBeGreaterThan(0);
  }

  await expect(
    page.getByRole("heading", { name: `Browser pipeline target ${fixtureKeyBase}`, exact: true }),
  ).toBeVisible();
  const dossierSections: ReadonlyArray<readonly [string, string]> = [
    ["overview", "概览"],
    ["relationships", "关系网络"],
    ["evidence", "转化证据"],
    ["activities", "活性数据"],
    ["pipeline", "竞品管线"],
    ["trials", "临床试验"],
    ["patents", "专利"],
    ["deals", "交易"],
    ["regulatory", "监管动态"],
    ["news", "新闻与会议"],
    ["structures", "结构"],
  ];
  for (const [section, label] of dossierSections) {
    await page.goto(`/workspace/research?view=target&entity=${targetId}&section=${section}`);
    await expect(page.getByRole("tab", { name: label, exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel")).toBeVisible();
    await expect(page.locator("main")).not.toContainText("加载失败");
    if (section === "activities") {
      await expect(page.getByRole("table", { name: "靶点标准化活性记录" })).toContainText("IC50");
    }
    if (section === "structures") {
      await expect(page.getByText("BSYNRYMUTXBXSQ-UHFFFAOYSA-N", { exact: true })).toBeVisible();
    }
  }

  const sarResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname === `/api/v1/targets/${targetId}/sar-comparison` && response.request().method() === "GET";
  });
  await page.goto(`/workspace/research?view=target&entity=${targetId}&section=sar`);
  const sarResponse = await sarResponsePromise;
  expect(sarResponse.status()).toBe(200);
  const sarPayload = (await sarResponse.json()) as { total?: number; items?: unknown[] };
  expect(sarPayload.total).toBeGreaterThan(0);
  expect(sarPayload.items?.length).toBeGreaterThan(0);
  await expect(page.getByRole("tab", { name: "SAR 对比", exact: true })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("table", { name: "SAR 活性对比结果" })).toContainText("IC50");
  await expect(page.getByRole("tabpanel")).toBeVisible();
  testInfo.annotations.push({
    type: "real-target-dossier",
    description: JSON.stringify({
      dossier_api_status: dossierResponse.status(),
      sar_api_status: sarResponse.status(),
      populated_domains: ["programs", "clinical_trials", "patents", "deals", "news_events", "activities", "structures"],
      empty_allowed_domains: ["regulatory_events"],
    }),
  });
});

test("[workspace-states] renders loading, error, recovery and empty search states", async ({ page }) => {
  let releaseSearch: (() => void) | undefined;
  const blockedSearch = new Promise<void>((resolve) => {
    releaseSearch = resolve;
  });
  let searchAttempts = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/auth/config") return route.fulfill({ json: { mode: "local" } });
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        json: {
          id: "browser-analyst",
          tenant_id: "browser-tenant",
          email: "analyst@example.test",
          display_name: "Browser Analyst",
          role: "analyst",
        },
      });
    }
    if (path === "/api/v1/entities") {
      searchAttempts += 1;
      if (searchAttempts === 1) {
        await blockedSearch;
      }
      if (searchAttempts <= 3) return route.fulfill({ status: 503, json: { detail: "Search backend unavailable" } });
      return route.fulfill({
        json: {
          items: [],
          total: 0,
          limit: 100,
          offset: 0,
          facets: {},
          suggestions: [],
          engine: "opensearch",
          took_ms: 1,
        },
      });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/?view=explorer&q=EGFR&type=target");
  await expect(page.getByText("正在检索结构化情报", { exact: true })).toBeVisible();
  releaseSearch?.();
  await expect(page.getByText("Search backend unavailable", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "重试" }).click();
  await expect(page.getByText("未找到匹配实体", { exact: true })).toBeVisible();
  await expect(page.getByLabel("情报检索词")).toHaveValue("EGFR");
  await expect(page.getByRole("button", { name: /对象类型：靶点/ })).toHaveAttribute("aria-pressed", "true");
});

test("[chemistry][chemistry-real-api] queries governed structures with the bundled RDKit runtime", async ({
  page,
}, testInfo) => {
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKey = process.env.E2E_FIXTURE_KEY;
  const expectedEntityId = process.env.E2E_REGULATORY_SUBJECT_ID;
  test.skip(
    !credentials || !fixtureKey || !expectedEntityId,
    "Real chemistry fixture and browser credentials are required",
  );
  if (!credentials || !fixtureKey || !expectedEntityId) return;
  const aspirinSmiles = "CC(=O)Oc1ccccc1C(=O)O";
  const expectedEntityName = `Browser regulatory drug ${fixtureKey}`;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await openNavigation(page);
  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "结构检索", exact: true }).click();
  const deferredResourcePattern = /(?:\.wasm$|rdkit|indigo|ketcher|structureeditor)/i;
  const chemistryResourcesBeforeEditor = await page.evaluate(() =>
    (performance.getEntriesByType("resource") as PerformanceResourceTiming[]).map(
      (entry) => new URL(entry.name).pathname,
    ),
  );
  expect(chemistryResourcesBeforeEditor.filter((path) => deferredResourcePattern.test(path))).toEqual([]);
  await page.getByRole("button", { name: "打开结构画板" }).click();
  await expect(page.getByRole("region", { name: "结构式编辑器" })).toBeVisible();
  await expect
    .poll(async () =>
      page.evaluate(() =>
        (performance.getEntriesByType("resource") as PerformanceResourceTiming[]).some((entry) =>
          /structureeditor/i.test(new URL(entry.name).pathname),
        ),
      ),
    )
    .toBe(true);
  await page.getByRole("button", { name: "Benzene (T)" }).click();
  const structureCanvas = page.getByRole("application");
  const structureCanvasBox = await structureCanvas.boundingBox();
  expect(structureCanvasBox).not.toBeNull();
  await structureCanvas.click({
    position: {
      x: Math.round((structureCanvasBox?.width ?? 0) / 2),
      y: Math.round((structureCanvasBox?.height ?? 0) / 2),
    },
  });
  await page.getByRole("button", { name: "应用到检索" }).click();
  await expect(page.getByRole("status").filter({ hasText: "结构已用于本次检索" })).toHaveText("结构已用于本次检索");
  await page.getByRole("tab", { name: "高级输入" }).click();
  await expect(page.getByLabel("SMILES")).not.toHaveValue("");
  await page.getByLabel("SMILES").fill(aspirinSmiles);
  const chemistryResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/chemistry/search",
  );
  await page.getByRole("button", { name: "检索", exact: true }).click();
  const chemistryResponse = await chemistryResponsePromise;
  expect(chemistryResponse.status()).toBe(200);
  const chemistryPayload = (await chemistryResponse.json()) as {
    mode: string;
    normalized_query: string;
    count: number;
    items: Array<{ entity_id: string; entity_name: string; standard_inchi_key: string }>;
  };
  expect(chemistryPayload.mode).toBe("exact");
  expect(chemistryPayload.normalized_query).toBe(aspirinSmiles);
  expect(chemistryPayload.count).toBe(1);
  expect(chemistryPayload.items).toEqual([
    expect.objectContaining({
      entity_id: expectedEntityId,
      entity_name: expectedEntityName,
      standard_inchi_key: "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
    }),
  ]);

  await expect(page.getByRole("heading", { name: expectedEntityName })).toBeVisible();
  const depiction = page.locator(".molecule-depiction");
  await expect(depiction).toHaveCount(1);
  await expect(depiction).toHaveAttribute("data-rdkit-version", /\S+/);
  const image = depiction.locator("img");
  await expect(image).toBeVisible();
  expect(await image.evaluate((element) => ({ width: element.naturalWidth, height: element.naturalHeight }))).toEqual({
    width: 360,
    height: 180,
  });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );

  await page.getByRole("button", { name: "保存结构检索", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "保存当前结构检索" })).toBeVisible();
  const savedSearchName = `Aspirin structure ${fixtureKey}`;
  await page.getByRole("dialog").getByLabel("名称").fill(savedSearchName);
  const savedSearchResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/monitoring/saved-searches",
  );
  await page.getByRole("dialog").getByRole("button", { name: "确认保存" }).click();
  const savedSearchResponse = await savedSearchResponsePromise;
  expect(savedSearchResponse.status()).toBe(201);
  const savedSearchPayload = (await savedSearchResponse.json()) as {
    id: string;
    query_type: string;
    query_json: { mode: string; query: string };
  };
  expect(savedSearchPayload.query_type).toBe("chemistry_search");
  expect(savedSearchPayload.query_json.query).toBe(aspirinSmiles);
  await expect(page).toHaveURL(new RegExp(`/workspace/research\\?view=chemistry&saved=${savedSearchPayload.id}`));
  expect(new URL(page.url()).search).not.toContain("CC(=O)");

  const restoredChemistryResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" && new URL(response.url()).pathname === "/api/v1/chemistry/search",
  );
  await page.reload();
  const restoredChemistryResponse = await restoredChemistryResponsePromise;
  expect(restoredChemistryResponse.status()).toBe(200);
  await expect(page.getByRole("heading", { name: expectedEntityName })).toBeVisible();

  await page.getByRole("button", { name: "查看实体", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/workspace/research\\?view=(?:entity|drug)&entity=${expectedEntityId}`));
  await expect(page.getByRole("heading", { name: expectedEntityName })).toBeVisible();
});
