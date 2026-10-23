import { expect, it } from "vitest";
import { displayTerms, formatAmount } from "../lib/dealDisplay";
import { setLocale } from "../lib/i18n";

it("retains source amount precision and currency without implicit conversion or rounding", () => {
  setLocale("en");
  expect(formatAmount(1.25, "USD")).toBe("USD 1.25");
  expect(formatAmount(0.000123456, "CNY")).toBe("CNY 0.000123456");
  expect(formatAmount(25_123_456.75, "USD")).toBe("USD 25,123,456.75");
  expect(formatAmount(0, "JPY")).toBe("JPY 0");
});

it("localizes only missing-amount framing and retains an unknown original currency code", () => {
  setLocale("en");
  expect(formatAmount(null, "USD")).toBe("Undisclosed");
  expect(formatAmount(1.5, "RAW_CURRENCY")).toBe("RAW_CURRENCY 1.5");
  setLocale("zh-CN");
  expect(formatAmount(null, "USD")).toBe("未披露");
});

it("keeps nested source term values and zero/false instead of flattening objects", () => {
  expect(displayTerms({ royalty: { lower: 0, contingent: false }, clauses: ["原始 <license>", 0] })).toBe(
    'royalty: {"lower":0,"contingent":false} · clauses: ["原始 <license>",0]',
  );
});
