import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { clinicalCaption, clinicalMessages } from "../lib/i18n/clinical";
import { professionalEnumLabel } from "../lib/i18n/professionalEnums";
import { localizedTrialPhase, localizedTrialStatus, localizedTrialStudyType } from "../lib/i18n/trialVocabulary";
import { trialLinkedPhaseLabels } from "../lib/phasePresentation";
import { clinicalSaveFeedback } from "../views/trials/saveFeedback";

it("has complete bilingual clinical captions with identical parameter slots", () => {
  const slots = (value: string) => [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(clinicalMessages)) {
    expect(english.trim(), key).not.toBe("");
    expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
    expect(slots(key), key).toEqual(slots(english));
  }
  expect(() => clinicalCaption("原始研究说明")).toThrow("Unknown clinical UI caption");
});
it("uses existing enum authorities for linked phases and leaves unknown science literal", () => {
  for (const [code, caption] of Object.entries(trialLinkedPhaseLabels)) {
    setLocale("zh-CN");
    expect(professionalEnumLabel(caption, code)).toBe(caption);
    setLocale("en");
    expect(professionalEnumLabel(caption, code)).not.toMatch(/[\u3400-\u9fff]/u);
  }
  expect(localizedTrialPhase("RAW_PHASE_CODE")).toBe("RAW_PHASE_CODE");
  expect(localizedTrialStatus("原始 状态_CODE")).toBe("原始 状态_CODE");
  expect(localizedTrialStudyType("原始研究类型")).toBe("原始研究类型");
  expect(localizedTrialStatus(null)).toBe("Unknown");
});
it("localizes partial success without translating a raw provider reason or replaying a write", () => {
  const outcome = { kind: "monitor_failed" as const, reason: "原始原因 临床试验检索已保存" };
  setLocale("en");
  expect(clinicalSaveFeedback(outcome)).toBe(
    "Search saved, but monitoring was not enabled: 原始原因 临床试验检索已保存",
  );
  setLocale("zh-CN");
  expect(clinicalSaveFeedback(outcome)).toBe("检索已保存，但监控未启用：原始原因 临床试验检索已保存");
});
