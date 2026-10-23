import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { domainLandscapeMessages } from "../lib/i18n/domainLandscape";
import { newsMessages } from "../lib/i18n/news";
import { newsSaveFeedback } from "../views/news/saveFeedback";

it("keeps update and statistics caption pairs complete with identical interpolation slots", () => {
  const slots = (text: string) => [...text.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries({ ...newsMessages, ...domainLandscapeMessages })) {
    expect(english.trim(), key).not.toBe("");
    expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
    expect(slots(english), key).toEqual(slots(key));
  }
});

it("retains raw partial-success reasons while translating feedback rather than replaying the operation", () => {
  const feedback = {
    kind: "outcome",
    outcome: { kind: "monitor_failed", reason: "原始 provider <EGFR> error" },
  } as const;
  setLocale("en");
  expect(newsSaveFeedback(feedback)).toBe("Query saved, but monitoring was not enabled: 原始 provider <EGFR> error");
  setLocale("zh-CN");
  expect(newsSaveFeedback(feedback)).toBe("检索已保存，但监控未启用：原始 provider <EGFR> error");
  expect(newsSaveFeedback({ kind: "error", reason: "" })).toBe("");
});
