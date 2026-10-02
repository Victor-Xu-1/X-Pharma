import type { Page, Route, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";

export async function verifyDossierSourceReturn(
  page: Page,
  testInfo: TestInfo,
  records: { targetId: string; targetName: string; drugId: string; query: string },
) {
  await page.goto(
    `/workspace/research?view=explorer&q=${encodeURIComponent(records.query)}&types=target&review=verified&sort=name%3Aasc&entity=${records.targetId}`,
  );
  await expect(page.getByRole("dialog", { name: records.targetName })).toBeVisible();
  testInfo.annotations.push({
    type: "source-preview-geometry",
    description: JSON.stringify(
      await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        documentWidth: document.documentElement.scrollWidth,
        overflow: Array.from(document.querySelectorAll<HTMLElement>("main *, .drawer-scrim, .entity-detail-drawer"))
          .filter((element) => element.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
          .slice(0, 12)
          .map((element) => ({
            tag: element.tagName,
            class: element.className,
            right: element.getBoundingClientRect().right,
            width: element.getBoundingClientRect().width,
          })),
      })),
    ),
  });
  const queryCheck = await page.request.get(
    `/api/v1/entities?q=${encodeURIComponent(records.query)}&entity_type=target&review_status=verified&sort=name%3Aasc`,
  );
  expect(queryCheck.ok()).toBe(true);
  const queryResult = (await queryCheck.json()) as { total: number; items: Array<{ id: string }> };
  expect(queryResult.total).toBe(1);
  expect(queryResult.items.map((item) => item.id)).toEqual([records.targetId]);
  const source = new URL(page.url());
  const sourcePath = `${source.pathname}${source.search}`;
  await page.getByRole("button", { name: "打开靶点全景", exact: true }).click();
  await expect(page.getByRole("heading", { name: records.targetName, exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "返回情报检索", exact: true })).toHaveCount(1);
  await page.getByRole("button", { name: "返回情报检索", exact: true }).click();
  await expect(page).toHaveURL(source.href);
  await expect(page.getByRole("dialog", { name: records.targetName })).toBeVisible();

  const cases = [
    { view: "drug", id: records.drugId, path: `/api/v1/entities/${records.drugId}`, loading: "正在恢复药物档案深链接" },
    {
      view: "target",
      id: records.targetId,
      path: `/api/v1/entities/${records.targetId}`,
      loading: "正在恢复靶点深链接",
    },
    {
      view: "trials",
      id: "550e8400-e29b-41d4-a716-446655440099",
      path: "/api/v1/trials/550e8400-e29b-41d4-a716-446655440099",
      loading: "正在加载临床试验专业档案",
    },
  ];
  for (const scenario of cases) {
    await test.step(`source-return-${scenario.view}-loading-error-reload`, async () => {
      const held: { route?: Route } = {};
      let released = false;
      const failure = { status: 503, json: { detail: "Controlled dossier lookup failure" } };
      const intercept = async (route: Route) => {
        if (!released) {
          held.route = route;
          return;
        }
        await route.fulfill(failure);
      };
      const pattern = `**${scenario.path}`;
      await page.route(pattern, intercept);
      try {
        const params = new URLSearchParams({ view: scenario.view, from: sourcePath });
        params.set(scenario.view === "trials" ? "trial" : "entity", scenario.id);
        await page.goto(`/workspace/research?${params}`);
        await expect.poll(() => Boolean(held.route)).toBe(true);
        const back = page.getByRole("button", { name: "返回情报检索", exact: true });
        await expect(back).toHaveCount(1);
        await expect(page.getByText(scenario.loading, { exact: true })).toBeVisible();
        await page.screenshot({ path: testInfo.outputPath(`${scenario.view}-source-return-loading.png`) });
        released = true;
        if (!held.route) throw new Error("The controlled dossier request did not start");
        await held.route.fulfill(failure);
        await expect(page.getByRole("alert")).toContainText("Controlled dossier lookup failure");
        await expect(back).toHaveCount(1);
        if (scenario.view === "trials")
          await expect(page.getByRole("button", { name: "返回试验列表", exact: true })).toHaveCount(0);
        await page.screenshot({ path: testInfo.outputPath(`${scenario.view}-source-return-error.png`) });
        await page.reload();
        await expect(back).toHaveCount(1);
        await expect(page.getByRole("alert")).toContainText("Controlled dossier lookup failure");
        await page.unroute(pattern, intercept);
        await back.click();
        await expect(page).toHaveURL(source.href);
        await expect(page.getByLabel("情报检索词", { exact: true })).toHaveValue(records.query);
        await expect(page.getByRole("dialog", { name: records.targetName })).toBeVisible();
        expect(new URL(page.url()).searchParams.getAll("sort")).toEqual(["name:asc"]);
        await page.getByRole("button", { name: "关闭实体详情", exact: true }).click();
        await expect(page.getByRole("table", { name: "实体检索结果" })).toBeVisible();
        await expect(page.getByRole("button", { name: /对象类型：靶点/ })).toHaveAttribute("aria-pressed", "true");
        await page.getByRole("button", { name: records.targetName, exact: true }).click();
        await expect(page).toHaveURL(source.href);
        await expect(page.getByRole("dialog", { name: records.targetName })).toBeVisible();
      } finally {
        released = true;
        await page.unroute(pattern, intercept);
      }
    });
  }
  await page.screenshot({ path: testInfo.outputPath("source-query-preview-restored.png") });
}
