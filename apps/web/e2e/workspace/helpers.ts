import { expect, type Locator, type Page, type Route } from "@playwright/test";
import { researchWorkflows } from "../../src/lib/workspace/researchNavigation";
import type { ViewKey } from "../../src/lib/workspaceRouting";

export type BrowserQualityMetrics = {
  cls: number;
  inp_ms: number;
  interaction_count: number;
  lcp_ms: number;
};

export async function expandProfessionalQuery(page: Page) {
  const filters = page.locator("details.explorer-professional-query");
  if ((await filters.getAttribute("open")) === null) await filters.locator(":scope > summary").click();
}

export async function installBrowserQualityProbe(page: Page) {
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
    const eventOptions: PerformanceObserverInit & { durationThreshold: number } = {
      type: "event",
      buffered: true,
      durationThreshold: 16,
    };

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
    }).observe(eventOptions);
  });
}

export async function readBrowserQualityMetrics(page: Page): Promise<BrowserQualityMetrics> {
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

export async function openNavigation(page: Page) {
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

export async function navigateResearchView(page: Page, view: ViewKey) {
  const workflow = researchWorkflows.find((item) => item.destinations.some((destination) => destination.view === view));
  if (!workflow) throw new Error(`No research navigation destination: ${view}`);
  await openNavigation(page);
  await page
    .getByRole("navigation", { name: "主导航" })
    .getByRole("button", { name: workflow.label, exact: true })
    .click();
  if (workflow.destinations[0].view !== view) {
    const destination = workflow.destinations.find((item) => item.view === view);
    await page
      .getByRole("navigation", { name: `${workflow.label}分类`, exact: true })
      .getByRole("button", { name: destination?.label, exact: true })
      .click();
  }
  await expect.poll(() => new URL(page.url()).searchParams.get("view")).toBe(view);
}

export async function findDataFactoryRunRow(page: Page, workflowId: string): Promise<Locator> {
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

export async function findSourceAssetRow(page: Page, fileName: string): Promise<Locator> {
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

export async function verifyProfessionalRefreshLifecycle({
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

export async function verifyProfessionalErrorPermissionLifecycle({
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
