import { expect, it } from "vitest";
import {
  dealLabel,
  dealTypeLabels,
  directionLabels,
  localizedDealLabels,
  partyRoleLabels,
  phaseLabels,
  rightTypeLabels,
  statusLabels,
} from "../lib/dealDisplay";
import { setLocale } from "../lib/i18n";
import { dealMessages } from "../lib/i18n/deals";
import { dealSaveFeedback } from "../views/deals/saveFeedback";

it("pairs every deal caption with the same interpolation slots and an English rendering", () => {
  const slots = (text: string) => [...text.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(dealMessages)) {
    expect(english.trim(), key).not.toBe("");
    expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
    expect(slots(english), key).toEqual(slots(key));
  }
});

it("translates only project-owned deal vocabulary and keeps prototype/future codes literal", () => {
  for (const locale of ["en", "zh-CN"] as const) {
    setLocale(locale);
    for (const labels of [
      dealTypeLabels,
      directionLabels,
      partyRoleLabels,
      phaseLabels,
      rightTypeLabels,
      statusLabels,
    ]) {
      const translated = localizedDealLabels(labels);
      expect(Object.keys(translated)).toEqual(Object.keys(labels));
      for (const [code, caption] of Object.entries(labels)) {
        if (locale === "en") expect(translated[code]).not.toMatch(/[\u3400-\u9fff]/u);
        else expect(translated[code]).toBe(caption);
      }
      for (const code of ["constructor", "__proto__", "toString", "RAW_future_Code"])
        expect(dealLabel(code, labels)).toBe(code);
      expect(dealLabel("RAW_CODE", labels, "原始来源标签")).toBe("原始来源标签");
    }
  }
});

it("translates saved/partial-success framing without changing the raw source reason", () => {
  const feedback = { kind: "outcome", outcome: { kind: "monitor_failed", reason: "原始失败 <Contract>" } } as const;
  setLocale("en");
  expect(dealSaveFeedback(feedback)).toBe("Search saved, but monitoring could not be enabled: 原始失败 <Contract>");
  setLocale("zh-CN");
  expect(dealSaveFeedback(feedback)).toBe("检索已保存，但监控未启用：原始失败 <Contract>");
});
