import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { governanceFact, governanceIdentity, installGovernanceFixture } from "./governance-fixture";
import { selectInterfaceLanguage } from "./interface-language";

test("[governance-language] preserves record drafts and immutable pending intent across bilingual switching", async ({
  page,
  context,
}, testInfo) => {
  const state = await installGovernanceFixture(page);
  await page.goto("/workspace/internal?view=governance");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const originalNotes = page.getByRole("textbox", { name: "Review notes", exact: true });
  await originalNotes.fill("原始 A draft");
  await page
    .locator(".review-list")
    .getByRole("button", { name: /原始药物 B/ })
    .click();
  await page.getByRole("textbox", { name: "Review notes", exact: true }).fill("原始 B draft");
  await page
    .locator(".review-list")
    .getByRole("button", { name: /原始药物 A/ })
    .click();
  await expect(originalNotes).toHaveValue("原始 A draft");
  const technical = page.getByText("Technical details and complete original records", { exact: true });
  await technical.click();
  const beforeLocale = { ...state.reads };
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("textbox", { name: "审核意见", exact: true })).toHaveValue("原始 A draft");
  await expect(page.getByText("技术详情与完整原始记录").locator("..")).toHaveAttribute("open", "");
  expect(state.reads).toEqual(beforeLocale);
  state.holdDecision = true;
  await page.getByRole("button", { name: "批准并发布", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "审核意见", exact: true })).toBeDisabled();
  await expect(page.getByRole("tab", { name: /^实体消歧/ })).toBeDisabled();
  await expect(page.locator(".review-list").getByRole("button", { name: /原始药物 B/ })).toBeDisabled();
  const second = await context.newPage();
  await installGovernanceFixture(second, state);
  await second.goto("/workspace/internal?view=governance");
  await selectInterfaceLanguage(second, "en");
  await expect(originalNotes).toHaveValue("原始 A draft");
  await expect(originalNotes).toBeDisabled();
  await expect(page.getByRole("button", { name: "Approve and publish", exact: true })).toBeDisabled();
  expect(
    (
      await new AxeBuilder({ page })
        .include("#governance-active-panel")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("governance-pending-en.png"), animations: "disabled" });
  expect(state.writes).toEqual([`POST /api/v1/governance/staged-facts/${governanceFact.id}/decision`]);
  state.release?.();
  await expect(page.getByRole("textbox", { name: "Review notes", exact: true })).toHaveValue("原始 B draft");
  await expect(page.getByRole("textbox", { name: "Review notes", exact: true })).toBeEnabled();
  await second.close();
  expect(state.errors).toEqual([]);
});

test("[governance-language] retains an explicit identity choice on refresh and hides a denied cached queue", async ({
  page,
}, testInfo) => {
  const state = await installGovernanceFixture(page);
  await page.goto("/workspace/internal?view=governance");
  await page.getByRole("tab", { name: /^Entity resolution/ }).click();
  const choice = page.getByRole("combobox", { name: "Canonical identity to retain", exact: true });
  await expect(choice).toHaveValue(governanceIdentity.candidate_entity_id);
  await choice.selectOption(governanceIdentity.source_entity_id);
  await page.getByRole("textbox", { name: "Review notes", exact: true }).fill("原始 identity basis");
  await selectInterfaceLanguage(page, "zh-CN");
  await expect(page.getByRole("combobox", { name: "规范实体保留", exact: true })).toHaveValue(
    governanceIdentity.source_entity_id,
  );
  const previousImpactReads = state.impactReads;
  await page.getByRole("button", { name: "刷新影响分析", exact: true }).click();
  await expect.poll(() => state.impactReads).toBe(previousImpactReads + 1);
  await expect(page.getByRole("combobox", { name: "规范实体保留", exact: true })).toBeEnabled();
  await expect(page.getByRole("combobox", { name: "规范实体保留", exact: true })).toHaveValue(
    governanceIdentity.source_entity_id,
  );
  await page.getByRole("tab", { name: /^事实审核/ }).click();
  await page.getByRole("tab", { name: /^实体消歧/ }).click();
  await expect(page.getByRole("textbox", { name: "审核意见", exact: true })).toHaveValue("原始 identity basis");
  expect(
    (
      await new AxeBuilder({ page })
        .include("#governance-active-panel")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("governance-identity-zh.png"), animations: "disabled" });
  await page.getByRole("tab", { name: /^事实审核/ }).click();
  state.queueDenied = true;
  await page.getByRole("button", { name: "刷新审核队列", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("RAW_QUEUE_DENIAL");
  await expect(page.getByText(governanceFact.source_quote, { exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "批准并发布", exact: true })).toHaveCount(0);
  expect(state.writes).toEqual([]);
  expect(state.errors).toEqual([]);
});
