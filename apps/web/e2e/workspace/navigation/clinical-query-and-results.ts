import { expect } from "@playwright/test";
import { expandProfessionalQuery, verifyProfessionalRefreshLifecycle } from "../helpers";
import type { verifyExportsAndComparison } from "./exports-and-comparison";

export async function verifyClinicalQueryAndResults(context: Awaited<ReturnType<typeof verifyExportsAndComparison>>) {
  const { page, fixtureKeyBase, trialProfileId, fixtureKey } = context;
  const professionalQuery = page.getByRole("region", { name: "专业条件查询" });
  await expandProfessionalQuery(page);
  await expect(professionalQuery).toContainText("已选 1 项");
  const modalityFacet = professionalQuery.getByRole("group", { name: "药物模态" });
  await modalityFacet.getByLabel("药物模态：全部").click();
  await modalityFacet.getByRole("checkbox", { name: /antibody/ }).check();
  await modalityFacet.getByRole("checkbox", { name: /small molecule/ }).check();
  const innovationTypeFacet = professionalQuery.getByRole("group", { name: "创新类型" });
  await innovationTypeFacet.getByLabel("创新类型：全部").click();
  await innovationTypeFacet.getByRole("checkbox", { name: /First-in-class/ }).check();
  const therapeuticAreaFacet = professionalQuery.getByRole("group", { name: "治疗领域" });
  await therapeuticAreaFacet.getByLabel("治疗领域：全部").click();
  await therapeuticAreaFacet.getByRole("checkbox", { name: /Oncology/ }).check();
  const drugCategoryFacet = professionalQuery.getByRole("group", { name: "药品类别" });
  await drugCategoryFacet.getByLabel("药品类别：全部").click();
  await drugCategoryFacet.getByRole("checkbox", { name: /Small molecule/ }).check();
  await professionalQuery.getByLabel("项目状态").selectOption("active");
  await professionalQuery.getByLabel("记录地区").selectOption("US");
  await professionalQuery.getByText("更多管线条件", { exact: true }).click();
  await professionalQuery.getByLabel("全球最高阶段").selectOption("phase_2");
  await professionalQuery.getByLabel("中国最高阶段").selectOption("phase_1");
  await professionalQuery.getByLabel("研发权益地区").selectOption("Global");
  await professionalQuery.getByLabel("商业化权益地区").selectOption("Greater China");
  await professionalQuery.getByLabel("机构角色").selectOption("originator");
  await professionalQuery.getByLabel("机构类型").selectOption("biopharma");
  await professionalQuery.getByLabel("机构所在地区").selectOption("CN");
  const programTagFacet = professionalQuery.getByRole("group", { name: "项目标签" });
  await programTagFacet.getByLabel("项目标签：全部").click();
  await programTagFacet.getByRole("checkbox", { name: /first_in_class/ }).check();
  await programTagFacet.getByRole("checkbox", { name: /best_in_class/ }).check();
  await professionalQuery.getByLabel("里程碑类型").selectOption("first_patient_in");
  await professionalQuery.getByLabel("全球阶段开始日期时间范围").selectOption("custom");
  const globalPhaseRange = professionalQuery.getByRole("group", { name: "全球阶段开始日期" });
  await globalPhaseRange.getByLabel("起").fill("2026-01-01");
  await globalPhaseRange.getByLabel("止").fill("2026-06-30");
  await professionalQuery.getByLabel("里程碑日期时间范围").selectOption("custom");
  const professionalMilestoneRange = professionalQuery.getByRole("group", { name: "里程碑日期" });
  await professionalMilestoneRange.getByLabel("起").fill("2026-05-01");
  await professionalMilestoneRange.getByLabel("止").fill("2026-06-30");
  await professionalQuery.getByText("临床结果与交易信号", { exact: true }).click();
  await professionalQuery.getByLabel("是否已有临床结果").selectOption("true");
  await professionalQuery.getByLabel("临床结果评价").selectOption("positive");
  await professionalQuery.getByLabel("是否存在交易记录").selectOption("true");
  await professionalQuery.getByLabel("交易币种").selectOption("USD");
  await professionalQuery.getByLabel("潜在总额下限").fill("100000000");
  await professionalQuery.getByLabel("潜在总额上限").fill("500000000");
  const advancedPipelineResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/pipelines" &&
      url.searchParams.get("geography") === "US" &&
      url.searchParams.get("global_phase") === "phase_2" &&
      url.searchParams.get("china_phase") === "phase_1" &&
      url.searchParams.get("development_rights_region") === "Global" &&
      url.searchParams.get("commercialization_rights_region") === "Greater China" &&
      url.searchParams.getAll("modality").includes("antibody") &&
      url.searchParams.getAll("modality").includes("small molecule") &&
      url.searchParams.getAll("innovation_type").includes("First-in-class") &&
      url.searchParams.getAll("therapeutic_area").includes("Oncology") &&
      url.searchParams.getAll("drug_category").includes("Small molecule") &&
      url.searchParams.get("program_status") === "active" &&
      url.searchParams.get("organization_role") === "originator" &&
      url.searchParams.get("organization_type") === "biopharma" &&
      url.searchParams.get("organization_country_region") === "CN" &&
      url.searchParams.get("has_clinical_results") === "true" &&
      url.searchParams.get("clinical_result_evaluation") === "positive" &&
      url.searchParams.get("has_deal") === "true" &&
      url.searchParams.get("deal_currency") === "USD" &&
      url.searchParams.get("deal_total_potential_amount_min") === "100000000" &&
      url.searchParams.get("deal_total_potential_amount_max") === "500000000" &&
      url.searchParams.getAll("program_tag").includes("first_in_class") &&
      url.searchParams.getAll("program_tag").includes("best_in_class") &&
      url.searchParams.get("milestone_type") === "first_patient_in"
    );
  });
  await professionalQuery.getByRole("button", { name: "查询 药物与管线" }).click();
  expect((await advancedPipelineResponse).ok()).toBe(true);
  await expect(page).toHaveURL(/global_phase=phase_2/);
  await expect(page).toHaveURL(/china_phase=phase_1/);
  await expect(page).toHaveURL(/geography=US/);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("modality")).toEqual(["antibody", "small molecule"]);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("innovation_type")).toEqual(["First-in-class"]);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("therapeutic_area")).toEqual(["Oncology"]);
  await expect.poll(() => new URL(page.url()).searchParams.getAll("drug_category")).toEqual(["Small molecule"]);
  await expect(page).toHaveURL(/program_status=active/);
  await expect(page).toHaveURL(/organization_role=originator/);
  await expect(page).toHaveURL(/organization_type=biopharma/);
  await expect(page).toHaveURL(/organization_country_region=CN/);
  await expect(page).toHaveURL(/has_clinical_results=true/);
  await expect(page).toHaveURL(/clinical_result_evaluation=positive/);
  await expect(page).toHaveURL(/has_deal=true/);
  await expect(page).toHaveURL(/deal_currency=USD/);
  await expect(page).toHaveURL(/deal_total_potential_amount_min=100000000/);
  await expect(page).toHaveURL(/deal_total_potential_amount_max=500000000/);
  await expect
    .poll(() => new URL(page.url()).searchParams.getAll("program_tag"))
    .toEqual(["first_in_class", "best_in_class"]);
  await expect(page).toHaveURL(/development_rights_region=Global/);
  await expect(page).toHaveURL(/commercialization_rights_region=Greater\+China/);
  await expect(page).toHaveURL(/global_phase_started_from=2026-01-01/);
  await expect(page).toHaveURL(/milestone_from=2026-05-01/);
  await page.goBack();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await expandProfessionalQuery(page);
  await professionalQuery.getByRole("button", { name: "临床试验", exact: true }).click();
  await professionalQuery.getByLabel("注册平台").selectOption("ClinicalTrials.gov");
  await professionalQuery.getByLabel("招募状态").selectOption("RECRUITING");
  await professionalQuery.getByLabel("临床分期").selectOption("PHASE2");
  await professionalQuery.getByLabel("结果发布", { exact: true }).selectOption("true");
  await professionalQuery.getByLabel("结果发布日期时间范围").selectOption("last_6_months");
  await professionalQuery.getByText("试验属性与结果评价", { exact: true }).click();
  await professionalQuery.getByLabel("试验简称").fill(`BRIDGE-${fixtureKeyBase}`);
  await professionalQuery.getByLabel("发起类型").selectOption("ist");
  await professionalQuery.getByLabel("治疗线次").selectOption("first_line");
  await professionalQuery.getByLabel("结果最优评价").selectOption("positive");
  await professionalQuery.getByText("关键结果与发表证据", { exact: true }).click();
  await professionalQuery.getByLabel("关键结果").selectOption("true");
  await professionalQuery.getByLabel("发表编号").fill("PMID:12345678");
  await professionalQuery.getByLabel("会议").fill("ASCO 2026");
  await professionalQuery.getByLabel("结果披露日期时间范围").selectOption("last_month");
  const trialPresetText = await professionalQuery
    .getByRole("group", { name: "结果发布日期" })
    .locator("output")
    .textContent();
  const trialPresetMatch = trialPresetText?.match(/(\d{4}-\d{2}-\d{2})\s+至\s+(\d{4}-\d{2}-\d{2})/);
  expect(trialPresetMatch).not.toBeNull();
  if (!trialPresetMatch) throw new Error("The visible trial date preset did not expose an explicit range");
  const trialPresetRange = { from: trialPresetMatch[1], to: trialPresetMatch[2] };
  const trialDisclosureText = await professionalQuery
    .getByRole("group", { name: "结果披露日期" })
    .locator("output")
    .textContent();
  const trialDisclosureMatch = trialDisclosureText?.match(/(\d{4}-\d{2}-\d{2})\s+至\s+(\d{4}-\d{2}-\d{2})/);
  expect(trialDisclosureMatch).not.toBeNull();
  if (!trialDisclosureMatch) throw new Error("The visible disclosure date preset did not expose an explicit range");
  const trialDisclosureRange = { from: trialDisclosureMatch[1], to: trialDisclosureMatch[2] };
  const presetTrialResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      url.searchParams.get("acronym") === `BRIDGE-${fixtureKeyBase}` &&
      url.searchParams.get("initiation_type") === "ist" &&
      url.searchParams.get("therapy_line") === "first_line" &&
      url.searchParams.get("result_evaluation") === "positive" &&
      url.searchParams.get("has_key_result") === "true" &&
      url.searchParams.get("publication_id") === "PMID:12345678" &&
      url.searchParams.get("conference") === "ASCO 2026" &&
      url.searchParams.get("disclosed_from") === `${trialDisclosureRange.from}T00:00:00.000Z` &&
      url.searchParams.get("disclosed_to") === `${trialDisclosureRange.to}T23:59:59.999Z` &&
      url.searchParams.get("results_posted_from") === `${trialPresetRange.from}T00:00:00.000Z` &&
      url.searchParams.get("results_posted_to") === `${trialPresetRange.to}T23:59:59.999Z`
    );
  });
  await professionalQuery.getByRole("button", { name: "查询 临床试验" }).click();
  expect((await presetTrialResponse).ok()).toBe(true);
  await expect(page).toHaveURL(new RegExp(`view=trials&q=${encodeURIComponent(fixtureKey)}`));
  await expect(page).toHaveURL(/registry=ClinicalTrials.gov/);
  await expect(page).toHaveURL(/status=RECRUITING/);
  await expect(page).toHaveURL(/phase=PHASE2/);
  await expect(page).toHaveURL(/has_results=true/);
  await expect(page).toHaveURL(new RegExp(`acronym=BRIDGE-${fixtureKeyBase}`));
  await expect(page).toHaveURL(/initiation_type=ist/);
  await expect(page).toHaveURL(/therapy_line=first_line/);
  await expect(page).toHaveURL(/result_evaluation=positive/);
  await expect(page).toHaveURL(/has_key_result=true/);
  await expect(page).toHaveURL(/publication_id=PMID%3A12345678/);
  await expect(page).toHaveURL(/conference=ASCO\+2026/);
  await expect(page).toHaveURL(new RegExp(`disclosed_from=${trialDisclosureRange.from}`));
  await expect(page).toHaveURL(new RegExp(`disclosed_to=${trialDisclosureRange.to}`));
  await expect(page).toHaveURL(new RegExp(`results_posted_from=${trialPresetRange.from}`));
  await expect(page).toHaveURL(new RegExp(`results_posted_to=${trialPresetRange.to}`));
  const trialFilters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(trialFilters.getByLabel("关键词")).toHaveValue(fixtureKey);
  await expect(trialFilters.getByLabel("注册平台")).toHaveValue("ClinicalTrials.gov");
  await expect(trialFilters.getByLabel("招募状态")).toHaveValue("RECRUITING");
  await expect(trialFilters.getByLabel("临床分期")).toHaveValue("PHASE2");
  await expect(trialFilters.getByLabel("结果发布", { exact: true })).toHaveValue("true");
  await expect(trialFilters.getByLabel("关键结果")).toHaveValue("true");
  await expect(trialFilters.getByLabel("发表编号")).toHaveValue("PMID:12345678");
  await expect(trialFilters.getByLabel("会议")).toHaveValue("ASCO 2026");
  await expect(trialFilters.getByLabel("披露日期起")).toHaveValue(trialDisclosureRange.from);
  await expect(trialFilters.getByLabel("披露日期止")).toHaveValue(trialDisclosureRange.to);
  const trialKeyword = fixtureKeyBase;
  await trialFilters.getByLabel("关键词").fill(trialKeyword);
  // The relative-date contract above is independent of this fixed-date fixture.
  // Clear both ranges before checking the fixture's clinical result fields.
  for (const label of ["结果发布日期起", "结果发布日期止", "披露日期起", "披露日期止"]) {
    await trialFilters.getByLabel(label).fill("");
  }
  await trialFilters.getByRole("button", { name: "查询" }).click();
  await expect(page).toHaveURL(new RegExp(`view=trials&q=${encodeURIComponent(trialKeyword)}`));
  const trialTitle = `Browser clinical trial ${trialKeyword}`;
  const trialRegistryId = `NCT-E2E-${trialKeyword}`;
  const trialResults = page.getByRole("table", { name: "临床试验结果" });
  await expect(trialResults).toContainText(trialTitle);
  await expect(trialResults).toContainText(`BRIDGE-${trialKeyword}`);
  await expect(trialResults).toContainText("IST（申办方发起）");
  await expect(trialResults).toContainText("一线治疗");
  await expect(trialResults).toContainText("Objective response rate: 42 %");
  await verifyProfessionalRefreshLifecycle({
    page,
    endpoint: "/api/v1/trials",
    resultSurface: trialResults,
  });
  await trialResults.getByRole("button", { name: `${trialRegistryId} ${trialTitle}`, exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`trial=${trialProfileId}`));
  await expect(page.getByRole("heading", { name: trialTitle })).toBeVisible();
  await expect(page.getByText("临床试验专业档案", { exact: false })).toBeVisible();
  await expect(page.getByText("128", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(`BRIDGE-${trialKeyword}`, { exact: true }).first()).toBeVisible();

  await page.getByRole("tab", { name: "设计与入组" }).click();
  await expect(page).toHaveURL(new RegExp(`trial=${trialProfileId}.*section=design`));
  await expect(page.getByText("Controlled single-arm phase 2 cohort")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("tab", { name: "设计与入组" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText("Adults with confirmed browser disease")).toBeVisible();

  await page.getByRole("tab", { name: "终点与结果" }).click();
  await expect(page).toHaveURL(new RegExp(`trial=${trialProfileId}.*section=outcomes`));
  await expect(page.getByText("Objective response rate")).toBeVisible();
  await expect(page.getByText(/p=0\.01/)).toBeVisible();
  const trialOutcomesVisual = page.locator(".trial-professional-body");
  await expect(trialOutcomesVisual).toHaveCount(1);
  await expect.soft(trialOutcomesVisual).toHaveScreenshot("research-trial-outcomes.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixelRatio: 0.001,
  });
  await page.getByRole("tab", { name: "时间线与中心" }).click();
  await expect(page.getByText("Shanghai Oncology Center")).toBeVisible();
  await expect(page.getByText("First site opened")).toBeVisible();

  await page.getByRole("button", { name: "返回试验列表" }).click();
  await expect(page).not.toHaveURL(/trial=/);
  await expect(trialFilters.getByLabel("关键词")).toHaveValue(trialKeyword);
  await expect(trialFilters.getByLabel("注册平台")).toHaveValue("ClinicalTrials.gov");
  await expect(trialFilters.getByLabel("临床分期")).toHaveValue("PHASE2");
  const trialDisplay = page.getByRole("group", { name: "临床结果展示方式" });
  await trialDisplay.getByRole("button", { name: "可视化" }).click();
  await expect(page).toHaveURL(/display=landscape/);
  const trialLandscape = page.getByLabel("临床结果可视化");
  await expect(trialLandscape).toContainText("完整命中集");
  await expect(trialLandscape.getByRole("img", { name: "试验数量完整命中集分布" })).toBeVisible();
  const trialCountSection = trialLandscape.getByRole("heading", { name: "试验数量" }).locator("..").locator("..");
  await trialCountSection.getByRole("button", { name: "列表" }).click();
  await expect(trialLandscape.getByRole("table", { name: "试验数量统计表" })).toBeVisible();
  await expect(trialLandscape.getByRole("heading", { name: "总体评价" })).toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/display=landscape/);
  await expect(page.getByLabel("临床结果可视化")).toBeVisible();
  await trialDisplay.getByRole("button", { name: "列表" }).click();
  await expect(page).not.toHaveURL(/display=landscape/);
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(trialTitle);
  for (const label of ["试验设计与注册信息", "试验结果、日期与发表"]) {
    const disclosure = trialFilters.locator("details").filter({ has: page.getByText(label, { exact: true }) });
    if ((await disclosure.getAttribute("open")) === null) await disclosure.locator(":scope > summary").click();
    await expect(disclosure).toHaveAttribute("open", "");
  }
  await trialFilters.getByLabel("结果最优评价").selectOption("positive");
  await trialFilters.getByLabel("试验简称").fill(`BRIDGE-${trialKeyword}`);
  await trialFilters.getByLabel("发起类型").selectOption("ist");
  await trialFilters.getByLabel("治疗线次").selectOption("first_line");
  await trialFilters.getByLabel("结果发布日期起").fill("2026-01-01");
  await trialFilters.getByLabel("结果发布日期止").fill("2026-07-31");
  await trialFilters.getByLabel("关键结果").selectOption("true");
  await trialFilters.getByLabel("发表编号").fill("PMID:12345678");
  await trialFilters.getByLabel("会议").fill("ASCO 2026");
  await trialFilters.getByLabel("披露日期起").fill("2026-06-01");
  await trialFilters.getByLabel("披露日期止").fill("2026-07-31");
  await trialFilters.getByRole("button", { name: "查询", exact: true }).click();
  await expect(page).toHaveURL(/results_posted_from=2026-01-01/);
  await expect(page).toHaveURL(/results_posted_to=2026-07-31/);
  await expect(page).toHaveURL(/result_evaluation=positive/);
  await expect(page).toHaveURL(new RegExp(`acronym=BRIDGE-${trialKeyword}`));
  await expect(page).toHaveURL(/initiation_type=ist/);
  await expect(page).toHaveURL(/therapy_line=first_line/);
  await expect(page).toHaveURL(/has_key_result=true/);
  await expect(page).toHaveURL(/publication_id=PMID%3A12345678/);
  await expect(page).toHaveURL(/conference=ASCO/);
  await expect(page).toHaveURL(/disclosed_from=2026-06-01/);
  await expect(page).toHaveURL(/disclosed_to=2026-07-31/);
  const appliedTrialFilters = page.getByRole("region", { name: "已应用查询条件" });
  await expect(appliedTrialFilters).toContainText("2026-01-01");
  await expect(appliedTrialFilters).toContainText("2026-07-31");
  await expect(appliedTrialFilters).toContainText("积极");
  await expect(appliedTrialFilters).toContainText(`BRIDGE-${trialKeyword}`);
  await expect(appliedTrialFilters).toContainText("IST（申办方发起）");
  await expect(appliedTrialFilters).toContainText("一线治疗");
  await expect(appliedTrialFilters).toContainText("PMID:12345678");
  await page.reload();
  await expect(trialFilters.getByLabel("结果发布日期起")).toHaveValue("2026-01-01");
  await expect(trialFilters.getByLabel("结果发布日期止")).toHaveValue("2026-07-31");
  await expect(trialFilters.getByLabel("结果最优评价")).toHaveValue("positive");
  await expect(trialFilters.getByLabel("试验简称")).toHaveValue(`BRIDGE-${trialKeyword}`);
  await expect(trialFilters.getByLabel("发起类型")).toHaveValue("ist");
  await expect(trialFilters.getByLabel("治疗线次")).toHaveValue("first_line");
  await expect(trialFilters.getByLabel("关键结果")).toHaveValue("true");
  await expect(trialFilters.getByLabel("发表编号")).toHaveValue("PMID:12345678");
  await expect(trialFilters.getByLabel("会议")).toHaveValue("ASCO 2026");
  await expect(trialFilters.getByLabel("披露日期起")).toHaveValue("2026-06-01");
  await expect(trialFilters.getByLabel("披露日期止")).toHaveValue("2026-07-31");
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(
    false,
  );
  return {
    ...context,
    professionalQuery,
    modalityFacet,
    innovationTypeFacet,
    therapeuticAreaFacet,
    drugCategoryFacet,
    programTagFacet,
    globalPhaseRange,
    professionalMilestoneRange,
    advancedPipelineResponse,
    trialPresetText,
    trialPresetMatch,
    trialPresetRange,
    trialDisclosureText,
    trialDisclosureMatch,
    trialDisclosureRange,
    presetTrialResponse,
    trialFilters,
    trialKeyword,
    trialTitle,
    trialRegistryId,
    trialResults,
    trialOutcomesVisual,
    trialDisplay,
    trialLandscape,
    trialCountSection,
    appliedTrialFilters,
  };
}
