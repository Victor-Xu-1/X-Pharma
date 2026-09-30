import { describe, expect, it } from "vitest";

import {
  countProfessionalConditions,
  createProfessionalSearchDraft,
  identifyProfessionalDatePreset,
  type ProfessionalSearchDraft,
  professionalSearchLocation,
  resolveProfessionalDatePreset,
  validateProfessionalSearch,
} from "../lib/professionalSearch";
import { parseWorkbenchLocation, workspaceUrl } from "../lib/workspaceRouting";

describe("professional composite query contract", () => {
  it("does not count empty array-backed filters as selected conditions", () => {
    expect(countProfessionalConditions(createProfessionalSearchDraft("pipeline"))).toBe(0);
    expect(countProfessionalConditions(createProfessionalSearchDraft("pipeline", "EGFR"))).toBe(1);
  });

  it.each([
    ["all", { from: "", to: "" }],
    ["last_month", { from: "2026-06-25", to: "2026-07-25" }],
    ["last_6_months", { from: "2026-01-25", to: "2026-07-25" }],
    ["last_year", { from: "2025-07-25", to: "2026-07-25" }],
  ] as const)("resolves the %s date preset into an explicit stable URL range", (preset, expected) => {
    expect(resolveProfessionalDatePreset(preset, "2026-07-25")).toEqual(expected);
    expect(identifyProfessionalDatePreset(expected.from, expected.to, "2026-07-25")).toBe(preset);
  });

  it("clamps calendar presets at month boundaries and treats manually edited ranges as custom", () => {
    expect(resolveProfessionalDatePreset("last_month", "2026-03-31")).toEqual({
      from: "2026-02-28",
      to: "2026-03-31",
    });
    expect(identifyProfessionalDatePreset("2026-02-27", "2026-03-31", "2026-03-31")).toBe("custom");
  });

  it.each([
    [
      "pipeline",
      {
        drugEntityId: "550e8400-e29b-41d4-a716-446655440000",
        targetEntityId: "550e8400-e29b-41d4-a716-446655440001",
        diseaseEntityId: "550e8400-e29b-41d4-a716-446655440002",
        modalities: ["antibody", "small molecule"] as string[],
        pipelineInnovationTypes: ["First-in-class", "Biosimilar"] as string[],
        pipelineTherapeuticAreas: ["Oncology", "Immunology"] as string[],
        pipelineDrugCategories: ["Small molecule", "Biologic"] as string[],
        pipelineProgramStatus: "active",
        pipelineOrganizationRole: "originator",
        pipelineOrganizationType: "biopharma",
        pipelineOrganizationCountryRegion: "CN",
        phase: "phase_2",
        geography: "Global",
        statusDateFrom: "2026-01-01",
        statusDateTo: "2026-06-30",
        pipelineGlobalPhase: "phase_2",
        pipelineChinaPhase: "phase_1",
        pipelineGlobalPhaseStartedFrom: "2025-01-01",
        pipelineGlobalPhaseStartedTo: "2026-06-30",
        pipelineChinaPhaseStartedFrom: "2025-06-01",
        pipelineChinaPhaseStartedTo: "2026-06-30",
        pipelineDevelopmentRightsRegion: "Global",
        pipelineCommercializationRightsRegion: "Greater China",
        pipelineProgramTags: ["first_in_class", "best_in_class"] as string[],
        pipelineMilestoneType: "first_patient_in",
        pipelineMilestoneFrom: "2026-05-01",
        pipelineMilestoneTo: "2026-06-30",
        pipelineHasClinicalResults: "true" as const,
        pipelineClinicalResultEvaluation: "positive",
        pipelineHasDeal: "true" as const,
        pipelineDealCurrency: "USD",
        pipelineDealTotalPotentialAmountMin: "100000000",
        pipelineDealTotalPotentialAmountMax: "500000000",
      },
      {
        pipelineDrugEntityId: "550e8400-e29b-41d4-a716-446655440000",
        pipelineTargetEntityId: "550e8400-e29b-41d4-a716-446655440001",
        pipelineDiseaseEntityId: "550e8400-e29b-41d4-a716-446655440002",
        pipelineModalities: ["antibody", "small molecule"],
        pipelineInnovationTypes: ["First-in-class", "Biosimilar"],
        pipelineTherapeuticAreas: ["Oncology", "Immunology"],
        pipelineDrugCategories: ["Small molecule", "Biologic"],
        pipelineProgramStatus: "active",
        pipelineOrganizationRole: "originator",
        pipelineOrganizationType: "biopharma",
        pipelineOrganizationCountryRegion: "CN",
        phase: "phase_2",
        geography: "Global",
        pipelineStatusDateFrom: "2026-01-01",
        pipelineStatusDateTo: "2026-06-30",
        pipelineGlobalPhase: "phase_2",
        pipelineChinaPhase: "phase_1",
        pipelineGlobalPhaseStartedFrom: "2025-01-01",
        pipelineGlobalPhaseStartedTo: "2026-06-30",
        pipelineChinaPhaseStartedFrom: "2025-06-01",
        pipelineChinaPhaseStartedTo: "2026-06-30",
        pipelineDevelopmentRightsRegion: "Global",
        pipelineCommercializationRightsRegion: "Greater China",
        pipelineProgramTags: ["first_in_class", "best_in_class"],
        pipelineMilestoneType: "first_patient_in",
        pipelineMilestoneFrom: "2026-05-01",
        pipelineMilestoneTo: "2026-06-30",
        pipelineHasClinicalResults: "true",
        pipelineClinicalResultEvaluation: "positive",
        pipelineHasDeal: "true",
        pipelineDealCurrency: "USD",
        pipelineDealTotalPotentialAmountMin: "100000000",
        pipelineDealTotalPotentialAmountMax: "500000000",
      },
    ],
    [
      "trials",
      {
        registry: "ClinicalTrials.gov",
        trialStatus: "RECRUITING",
        trialPhase: "PHASE2",
        studyType: "INTERVENTIONAL",
        trialHasResults: "true",
        trialAcronym: "BRIDGE-001",
        trialInitiationType: "ist",
        trialTherapyLine: "first_line",
        trialResultEvaluation: "positive",
        trialHasKeyResult: "true",
        trialPublicationId: " PMID:12345678 ",
        trialConference: " ASCO 2026 ",
        trialDisclosedFrom: "2026-06-01",
        trialDisclosedTo: "2026-07-31",
      },
      {
        registry: "ClinicalTrials.gov",
        trialStatus: "RECRUITING",
        trialPhase: "PHASE2",
        studyType: "INTERVENTIONAL",
        trialHasResults: "true",
        trialAcronym: "BRIDGE-001",
        trialInitiationType: "ist",
        trialTherapyLine: "first_line",
        trialResultEvaluation: "positive",
        trialHasKeyResult: "true",
        trialPublicationId: "PMID:12345678",
        trialConference: "ASCO 2026",
        trialDisclosedFrom: "2026-06-01",
        trialDisclosedTo: "2026-07-31",
      },
    ],
    [
      "patents",
      {
        patentEntityType: "drug" as const,
        patentEntityId: "550e8400-e29b-41d4-a716-446655440004",
        applicant: "Victor Therapeutics",
        legalStatus: "ACTIVE",
        patentPriorityFrom: "2020-01-01",
        patentPriorityTo: "2022-12-31",
        patentExpirationFrom: "2035-01-01",
        patentExpirationTo: "2040-12-31",
      },
      {
        patentEntityId: "550e8400-e29b-41d4-a716-446655440004",
        applicant: "Victor Therapeutics",
        legalStatus: "ACTIVE",
        patentPriorityFrom: "2020-01-01",
        patentPriorityTo: "2022-12-31",
        patentExpirationFrom: "2035-01-01",
        patentExpirationTo: "2040-12-31",
      },
    ],
    [
      "deals",
      {
        dealDirectionReferenceJurisdiction: "US",
        dealAssetEntityId: "550e8400-e29b-41d4-a716-446655440010",
        dealTargetEntityId: "550e8400-e29b-41d4-a716-446655440011",
        dealDiseaseEntityId: "550e8400-e29b-41d4-a716-446655440012",
        dealAssetModalities: ["antibody", "small molecule"] as string[],
        dealAssetProgramTags: ["first_in_class", "best_in_class"] as string[],
        dealPartyEntityId: "550e8400-e29b-41d4-a716-446655440003",
        dealType: "license",
        dealStatus: "active",
        dealDirection: "outbound",
        dealTerritory: "Greater China",
        dealPartyRole: "licensor",
        dealPartyCountryRegion: "US",
        dealPartyOrganizationType: "biopharma",
        dealDevelopmentPhaseAtTransaction: "phase_2",
        dealCurrentDevelopmentPhase: "phase_3",
        dealRightType: "commercialization",
        dealRightsTerritory: "Greater China",
        dealCurrency: "USD",
        dealAnnouncedFrom: "2026-01-01",
        dealAnnouncedTo: "2026-01-31",
        dealTerminatedFrom: "2026-02-01",
        dealTerminatedTo: "2026-02-28",
        dealSourceUpdatedFrom: "2026-03-01",
        dealSourceUpdatedTo: "2026-03-31",
        dealUpfrontAmountMin: "10000000",
        dealUpfrontAmountMax: "30000000",
        dealTotalPotentialAmountMin: "100000000",
        dealTotalPotentialAmountMax: "500000000",
      },
      {
        dealDirectionReferenceJurisdiction: "US",
        dealAssetEntityId: "550e8400-e29b-41d4-a716-446655440010",
        dealTargetEntityId: "550e8400-e29b-41d4-a716-446655440011",
        dealDiseaseEntityId: "550e8400-e29b-41d4-a716-446655440012",
        dealAssetModalities: ["antibody", "small molecule"],
        dealAssetProgramTags: ["first_in_class", "best_in_class"],
        dealPartyEntityId: "550e8400-e29b-41d4-a716-446655440003",
        dealType: "license",
        dealStatus: "active",
        dealDirection: "outbound",
        dealTerritory: "Greater China",
        dealPartyRole: "licensor",
        dealPartyCountryRegion: "US",
        dealPartyOrganizationType: "biopharma",
        dealDevelopmentPhaseAtTransaction: "phase_2",
        dealCurrentDevelopmentPhase: "phase_3",
        dealRightType: "commercialization",
        dealRightsTerritory: "Greater China",
        dealCurrency: "USD",
        dealAnnouncedFrom: "2026-01-01",
        dealAnnouncedTo: "2026-01-31",
        dealTerminatedFrom: "2026-02-01",
        dealTerminatedTo: "2026-02-28",
        dealSourceUpdatedFrom: "2026-03-01",
        dealSourceUpdatedTo: "2026-03-31",
        dealUpfrontAmountMin: "10000000",
        dealUpfrontAmountMax: "30000000",
        dealTotalPotentialAmountMin: "100000000",
        dealTotalPotentialAmountMax: "500000000",
      },
    ],
    [
      "regulatory",
      {
        regulatoryAgency: "FDA",
        regulatoryJurisdiction: "US",
        regulatoryEventType: "approval",
        regulatoryStatus: "approved",
        regulatoryDesignationType: "breakthrough_therapy",
        regulatoryLabelChangeType: "initial_label",
        regulatoryBoxedWarning: "true" as const,
        regulatorySafetySignalType: "adverse_event",
        regulatorySafetySeverity: "serious",
        regulatorySafetyStatus: "confirmed",
        regulatoryDecisionFrom: "2026-01-01",
        regulatoryDecisionTo: "2026-01-31",
        regulatorySourceUpdatedFrom: "2026-02-01",
        regulatorySourceUpdatedTo: "2026-02-28",
      },
      {
        regulatoryAgency: "FDA",
        regulatoryJurisdiction: "US",
        regulatoryEventType: "approval",
        regulatoryStatus: "approved",
        regulatoryDesignationType: "breakthrough_therapy",
        regulatoryLabelChangeType: "initial_label",
        regulatoryBoxedWarning: "true",
        regulatorySafetySignalType: "adverse_event",
        regulatorySafetySeverity: "serious",
        regulatorySafetyStatus: "confirmed",
        regulatoryDecisionFrom: "2026-01-01",
        regulatoryDecisionTo: "2026-01-31",
        regulatorySourceUpdatedFrom: "2026-02-01",
        regulatorySourceUpdatedTo: "2026-02-28",
      },
    ],
    [
      "epidemiology",
      {
        diseaseEntityId: "550e8400-e29b-41d4-a716-446655440001",
        epidemiologyMeasure: "prevalence",
        epidemiologyGeography: "China",
        epidemiologyUnit: "patients",
        epidemiologyPatientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
        epidemiologyPopulationScope: "adults",
        epidemiologyAgeGroup: "18+",
        epidemiologySex: "all",
      },
      {
        epidemiologyDiseaseEntityId: "550e8400-e29b-41d4-a716-446655440001",
        epidemiologyMeasure: "prevalence",
        epidemiologyGeography: "China",
        epidemiologyUnit: "patients",
        epidemiologyPatientPopulationId: "550e8400-e29b-41d4-a716-446655440003",
        epidemiologyPopulationScope: "adults",
        epidemiologyAgeGroup: "18+",
        epidemiologySex: "all",
      },
    ],
    [
      "news",
      {
        newsEntityId: "550e8400-e29b-41d4-a716-446655440002",
        newsEventType: "publication",
        newsPublisher: "ASCO",
        newsLanguage: "en",
        newsVenue: "ASCO 2026",
        newsContentScope: "research",
      },
      {
        newsEntityId: "550e8400-e29b-41d4-a716-446655440002",
        newsEventType: "publication",
        newsPublisher: "ASCO",
        newsLanguage: "en",
        newsVenue: "ASCO 2026",
        newsContentScope: "research",
        newsDisplayMode: "timeline",
      },
    ],
  ] as const)(
    "maps and round-trips the %s domain through authoritative workspace URL state",
    (domain, changes, expected) => {
      const draft = { ...createProfessionalSearchDraft(domain, "EGFR"), ...changes };
      const location = professionalSearchLocation(draft);
      expect(location).toMatchObject({ view: domain, query: "EGFR", ...expected });

      const parsed = parseWorkbenchLocation("research", workspaceUrl(location).split("?")[1]);
      expect(parsed).toMatchObject({ view: domain, query: "EGFR", ...expected });
    },
  );

  it("rejects inverted date ranges before the domain API can be queried", () => {
    const draft = {
      ...createProfessionalSearchDraft("regulatory", "EGFR"),
      regulatoryDecisionFrom: "2026-07-31",
      regulatoryDecisionTo: "2026-01-01",
    };
    expect(validateProfessionalSearch(draft)).toBe("监管决定日期起始值不能晚于结束值");
  });

  it("rejects an inverted regulatory source update range before navigation", () => {
    const draft = {
      ...createProfessionalSearchDraft("regulatory", "EGFR"),
      regulatorySourceUpdatedFrom: "2026-07-31",
      regulatorySourceUpdatedTo: "2026-01-01",
    };
    expect(validateProfessionalSearch(draft)).toBe("来源更新日期起始值不能晚于结束值");
  });

  it("rejects an inverted advanced pipeline range before navigation", () => {
    const draft = {
      ...createProfessionalSearchDraft("pipeline", "EGFR"),
      pipelineMilestoneFrom: "2026-12-31",
      pipelineMilestoneTo: "2026-01-01",
    };
    expect(validateProfessionalSearch(draft)).toBe("里程碑日期起始值不能晚于结束值");
  });

  it.each([
    ["patentPriorityFrom", "patentPriorityTo", "优先权日期"],
    ["patentExpirationFrom", "patentExpirationTo", "到期日期"],
  ] as const)("rejects an inverted patent %s range before navigation", (fromKey, toKey, label) => {
    const draft = {
      ...createProfessionalSearchDraft("patents", "EGFR"),
      [fromKey]: "2040-12-31",
      [toKey]: "2020-01-01",
    };
    expect(validateProfessionalSearch(draft)).toBe(`${label}起始值不能晚于结束值`);
  });

  const invalidPipelineSignalCases: Array<[Partial<ProfessionalSearchDraft>, string]> = [
    [
      { pipelineHasClinicalResults: "false", pipelineClinicalResultEvaluation: "positive" },
      "选择“无临床结果”时不能同时限定结果评价",
    ],
    [{ pipelineHasDeal: "false", pipelineDealCurrency: "USD" }, "选择“无交易记录”时不能同时限定交易金额或币种"],
    [{ pipelineDealTotalPotentialAmountMin: "100000000" }, "按交易金额查询时必须选择币种"],
    [
      {
        pipelineDealCurrency: "USD",
        pipelineDealTotalPotentialAmountMin: "500000000",
        pipelineDealTotalPotentialAmountMax: "100000000",
      },
      "交易潜在总额下限不能大于上限",
    ],
  ];

  it.each(invalidPipelineSignalCases)(
    "rejects an invalid professional pipeline signal combination",
    (changes, expected) => {
      const draft = { ...createProfessionalSearchDraft("pipeline", "EGFR"), ...changes };
      expect(validateProfessionalSearch(draft)).toBe(expected);
    },
  );

  it("rejects a result evaluation when the professional trial query explicitly requires no results", () => {
    const draft = {
      ...createProfessionalSearchDraft("trials", "EGFR"),
      trialHasResults: "false",
      trialResultEvaluation: "positive",
    };
    expect(validateProfessionalSearch(draft)).toBe("选择“未发布结果”时不能同时限定结果评价");
  });

  it("rejects a reversed disclosure date range in the professional trial query", () => {
    const draft = {
      ...createProfessionalSearchDraft("trials", "EGFR"),
      trialDisclosedFrom: "2026-07-31",
      trialDisclosedTo: "2026-06-01",
    };
    expect(validateProfessionalSearch(draft)).toBe("结果披露日期起始值不能晚于结束值");
  });

  it.each([
    [{ dealAnnouncedFrom: "2026-02-01", dealAnnouncedTo: "2026-01-01" }, "初始披露日期起始日期不能晚于结束日期"],
    [{ dealTerminatedFrom: "2026-03-01", dealTerminatedTo: "2026-02-01" }, "终止日期起始日期不能晚于结束日期"],
    [
      { dealSourceUpdatedFrom: "2026-04-01", dealSourceUpdatedTo: "2026-03-01" },
      "信息更新日期起始日期不能晚于结束日期",
    ],
    [{ dealUpfrontAmountMin: "30", dealUpfrontAmountMax: "10" }, "首付款下限不能高于上限"],
    [{ dealTotalPotentialAmountMin: "500", dealTotalPotentialAmountMax: "100" }, "潜在总额下限不能高于上限"],
    [{ dealDirection: "outbound" }, "引进或对外许可必须选择方向参照地区"],
  ] as const)("rejects an invalid professional deal combination", (changes, expected) => {
    const draft = { ...createProfessionalSearchDraft("deals", "EGFR"), ...changes };
    expect(validateProfessionalSearch(draft)).toBe(expected);
  });
});
