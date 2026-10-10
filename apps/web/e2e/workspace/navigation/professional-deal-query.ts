import { expect } from "@playwright/test";
import type { verifyNewsDealAndPatentDetails } from "./news-deal-and-patent-details";

type Context = Pick<
  Awaited<ReturnType<typeof verifyNewsDealAndPatentDetails>>,
  "page" | "companyName" | "createdCompany"
>;

/** The same focused actor is reused by integrated navigation and changed-query acceptance. */
export async function verifyProfessionalDealQuery({ page, companyName, createdCompany }: Context) {
  await page.goto("/workspace/research?view=deals&q=license");
  const dealFilters = page.getByRole("form", { name: "交易筛选" });
  await expect(dealFilters.getByLabel("关键词")).toHaveValue("license");
  await dealFilters.getByLabel("交易状态").selectOption("active");
  await expect(dealFilters.getByLabel("交易方向")).not.toBeVisible();
  await dealFilters.getByText("参与方与关联条件", { exact: true }).click();
  await expect(dealFilters.getByLabel("交易方向")).toBeVisible();
  await dealFilters.getByLabel("交易方向").selectOption("outbound");
  await dealFilters.getByLabel("参与机构").fill(companyName);
  await page
    .getByRole("option")
    .filter({ has: page.getByText(companyName, { exact: true }) })
    .click();
  await dealFilters.getByLabel("参与角色").selectOption("licensor");
  await dealFilters.getByText("更多交易条件").click();
  await dealFilters.getByLabel("方向参照地区").fill("US");
  await dealFilters.getByLabel("机构所在地区").fill("US");
  await dealFilters.getByLabel("机构类型").fill("biopharma");
  await dealFilters.getByLabel("交易时阶段").selectOption("phase_2");
  await dealFilters.getByLabel("当前最高阶段").selectOption("phase_3");
  await dealFilters.getByLabel("权益类型").selectOption("commercialization");
  await dealFilters.getByLabel("币种", { exact: true }).selectOption("USD");
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
  await expect(appliedDealFilters).toContainText("进行中");
  await expect(appliedDealFilters).toContainText("许可方");
  await expect(appliedDealFilters).toContainText("II期");
  await page.reload();
  await expect(dealFilters.getByLabel("交易状态")).toHaveValue("active");
  await expect(dealFilters.getByLabel("交易方向")).toHaveValue("outbound");
  await expect(dealFilters.getByLabel("参与机构")).toHaveValue(companyName);
  await expect(dealFilters.getByLabel("参与角色")).toHaveValue("licensor");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  return { dealFilters, announcedRange, terminatedRange, updatedRange, upfrontRange, totalRange, appliedDealFilters };
}
