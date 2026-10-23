import { expect } from "@playwright/test";
import { expandProfessionalQuery, verifyProfessionalRefreshLifecycle } from "../helpers";
import type { verifyProfessionalQueryDomains } from "./professional-query-domains";

export async function verifyNewsDealAndPatentDetails(
  context: Awaited<ReturnType<typeof verifyProfessionalQueryDomains>>,
) {
  const { page, fixtureKeyBase, pipelineTargetId, patentFamilyId, newsEventId, dealProfileId } = context;
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
  await expect(restoredProfessionalNewsFilters.getByRole("group", { name: "关联实体检索与选择" })).toContainText(
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
  await expect.soft(dealRightsVisual).toHaveScreenshot("research-deal-rights.png", {
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
  await expect.soft(patentTimelineVisual).toHaveScreenshot("research-patent-timeline.png", {
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
  return {
    ...context,
    newsProfessionalQuery,
    professionalNewsEntityName,
    professionalNewsPublishedRange,
    professionalNewsResponse,
    professionalNewsPayload,
    restoredProfessionalNewsFilters,
    professionalNewsTimeline,
    governedDealFilters,
    dealTitle,
    governedDealTable,
    dealRightsVisual,
    patentFilters,
    patentIdentifier,
    patentTitle,
    patentTable,
    patentTimelineVisual,
  };
}
