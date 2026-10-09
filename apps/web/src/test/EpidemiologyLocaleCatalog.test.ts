import { expect, it } from "vitest";
import { epidemiologyMeasureLabels, epidemiologySexLabels } from "../lib/epidemiologyDisplay";
import { setLocale } from "../lib/i18n";
import { epidemiologyMessages } from "../lib/i18n/epidemiology";
import { professionalEnumMessages } from "../lib/i18n/professionalEnums";
import { epidemiologySaveFeedback } from "../views/epidemiology/saveFeedback";

it("pairs complete fixed captions and retains interpolation parameters in English", () => {
  for (const [zh, en] of Object.entries(epidemiologyMessages)) {
    expect(en.trim()).not.toBe("");
    expect(en).not.toMatch(/[\u3400-\u9fff]/);
    expect([...en.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()).toEqual(
      [...zh.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort(),
    );
  }
});

it("uses the existing professional enumeration authority for every known measure and sex", () => {
  for (const label of [...Object.values(epidemiologyMeasureLabels), ...Object.values(epidemiologySexLabels)]) {
    expect(Object.hasOwn(professionalEnumMessages, label)).toBe(true);
  }
});

it("localizes save outcome structure without translating the original provider reason", () => {
  const feedback = { kind: "outcome", outcome: { kind: "monitor_failed", reason: "原始 SOURCE_ERROR" } } as const;
  setLocale("en");
  expect(epidemiologySaveFeedback(feedback)).toBe("Query saved, but monitoring was not enabled: 原始 SOURCE_ERROR");
  setLocale("zh-CN");
  expect(epidemiologySaveFeedback(feedback)).toBe("检索已保存，但监控未启用：原始 SOURCE_ERROR");
});
