import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { explorerMessages } from "../lib/i18n/explorer";
import { explorerSaveFeedback } from "../views/explorer/saveFeedback";

it("reformats a retained partial outcome in the active language without altering its source reason", () => {
  const outcome = { kind: "monitor_failed" as const, reason: "Original <EGFR> {reason} 科研" };
  setLocale("en");
  expect(explorerSaveFeedback(outcome)).toBe(
    "Search saved, but monitoring was not enabled: Original <EGFR> {reason} 科研",
  );
  setLocale("zh-CN");
  expect(explorerSaveFeedback(outcome)).toBe("检索已保存，但监控未启用：Original <EGFR> {reason} 科研");
  expect(outcome.reason).toBe("Original <EGFR> {reason} 科研");
});
it("distinguishes saved, monitored, rejected and missing-reason feedback in both languages", () => {
  for (const locale of ["en", "zh-CN"] as const) {
    setLocale(locale);
    expect(explorerSaveFeedback({ kind: "saved", monitoring: false })).toBe(
      locale === "en" ? "Search saved" : "基础查询检索已保存",
    );
    expect(explorerSaveFeedback({ kind: "saved", monitoring: true })).toBe(
      locale === "en" ? "Search saved and monitoring enabled" : "基础查询检索已保存并启用监控",
    );
    expect(explorerSaveFeedback({ kind: "monitor_failed", reason: null })).toContain(
      locale === "en" ? "Unknown error" : "未知错误",
    );
    expect(explorerSaveFeedback({ kind: "failed", reason: null })).toBe(
      locale === "en" ? "Could not save the search." : "保存失败",
    );
    expect(explorerSaveFeedback({ kind: "failed", reason: "Original rejection 科研" })).toBe("Original rejection 科研");
    expect(explorerSaveFeedback("Original comparison feedback 科研")).toBe("Original comparison feedback 科研");
  }
});
it("keeps the feature catalog's interpolation parameters complete", () => {
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(explorerMessages)) {
    expect(english.trim(), key).not.toBe("");
    expect(parameters(english), key).toEqual(parameters(key));
  }
});
