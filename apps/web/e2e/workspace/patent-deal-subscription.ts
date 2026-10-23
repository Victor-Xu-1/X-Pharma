import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";
import { selectInterfaceLanguage } from "../interface-language";

export async function verifyPatentDealSubscription(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
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
  await selectInterfaceLanguage(page, "zh-CN");
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
  await expect(page.getByRole("group", { name: "交易药品检索与选择" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await expect(page.getByRole("group", { name: "关联靶点检索与选择" })).toContainText(
    `Browser pipeline target ${fixtureKeyBase}`,
  );
  await expect(page.getByRole("group", { name: "关联适应症检索与选择" })).toContainText(
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
  await expect(dealFilters.getByLabel(/资产模态：/)).toBeVisible();
  await dealFilters.getByLabel(/资产模态：/).click();
  await expect(dealFilters.getByRole("checkbox", { name: /small molecule/ })).toBeChecked();
  await expect(dealFilters.getByRole("checkbox", { name: /antibody/ })).toBeChecked();
  await dealFilters.getByLabel(/资产项目标签：/).click();
  await expect(dealFilters.getByRole("checkbox", { name: /first_in_class/ })).toBeChecked();
  await expect(dealFilters.getByRole("checkbox", { name: /best_in_class/ })).toBeChecked();
  await expect(dealFilters.getByLabel("币种", { exact: true })).toHaveValue("USD");
  await expect(dealFilters.getByRole("group", { name: "交易药品检索与选择" })).toContainText(
    `Browser regulatory drug ${fixtureKeyBase}`,
  );
  await expect(dealFilters.getByRole("group", { name: "关联靶点检索与选择" })).toContainText(
    `Browser pipeline target ${fixtureKeyBase}`,
  );
  await expect(dealFilters.getByRole("group", { name: "关联适应症检索与选择" })).toContainText(
    `Browser regulatory indication ${fixtureKeyBase}`,
  );
  await page.reload();
  await expect(page.getByRole("table", { name: "参与方地区统计表" })).toContainText("US");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
}
