import { expect, type PlaywrightTestArgs, type TestInfo, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { expectNamedKeyboardScrollableTables, expectPageReflow } from "./reflow-support";

export async function verifyKeyboardReflow({ page }: Pick<PlaywrightTestArgs, "page">, testInfo: TestInfo) {
  testInfo.setTimeout(120_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const targetId = process.env.E2E_PIPELINE_TARGET_ID;
  const trialId = process.env.E2E_TRIAL_PROFILE_ID;
  const patentId = process.env.E2E_PATENT_FAMILY_ID;
  const dealId = process.env.E2E_DEAL_PROFILE_ID;
  test.skip(
    !credentials || !targetId || !trialId || !patentId || !dealId,
    "Authenticated browser credentials and stable dossier IDs are required",
  );
  if (!credentials || !targetId || !trialId || !patentId || !dealId) return;

  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/");
  const email = page.getByLabel("工作邮箱");
  const password = page.getByLabel("密码");
  const submit = page.getByRole("button", { name: "进入工作台" });
  await email.focus();
  await page.keyboard.type(credentials.email);
  await page.keyboard.press("Tab");
  await expect(password).toBeFocused();
  await page.keyboard.type(credentials.password);
  await page.keyboard.press("Tab");
  await expect(submit).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "全局情报检索", level: 1 })).toBeVisible();
  await expect(page).toHaveURL(/\/workspace\/research\?view=explorer$/);
  await expectPageReflow(page, "research overview");

  const openNavigation = page.getByTitle("打开导航");
  await openNavigation.focus();
  await expect(openNavigation).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".workspace-sidebar")).toHaveClass(/mobile-open/);
  const pipelineButton = page.getByRole("button", { name: "药物与管线", exact: true });
  await pipelineButton.focus();
  await expect(pipelineButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "药物与研发管线", level: 1 })).toBeVisible();
  await expectPageReflow(page, "pipeline work domain");

  const governedResearchPaths = [
    "/workspace/research?view=explorer",
    `/workspace/research?view=target&entity=${targetId}`,
    `/workspace/research?view=trials&trial=${trialId}&section=outcomes`,
    `/workspace/research?view=patents&patent=${patentId}&section=timeline`,
    `/workspace/research?view=deals&deal=${dealId}&section=rights`,
    "/workspace/research?view=chemistry",
  ];
  const effectiveZoomViewports = [
    { label: "320 CSS px baseline", width: 320 },
    { label: "200% zoom-equivalent", width: 720 },
    { label: "400% zoom-equivalent", width: 360 },
  ] as const;
  for (const { label, width } of effectiveZoomViewports) {
    await page.setViewportSize({ width, height: 720 });
    for (const path of governedResearchPaths) {
      await page.goto(path);
      await expect(page.locator("main h1").first()).toBeVisible();
      await expectNamedKeyboardScrollableTables(page, `${label}: ${path}`);
      await expectPageReflow(page, `${label}: ${path}`);
    }
  }
}
