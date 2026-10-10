import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { factoryMessages, factoryText } from "../lib/i18n/dataFactory";

it("pairs every factory message with identical interpolation parameters in both languages", () => {
  const fields = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(factoryMessages)) {
    expect(english.trim().length).toBeGreaterThan(0);
    expect(fields(english), key).toEqual(fields(key));
  }
});

it("translates source control framing but leaves names, paths and identifiers literal", () => {
  setLocale("en");
  expect(factoryText("编辑 {name}", { name: "原始 Source <Bio>" })).toBe("Edit 原始 Source <Bio>");
  setLocale("zh-CN");
  expect(factoryText("编辑 {name}", { name: "原始 Source <Bio>" })).toBe("编辑 原始 Source <Bio>");
});
