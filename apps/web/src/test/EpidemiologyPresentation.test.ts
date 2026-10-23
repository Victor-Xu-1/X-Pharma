import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { comparableTrend, formatNumber, trendMatchesSelection } from "../views/epidemiology/presentation";
import { observation, searchResult } from "./fixtures/epidemiologyResearch";

it("retains zero and sub-milliscale estimates without three-decimal rounding", () => {
  for (const locale of ["en", "zh-CN"] as const) {
    setLocale(locale);
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(0.000123456)).toBe("0.000123456");
    expect(formatNumber(null)).toBe("--");
  }
});

it.each([
  { anchor_observation_id: "foreign" },
  { anchor_observation_id: null },
  { items: [{ ...observation, publisher_entity_id: "foreign" }] },
  { items: [{ ...observation, methodology: "FOREIGN_METHOD" }] },
])("does not combine a different anchor, publisher or methodology into the cohort", (change) => {
  const data = {
    disease: observation.disease_entity,
    anchor_observation_id: observation.id,
    items: [observation],
    total: 1,
    truncated: false,
    as_of: searchResult.as_of,
    warnings: [],
    ...change,
  };
  expect(trendMatchesSelection(data, comparableTrend(observation))).toBe(false);
});
