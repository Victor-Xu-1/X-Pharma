import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { knowledgeMessages } from "../lib/i18n/knowledge";
import { knowledgeFieldMessages } from "../lib/i18n/knowledgeFields";
import { knowledgeTrialFieldText } from "../views/knowledge/knowledgeTrialFields";

it("pairs knowledge message parameters and keeps query ownership out of presentation panels", () => {
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const catalog of [knowledgeMessages, knowledgeFieldMessages])
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(parameters(english), key).toEqual(parameters(key));
    }
  for (const module of ["KnowledgeCoverage", "KnowledgeVersionHistory"])
    expect(readFileSync(resolve(process.cwd(), `src/views/knowledge/${module}.tsx`), "utf8")).not.toMatch(
      /\b(?:useQuery|useMutation|useState)\s*\(/,
    );
  const view = readFileSync(resolve(process.cwd(), "src/views/KnowledgeView.tsx"), "utf8");
  expect(view.split("\n").length).toBeLessThan(300);
  expect(view.match(/\buseQuery\s*\(/g)).toHaveLength(5);
});

it("formats recorded precision without inventing dates or translating unknown clinical values", () => {
  setLocale("en");
  expect(
    knowledgeTrialFieldText("2028-02-01T00:00:00Z", "completion_date", { completion_date_precision: "month" }),
  ).toBe("2028-02");
  expect(knowledgeTrialFieldText("2028", "completion_date", { completion_date_precision: "year" })).toBe("2028");
  expect(knowledgeTrialFieldText("2028-02", "completion_date", { completion_date_precision: "day" })).toBeNull();
  expect(knowledgeTrialFieldText("2028-02-30", "completion_date", { completion_date_precision: "day" })).toBeNull();
  expect(
    knowledgeTrialFieldText("2028-02-01T12:00:00Z", "completion_date", { completion_date_precision: "day" }),
  ).toBeNull();
  expect(knowledgeTrialFieldText("FUTURE_STATUS", "overall_status", {})).toBe("FUTURE_STATUS");
  expect(knowledgeTrialFieldText("原始登记状态", "overall_status", {})).toBe("原始登记状态");
});
