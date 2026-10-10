import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import {
  sourceOperationalLabel,
  sourceReadinessGuidance,
  sourceReadinessRawDiagnostic,
} from "../views/dataFactory/sourceReadinessPresentation";

it("formats only known source states and keeps prototype-like codes literal", () => {
  setLocale("en");
  expect(sourceOperationalLabel("ready")).toBe("Ready");
  for (const code of ["constructor", "__proto__", "CUSTOM_SOURCE_STATE"])
    expect(sourceOperationalLabel(code)).toBe(code);
  setLocale("zh-CN");
  expect(sourceOperationalLabel("ready")).toBe("就绪");
});

it("uses the source success observation for freshness guidance rather than parsing arbitrary prose", () => {
  setLocale("en");
  const check = { code: "freshness", message: "Original unexpected diagnostic" };
  expect(sourceReadinessGuidance(check, null)).toBe("The first successful scan has not completed");
  expect(sourceReadinessGuidance(check, 200000)).toBe("The source has exceeded its freshness objective");
  expect(sourceReadinessRawDiagnostic(check, null)).toBe("Original unexpected diagnostic");
  expect(
    sourceReadinessRawDiagnostic({ code: "freshness", message: "Source has not completed its first scan" }, null),
  ).toBeNull();
});

it("preserves unknown source diagnostic text including markup characters", () => {
  setLocale("en");
  expect(sourceReadinessGuidance({ code: "constructor", message: "原始失败 <RAW>" }, null)).toBe("原始失败 <RAW>");
  expect(sourceReadinessGuidance({ code: "provider-specific", message: "Original provider failure" }, null)).toBe(
    "Original provider failure",
  );
});
