import { expect, type PlaywrightTestArgs, type PlaywrightWorkerArgs, type TestInfo, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import type { DiseaseDossierResponse } from "../../src/lib/generated";
import { selectInterfaceLanguage } from "../interface-language";
import { verifyResearchNavigationHierarchy } from "./research-navigation";

export async function verifyResearcherReview(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(120_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const ids = [
    process.env.E2E_PIPELINE_TARGET_ID,
    process.env.E2E_PIPELINE_DRUG_B_ID,
    process.env.E2E_PIPELINE_ORGANIZATION_ID,
    process.env.E2E_PIPELINE_DISEASE_ID,
    process.env.E2E_DEAL_ENTITY_ID,
  ];
  test.skip(
    !credentials || ids.some((id) => !id),
    "A dedicated authenticated fixture with five governed dossier identities is required",
  );
  if (!credentials || ids.some((id) => !id)) return;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/workspace/research");
  await selectInterfaceLanguage(page, "zh-CN");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();

  async function noOverflow() {
    const layout = await page.evaluate(() => {
      const width = document.documentElement.clientWidth;
      return {
        width,
        scrollWidth: document.documentElement.scrollWidth,
        overflow: [...document.querySelectorAll("main *")]
          .filter((element) => element.getBoundingClientRect().right > width + 1)
          .slice(0, 12)
          .map((element) => ({
            tag: element.tagName,
            class: element.className,
            width: element.getBoundingClientRect().width,
          })),
      };
    });
    expect(layout.scrollWidth, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width);
  }
  await verifyResearchNavigationHierarchy(page);
  for (const [index, view] of ["target", "drug", "company", "disease", "entity"].entries()) {
    const diseaseResponse =
      view === "disease"
        ? page.waitForResponse(
            (response) => new URL(response.url()).pathname === `/api/v1/diseases/${ids[index]}/dossier`,
          )
        : null;
    await page.goto(`/workspace/research?view=${view}&entity=${ids[index]}`);
    await expect(page.locator(".page-heading h1")).toBeVisible();
    const overviewLabel =
      view === "drug" ? "药物概览" : view === "company" ? "公司概览" : view === "disease" ? "疾病概览" : "概览";
    await expect(page.getByRole("tab", { name: overviewLabel, exact: true })).toBeVisible();
    await expect(page.getByText("正在加载研究工作区", { exact: true })).toHaveCount(0);
    if (diseaseResponse) {
      const data = (await (await diseaseResponse).json()) as DiseaseDossierResponse;
      const available = data.coverage.filter((item) => item.total > 0).length + Number(data.epidemiology.total > 0);
      const disclosure = page.locator(".dossier-coverage-disclosure");
      await expect(disclosure).toContainText(`${available} / ${data.coverage.length + 1} 个信息领域有记录`);
      if (available) await expect(disclosure).toHaveAttribute("open", "");
      else await expect(disclosure).not.toHaveAttribute("open", "");
    }
    await noOverflow();
    await page.screenshot({ path: testInfo.outputPath(`researcher-${view}.png`), fullPage: true });
  }
  await page.goto("/workspace/research?view=trials");
  const design = page.locator("details").filter({ has: page.getByText("试验设计与注册信息", { exact: true }) });
  await expect(design).not.toHaveAttribute("open", "");
  await design.locator(":scope > summary").click();
  await page.getByLabel("试验简称", { exact: true }).fill("Researcher check");
  await design.locator(":scope > summary").click();
  await design.locator(":scope > summary").click();
  await expect(page.getByLabel("试验简称", { exact: true })).toHaveValue("Researcher check");
  await noOverflow();
  await page.screenshot({ path: testInfo.outputPath("researcher-clinical-filters.png"), fullPage: true });
  for (const view of ["factory", "governance", "commercial", "enterprise"]) {
    await page.goto(`/workspace/internal?view=${view}`);
    await expect(page.locator(".page-heading h1")).toBeVisible();
    if (view === "factory") await expect(page.getByRole("heading", { name: "自动数据源", exact: true })).toBeVisible();
    else {
      const label = view === "governance" ? "治理队列" : view === "commercial" ? "商业运营视图" : "企业管理视图";
      await expect(page.getByRole("tablist", { name: label, exact: true })).toBeVisible();
    }
    await expect(page.locator("main .spinner")).toHaveCount(0);
    await expect(page.locator("main [role=alert]")).toHaveCount(0);
    await noOverflow();
    await page.screenshot({ path: testInfo.outputPath(`researcher-${view}.png`), fullPage: true });
  }
  await page.goto("/workspace/internal?view=environment");
  await expect(page.getByRole("heading", { name: "运行环境与安装管理", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "依赖就绪概览", exact: true })).toBeVisible();
  const gatewayDetails = page.locator("details").filter({ has: page.getByText("查看网关依赖明细", { exact: true }) });
  if ((await gatewayDetails.getAttribute("open")) === null) await gatewayDetails.locator(":scope > summary").click();
  await expect(page.getByRole("table", { name: "网关依赖版本" })).toBeVisible();
  await expect(page.getByRole("table", { name: "网关依赖版本" }).getByRole("columnheader")).toHaveCount(4);
  await expect(page.getByText(/未声明明确版本要求时，不判定为兼容/)).toBeVisible();
  await noOverflow();
  await page.screenshot({ path: testInfo.outputPath("researcher-environment-detection.png"), fullPage: true });
  await page.getByRole("tab", { name: "安装与修复" }).click();
  await expect(page.getByRole("checkbox", { name: "仅使用离线缓存（缺失时失败，不自动联网）" })).toBeChecked();
  await expect(page.getByRole("button", { name: "立即安装", exact: true })).toHaveCount(0);
  await noOverflow();
  await page.screenshot({ path: testInfo.outputPath("researcher-environment.png"), fullPage: true });
  expect(errors).toEqual([]);
}
