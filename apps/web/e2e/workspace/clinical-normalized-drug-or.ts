import type { PlaywrightTestArgs, PlaywrightWorkerArgs, TestInfo } from "@playwright/test";
import { expect, test } from "@playwright/test";
import { resolveBrowserCredentials } from "../../src/lib/browserAcceptanceCredentials";

export async function verifyClinicalNormalizedDrugOr(
  { page }: Pick<PlaywrightTestArgs & PlaywrightWorkerArgs, "page">,
  testInfo: TestInfo,
) {
  testInfo.setTimeout(60_000);
  const credentials = resolveBrowserCredentials(testInfo.project.name, process.env);
  const fixtureKeyBase = process.env.E2E_FIXTURE_KEY;
  const regulatorySubjectId = process.env.E2E_REGULATORY_SUBJECT_ID;
  const pipelineDrugBId = process.env.E2E_PIPELINE_DRUG_B_ID;
  const pipelineTargetId = process.env.E2E_PIPELINE_TARGET_ID;
  const pipelineCombinationTargetId = process.env.E2E_PIPELINE_COMBINATION_TARGET_ID;
  const trialProfileId = process.env.E2E_TRIAL_PROFILE_ID;
  const trialNegativeProfileId = process.env.E2E_TRIAL_NEGATIVE_PROFILE_ID;
  test.skip(
    !credentials ||
      !fixtureKeyBase ||
      !regulatorySubjectId ||
      !pipelineDrugBId ||
      !pipelineTargetId ||
      !pipelineCombinationTargetId ||
      !trialProfileId ||
      !trialNegativeProfileId,
    "Authenticated browser fixture credentials and normalized clinical role IDs are required",
  );
  if (
    !credentials ||
    !fixtureKeyBase ||
    !regulatorySubjectId ||
    !pipelineDrugBId ||
    !pipelineTargetId ||
    !pipelineCombinationTargetId ||
    !trialProfileId ||
    !trialNegativeProfileId
  )
    return;

  await page.goto("/");
  await page.getByLabel("工作邮箱").fill(credentials.email);
  await page.getByLabel("密码").fill(credentials.password);
  await page.getByRole("button", { name: "进入工作台" }).click();
  await expect(page.getByRole("heading", { name: "全局情报检索" })).toBeVisible();
  await page.goto(
    `/workspace/research?view=trials&investigational_drug_entity_ids=${regulatorySubjectId}` +
      `&combination_drug_entity_ids=${pipelineDrugBId}` +
      `&investigational_target_entity_ids=${pipelineTargetId}` +
      `&combination_target_entity_ids=${pipelineCombinationTargetId}`,
  );
  const clinicalFilters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(clinicalFilters).toContainText(`Browser regulatory drug ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser combination target ${fixtureKeyBase}`);
  const roleComboboxes = clinicalFilters.locator('input[role="combobox"][aria-controls*="-multi-filter-options-"]');
  const roleListboxes = await roleComboboxes.evaluateAll((inputs) =>
    inputs.map((input) => input.getAttribute("aria-controls")),
  );
  expect(roleListboxes.every(Boolean)).toBe(true);
  expect(new Set(roleListboxes).size).toBe(roleListboxes.length);
  const investigationalDrugCombobox = clinicalFilters.getByLabel("试验药物（任一）筛选");
  await investigationalDrugCombobox.fill(`Browser antibody alias ${fixtureKeyBase}`);
  const disambiguatedCandidate = clinicalFilters.getByRole("option", {
    name: new RegExp(`Browser pipeline antibody ${fixtureKeyBase}`),
  });
  await expect(disambiguatedCandidate).toContainText("别名精确匹配");
  await expect(disambiguatedCandidate).toContainText(`Browser antibody alias ${fixtureKeyBase}`);
  await expect(disambiguatedCandidate).toContainText(`英文名 Browser Antibody ${fixtureKeyBase}`);
  await expect(disambiguatedCandidate).toContainText("创新类型 First-in-class");
  await expect(disambiguatedCandidate).toContainText("药物类型 单克隆抗体");
  await investigationalDrugCombobox.press("ArrowDown");
  await expect(investigationalDrugCombobox).toBeFocused();
  await expect(disambiguatedCandidate).toHaveAttribute("aria-selected", "true");
  const disambiguatedCandidateId = await disambiguatedCandidate.getAttribute("id");
  expect(disambiguatedCandidateId).toBeTruthy();
  await expect(investigationalDrugCombobox).toHaveAttribute("aria-activedescendant", disambiguatedCandidateId ?? "");
  await investigationalDrugCombobox.press("Enter");
  await expect(clinicalFilters).toContainText(`Browser pipeline antibody ${fixtureKeyBase}`);
  const normalizedRoleGroupResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    const investigationalDrugIds = url.searchParams.getAll("investigational_drug_entity_ids");
    return (
      url.pathname === "/api/v1/trials" &&
      investigationalDrugIds.length === 2 &&
      investigationalDrugIds.includes(regulatorySubjectId) &&
      investigationalDrugIds.includes(pipelineDrugBId) &&
      url.searchParams.get("combination_drug_entity_ids") === pipelineDrugBId &&
      url.searchParams.get("investigational_target_entity_ids") === pipelineTargetId &&
      url.searchParams.get("combination_target_entity_ids") === pipelineCombinationTargetId
    );
  });
  await clinicalFilters.getByRole("button", { name: "查询", exact: true }).click();
  const roleGroupResponse = await normalizedRoleGroupResponse;
  const roleGroupPayload = (await roleGroupResponse.json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(roleGroupPayload.total).toBe(1);
  expect(roleGroupPayload.items.map((item) => item.id)).toEqual([trialProfileId]);
  expect(roleGroupPayload.items.some((item) => item.id === trialNegativeProfileId)).toBe(false);
  await expect(page).toHaveURL(/investigational_drug_entity_ids=.*investigational_drug_entity_ids=/);
  await expect(page).toHaveURL(/combination_drug_entity_ids=/);
  await expect(page).toHaveURL(/investigational_target_entity_ids=/);
  await expect(page).toHaveURL(/combination_target_entity_ids=/);
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await page.reload();
  await expect(clinicalFilters).toContainText(`Browser regulatory drug ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser pipeline antibody ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser pipeline target ${fixtureKeyBase}`);
  await expect(clinicalFilters).toContainText(`Browser combination target ${fixtureKeyBase}`);

  const linkedProgramQuery = new URLSearchParams({ view: "trials" });
  linkedProgramQuery.append("investigational_drug_entity_ids", regulatorySubjectId);
  linkedProgramQuery.append("investigational_drug_entity_ids", pipelineDrugBId);
  linkedProgramQuery.set("combination_drug_entity_ids", pipelineDrugBId);
  linkedProgramQuery.set("investigational_target_entity_ids", pipelineTargetId);
  linkedProgramQuery.set("combination_target_entity_ids", pipelineCombinationTargetId);
  linkedProgramQuery.set("linked_drug_modality", "antibody");
  linkedProgramQuery.set("linked_drug_program_tag", "best_in_class");
  linkedProgramQuery.set("linked_drug_global_phase", "phase_3");
  linkedProgramQuery.set("linked_drug_organization_country_region", "US");
  const linkedPositiveResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      url.searchParams.get("linked_drug_modality") === "antibody" &&
      url.searchParams.get("linked_drug_program_tag") === "best_in_class" &&
      url.searchParams.get("linked_drug_global_phase") === "phase_3" &&
      url.searchParams.get("linked_drug_organization_country_region") === "US"
    );
  });
  await page.goto(`/workspace/research?${linkedProgramQuery.toString()}`);
  const linkedPositivePayload = (await (await linkedPositiveResponse).json()) as {
    total: number;
    items: Array<{ id: string }>;
    query_schema_version: string;
  };
  expect(linkedPositivePayload.query_schema_version).toBe("pharma.clinical_trial.search.v10");
  expect(linkedPositivePayload.total).toBe(1);
  expect(linkedPositivePayload.items.map((item) => item.id)).toEqual([trialProfileId]);
  const linkedProgramFilters = page.getByRole("form", { name: "临床试验筛选" });
  await expect(linkedProgramFilters.locator("details.trial-linked-program-filters")).toHaveAttribute("open", "");
  await expect(linkedProgramFilters.getByLabel("全球最高阶段")).toHaveValue("phase_3");
  await expect(linkedProgramFilters.getByLabel("研发机构国家/地区")).toHaveValue("US");
  await expect(page.getByRole("table", { name: "临床试验结果" })).toContainText(`NCT-E2E-${fixtureKeyBase}`);
  await page.reload();
  await expect(linkedProgramFilters.getByLabel("全球最高阶段")).toHaveValue("phase_3");
  await expect(linkedProgramFilters.getByLabel("研发机构国家/地区")).toHaveValue("US");

  linkedProgramQuery.set("linked_drug_program_tag", "first_in_class");
  linkedProgramQuery.delete("linked_drug_global_phase");
  linkedProgramQuery.delete("linked_drug_organization_country_region");
  const linkedNegativeResponse = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return (
      url.pathname === "/api/v1/trials" &&
      url.searchParams.get("linked_drug_modality") === "antibody" &&
      url.searchParams.get("linked_drug_program_tag") === "first_in_class"
    );
  });
  await page.goto(`/workspace/research?${linkedProgramQuery.toString()}`);
  const linkedNegativePayload = (await (await linkedNegativeResponse).json()) as {
    total: number;
    items: Array<{ id: string }>;
  };
  expect(linkedNegativePayload.total).toBe(0);
  expect(linkedNegativePayload.items).toEqual([]);
  await expect(page.getByText("未找到匹配记录", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "清除筛选条件", exact: true })).toBeVisible();
}
