import { expect } from "@playwright/test";
import type { verifyDenseResultAndLandscape } from "./dense-result-and-landscape";

export async function verifyTablePreferencesAndQuickDetail(
  context: Awaited<ReturnType<typeof verifyDenseResultAndLandscape>>,
) {
  const { page, browser, testInfo, credentials, fixtureKey, fixtureName, createdEntity, companyName } = context;
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
  const previewUrl = page.url();
  const sourceUrl = new URL(previewUrl);
  await page.getByRole("button", { name: "打开靶点全景" }).click();
  await expect(page.getByRole("heading", { name: fixtureName, exact: true })).toBeVisible();
  expect(new URL(page.url()).searchParams.get("from")).toBe(`${sourceUrl.pathname}${sourceUrl.search}`);
  await page.reload();
  await page.getByRole("button", { name: "返回情报检索", exact: true }).click();
  await expect(page).toHaveURL(previewUrl);
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
  return { ...context, configuredEntityTable, restoredEntityTable, entityNameHeader };
}
