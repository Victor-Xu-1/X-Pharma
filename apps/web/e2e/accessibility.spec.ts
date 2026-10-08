import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../src/lib/browserAcceptanceCredentials";
import { verifyKeyboardReflow } from "./accessibility/reflow-keyboard";
import { expectNamedKeyboardScrollableTables } from "./accessibility/reflow-support";
import { selectInterfaceLanguage } from "./interface-language";

const wcagTags = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"];

const researchViews = [
  ["overview", "用户中心"],
  ["explorer", "全局情报检索"],
  ["pipeline", "药物与研发管线"],
  ["trials", "临床试验与结果"],
  ["patents", "专利族与资产关联"],
  ["deals", "交易、参与方与资产关联"],
  ["regulatory", "监管事件与安全时间线"],
  ["epidemiology", "流行病学与疾病负担"],
  ["news", "新闻、公告与会议动态"],
  ["chemistry", "化学结构检索"],
  ["evidence", "原始资料查证"],
  ["knowledge", "版本化知识专题"],
  ["monitoring", "情报监控与变更提醒"],
  ["collections", "对比列表"],
] as const;

function formatViolations(context: string, violations: Awaited<ReturnType<AxeBuilder["analyze"]>>["violations"]) {
  return [
    `${context} has ${violations.length} WCAG A/AA violation groups`,
    ...violations.map(
      (violation) =>
        `${violation.id} (${violation.impact ?? "unknown"}): ${violation.help}\n${violation.nodes
          .map((node) => `  ${node.target.join(" ")}: ${node.failureSummary ?? "no failure summary"}`)
          .join("\n")}`,
    ),
  ].join("\n");
}

async function findWcagViolations(page: Page, context: string) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
  });
  const results = await new AxeBuilder({ page }).withTags(wcagTags).analyze();
  return results.violations.length ? formatViolations(context, results.violations) : null;
}

async function expectSharedLightTheme(page: Page) {
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(page.locator("h1").first()).toHaveCSS("font-family", /sans-serif/);
  const sidebar = page.locator(".workspace-sidebar");
  if (await sidebar.count()) {
    await expect(sidebar).toHaveCSS("background-color", "rgb(249, 249, 249)");
    await expect(sidebar).toHaveCSS("color", "rgb(48, 48, 48)");
  }
}

test("[accessibility] passes WCAG 2.2 A/AA across the public login and every external work domain", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  test.skip(!credentials, "Authenticated browser fixture credentials are required");
  if (!credentials) return;

  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
  await expectSharedLightTheme(page);
  const violations = [await findWcagViolations(page, "public login")].filter((value): value is string =>
    Boolean(value),
  );

  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索", level: 1 })).toBeVisible();

  for (const [view, heading] of researchViews) {
    await page.goto(`/workspace/research?view=${view}`);
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectSharedLightTheme(page);
    await expectNamedKeyboardScrollableTables(page, `${view} work domain`);
    const violation = await findWcagViolations(page, `${view} work domain`);
    if (violation) violations.push(violation);
  }

  expect(violations, violations.join("\n\n")).toEqual([]);
});

test("[accessibility-dossier] passes WCAG 2.2 A/AA across every professional dossier section", async ({
  page,
}, testInfo) => {
  test.setTimeout(180_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const targetId = process.env.E2E_PIPELINE_TARGET_ID;
  const drugId = process.env.E2E_PIPELINE_DRUG_B_ID;
  const companyId = process.env.E2E_PIPELINE_ORGANIZATION_ID;
  const diseaseId = process.env.E2E_EPIDEMIOLOGY_DISEASE_ID;
  const trialId = process.env.E2E_TRIAL_PROFILE_ID;
  const patentId = process.env.E2E_PATENT_FAMILY_ID;
  const dealId = process.env.E2E_DEAL_PROFILE_ID;
  test.skip(
    !credentials || !targetId || !drugId || !companyId || !diseaseId || !trialId || !patentId || !dealId,
    "Authenticated browser credentials and stable dossier IDs are required",
  );
  if (!credentials || !targetId || !drugId || !companyId || !diseaseId || !trialId || !patentId || !dealId) return;

  await page.goto("/");
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("heading", { name: "账户登录" })).toBeVisible();
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索", level: 1 })).toBeVisible();

  // Professional dossiers render UI that the list-view audit never reaches: separate
  // tab lists, coverage grids, timelines, terms and provenance drawers.
  const dossierRoutes: readonly (readonly [string, string])[] = [
    ["target", `/workspace/research?view=target&entity=${targetId}`],
    ["drug", `/workspace/research?view=drug&entity=${drugId}`],
    ["company", `/workspace/research?view=company&entity=${companyId}`],
    ["disease", `/workspace/research?view=disease&entity=${diseaseId}`],
    ["entity", `/workspace/research?view=entity&entity=${targetId}`],
    ["clinical trial overview", `/workspace/research?view=trials&trial=${trialId}`],
    ["clinical trial design", `/workspace/research?view=trials&trial=${trialId}&section=design`],
    ["clinical trial outcomes", `/workspace/research?view=trials&trial=${trialId}&section=outcomes`],
    ["clinical trial timeline", `/workspace/research?view=trials&trial=${trialId}&section=timeline`],
    ["patent family overview", `/workspace/research?view=patents&patent=${patentId}`],
    ["patent family timeline", `/workspace/research?view=patents&patent=${patentId}&section=timeline`],
    ["patent family relationships", `/workspace/research?view=patents&patent=${patentId}&section=relationships`],
    ["deal overview", `/workspace/research?view=deals&deal=${dealId}`],
    ["deal parties", `/workspace/research?view=deals&deal=${dealId}&section=parties`],
    ["deal assets", `/workspace/research?view=deals&deal=${dealId}&section=assets`],
    ["deal rights", `/workspace/research?view=deals&deal=${dealId}&section=rights`],
    ["deal terms", `/workspace/research?view=deals&deal=${dealId}&section=terms`],
  ];

  const violations: string[] = [];
  for (const [label, path] of dossierRoutes) {
    await page.goto(path);
    await expect(page.locator("main h1").first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectNamedKeyboardScrollableTables(page, `${label} dossier`);
    const violation = await findWcagViolations(page, `${label} dossier`);
    if (violation) violations.push(violation);
  }

  expect(violations, violations.join("\n\n")).toEqual([]);
});

test(
  "[reflow-keyboard] preserves the primary research path at 320 CSS pixels with keyboard activation",
  verifyKeyboardReflow,
);
