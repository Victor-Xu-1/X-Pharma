import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { regulatoryMessages } from "../lib/i18n/regulatory";
import { sourceMetadataMessages } from "../lib/i18n/sourceMetadata";
import * as vocabulary from "../lib/regulatoryDisplay";
import { regulatoryBoolean, regulatoryLabels, regulatoryValue } from "../views/regulatory/presentation";
import { regulatorySaveFeedback } from "../views/regulatory/saveFeedback";

it("keeps every regulatory/source UI caption paired with the same interpolation slots", () => {
  const slots = (text: string) => [...text.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries({ ...regulatoryMessages, ...sourceMetadataMessages })) {
    expect(english.trim(), key).not.toBe("");
    expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
    expect(slots(english), key).toEqual(slots(key));
  }
});

it("uses existing controlled producers and preserves unknown/prototype-like source codes", () => {
  setLocale("en");
  for (const labels of Object.values(vocabulary)) {
    const captions = regulatoryLabels(labels);
    expect(Object.keys(captions)).toEqual(Object.keys(labels));
    for (const caption of Object.values(captions)) expect(caption).not.toMatch(/[\u3400-\u9fff]/u);
  }
  for (const code of ["__proto__", "constructor", "toString", "RAW_FUTURE_CODE"]) {
    expect(regulatoryValue(code, vocabulary.eventTypeLabels)).toBe(code);
  }
  expect(regulatoryBoolean(false)).toBe("No");
  expect(regulatoryBoolean(null)).toBe("Not provided");
  expect(regulatoryBoolean(undefined)).toBe("Not provided");
});

it("translates partial-success feedback independently of its unchanged raw reason", () => {
  const feedback = { kind: "outcome", outcome: { kind: "monitor_failed", reason: "原始失败 <FDA>" } } as const;
  setLocale("en");
  expect(regulatorySaveFeedback(feedback)).toBe("Query saved, but monitoring was not enabled: 原始失败 <FDA>");
  setLocale("zh-CN");
  expect(regulatorySaveFeedback(feedback)).toBe("检索已保存，但监控未启用：原始失败 <FDA>");
});
