import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { pipelineMessages } from "../lib/i18n/pipeline";
import { pipelineLandscapeMessages } from "../lib/i18n/pipelineLandscape";
import {
  localizedDevelopmentPhase,
  localizedProgramModality,
  localizedProgramTag,
} from "../lib/i18n/programVocabulary";
import { compactPhaseLabels, spacedPhaseLabels } from "../lib/phasePresentation";
import { pipelineSaveFeedback } from "../views/pipeline/saveFeedback";

it.each([pipelineMessages, pipelineLandscapeMessages])(
  "has complete literal caption pairs and identical interpolation slots",
  (catalog) => {
    const slots = (value: string) =>
      [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/g)].map((match) => match[1]).sort();
    for (const [key, value] of Object.entries(catalog)) {
      expect(value.trim(), key).not.toBe("");
      expect(slots(value), key).toEqual(slots(key));
    }
  },
);
it("uses the original phase authority in both languages and preserves unknown scientific codes and labels", () => {
  setLocale("zh-CN");
  for (const code of Object.keys(compactPhaseLabels)) {
    expect(localizedDevelopmentPhase(code)).toBe(compactPhaseLabels[code]);
    expect(localizedDevelopmentPhase(code, true)).toBe(spacedPhaseLabels[code]);
  }
  setLocale("en");
  expect(localizedDevelopmentPhase("filed")).toBe("Filed");
  expect(localizedDevelopmentPhase("phase_2")).toBe("Phase II");
  expect(localizedProgramTag("next_generation")).toBe("Next generation");
  expect(localizedProgramModality("未知模态 EGFR")).toBe("未知模态 EGFR");
  expect(localizedProgramTag("未知标签 EGFR")).toBe("未知标签 EGFR");
  expect(localizedDevelopmentPhase("未知阶段 EGFR")).toBe("未知阶段 EGFR");
});
it("translates owned partial/success/failure captions but never parses or rewrites the provider's reason", () => {
  const partial = { kind: "monitor_failed" as const, reason: "原始原因 管线检索已保存 <EGFR>" };
  setLocale("en");
  expect(pipelineSaveFeedback(partial)).toBe(
    "Search saved, but monitoring was not enabled: 原始原因 管线检索已保存 <EGFR>",
  );
  expect(pipelineSaveFeedback({ kind: "failed", reason: null })).toBe("Could not save the pipeline search");
  expect(pipelineSaveFeedback({ kind: "failed", reason: "管线检索保存失败" })).toBe("管线检索保存失败");
  setLocale("zh-CN");
  expect(pipelineSaveFeedback(partial)).toBe("检索已保存，但监控未启用：原始原因 管线检索已保存 <EGFR>");
});
