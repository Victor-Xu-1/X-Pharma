import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { monitoringMessages } from "../lib/i18n/monitoring";
import { savedSearchMessages } from "../lib/i18n/savedSearch";
import { trialVocabularyMessages } from "../lib/i18n/trialVocabulary";
import { savedSearchConditionFields } from "../views/monitoring/savedSearchConditionFields";
import { savedSearchConditionValue } from "../views/monitoring/savedSearchConditionValue";

it("pairs monitoring message parameters and keeps condition presentation modules bounded and query-free", () => {
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const catalog of [monitoringMessages, savedSearchMessages, trialVocabularyMessages])
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(parameters(english), key).toEqual(parameters(key));
    }
  for (const module of ["savedSearchPresentation", "savedSearchConditionFields", "savedSearchConditionValue"]) {
    const source = readFileSync(resolve(process.cwd(), `src/views/monitoring/${module}.ts`), "utf8");
    expect(source.split("\n").length).toBeLessThan(300);
    expect(source).not.toMatch(/\b(?:useQuery|useMutation|useState)\s*\(/);
  }
});

it("represents every professional saved-query field without dropping filters, dates, numeric bounds or sort intent", () => {
  const domains = [
    ["pipeline_search", "PipelineSavedSearchQuery"],
    ["clinical_trial_search", "ClinicalTrialSavedSearchQuery"],
    ["patent_search", "PatentSavedSearchQuery"],
    ["deal_search", "DealSavedSearchQuery"],
    ["regulatory_search", "RegulatorySavedSearchQuery"],
    ["epidemiology_search", "EpidemiologySavedSearchQuery"],
    ["news_search", "NewsSavedSearchQuery"],
  ];
  for (const [kind, schema] of domains) {
    const source = readFileSync(resolve(process.cwd(), `src/lib/generated/models/${schema}.ts`), "utf8");
    const properties = [...source.matchAll(/^\s+(?:'([^']+)'|([a-z_]+))\?:/gm)].map((match) => match[1] ?? match[2]);
    const represented = new Set(savedSearchConditionFields[kind].map((field) => field.key));
    const missing = properties.filter(
      (key) => !["q", "display_mode", "analysis_view"].includes(key) && !represented.has(key),
    );
    expect(missing, schema).toEqual([]);
  }
});

it("retains zero, false, unknown vocabulary and original text while translating registered values", () => {
  setLocale("en");
  expect(savedSearchConditionValue(0, "upfront_amount_min", "deal_search")).toBe("0");
  expect(savedSearchConditionValue(false, "has_results", "clinical_trial_search", "boolean")).toBe("No");
  expect(savedSearchConditionValue("RECRUITING", "status", "clinical_trial_search")).toBe("Recruiting");
  expect(savedSearchConditionValue("FUTURE_PHASE", "phase", "pipeline_search")).toBe("FUTURE_PHASE");
  expect(savedSearchConditionValue("原始研究条件", "applicant", "patent_search", "text")).toBe("原始研究条件");
  expect(savedSearchConditionValue(0.0000001, "total_potential_amount_min", "deal_search")).toBe("1e-7");
});
