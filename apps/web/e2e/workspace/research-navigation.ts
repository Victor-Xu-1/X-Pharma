import { expect, type Page } from "@playwright/test";
import { researchWorkflows } from "../../src/lib/workspace/researchNavigation";
import { navigateResearchView, openNavigation } from "./helpers";

export async function verifyResearchNavigationHierarchy(page: Page) {
  const primary = page.getByRole("navigation", { name: "主导航", exact: true });
  await expect(primary.getByRole("button")).toHaveCount(5);
  await expect(primary.getByRole("button")).toHaveText(["情报检索", "研发数据", "竞争情报", "研究动态", "我的研究"]);
  for (const workflow of researchWorkflows) {
    for (const destination of workflow.destinations) {
      await navigateResearchView(page, destination.view);
      await expect(primary.getByRole("button", { name: workflow.label, exact: true })).toHaveAttribute(
        "aria-current",
        "page",
      );
      await expect(primary.locator("[aria-current=page]")).toHaveCount(1);
      await expect(page.locator("main .spinner")).toHaveCount(0);
      await expect(page.locator(".page-heading h1")).toBeVisible();
      if (workflow.destinations.length > 1) {
        const categories = page.getByRole("navigation", { name: `${workflow.label}分类`, exact: true });
        await expect(categories.getByRole("button")).toHaveCount(workflow.destinations.length);
        await expect(categories.getByRole("button", { name: destination.label, exact: true })).toHaveAttribute(
          "aria-current",
          "page",
        );
      } else await expect(page.locator(".research-view-navigation")).toHaveCount(0);
      await expect(page.locator(".workspace-sidebar")).not.toHaveClass(/mobile-open/);
      const dimensions = await page.evaluate(() => ({
        width: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.width);
    }
  }
  await navigateResearchView(page, "trials");
  await page.reload();
  await expect(page.getByRole("heading", { name: "临床试验与结果", exact: true })).toBeVisible();
  await expect(primary.getByRole("button", { name: "研发数据", exact: true })).toHaveAttribute("aria-current", "page");
  await page
    .getByRole("navigation", { name: "研发数据分类" })
    .getByRole("button", { name: "流行病学", exact: true })
    .click();
  await expect.poll(() => new URL(page.url()).searchParams.get("view")).toBe("epidemiology");
  await page.goBack();
  await expect(page.getByRole("heading", { name: "临床试验与结果", exact: true })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("heading", { name: "流行病学与疾病负担", exact: true })).toBeVisible();
  await navigateResearchView(page, "explorer");
  await page.getByLabel("情报检索词").fill("navigation-state-check");
  await page
    .getByRole("navigation", { name: "情报检索分类" })
    .getByRole("button", { name: "实体检索", exact: true })
    .click();
  await expect(page.getByLabel("情报检索词")).toHaveValue("navigation-state-check");
  await openNavigation(page);
  await primary.getByRole("button", { name: "研发数据", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "药物与研发管线", exact: true })).toBeFocused();
  await openNavigation(page);
  await page
    .getByRole("navigation", { name: "账户导航" })
    .getByRole("button", { name: "用户中心", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "用户中心", exact: true })).toBeVisible();
  await expect(page.locator(".research-view-navigation")).toHaveCount(0);
  await expect(primary.locator("[aria-current=page]")).toHaveCount(0);
}
