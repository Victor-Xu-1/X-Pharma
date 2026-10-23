import { expect, it } from "vitest";
import {
  emptyPatentSearchFilters,
  patentLegalStatusLabels,
  validatePatentSearchFilters,
} from "../lib/contracts/patents";
import { setLocale } from "../lib/i18n";
import { patentMessages } from "../lib/i18n/patents";
import { patentStatus } from "../lib/patentDisplay";
import { displayPatentList, patentCalendarDate, publicationNumbers } from "../views/patents/presentation";
import { patentSaveFeedback } from "../views/patents/saveFeedback";

it("pairs every patent interface caption with identical interpolation slots", () => {
  const slots = (text: string) => [...text.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(patentMessages)) {
    expect(english.trim(), key).not.toBe("");
    expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
    expect(slots(english), key).toEqual(slots(key));
  }
});

it("translates explicit patent status captions and preserves all unknown codes literally", () => {
  for (const locale of ["en", "zh-CN"] as const) {
    setLocale(locale);
    for (const code of ["constructor", "__proto__", "toString", "custom_status", "Raw Future Code"])
      expect(patentStatus(code)).toBe(code);
    expect(patentStatus("RAW_STATUS", "原始状态标题")).toBe("原始状态标题");
    for (const [code, label] of Object.entries(patentLegalStatusLabels)) {
      if (locale === "en") expect(patentStatus(code)).not.toMatch(/[\u3400-\u9fff]/u);
      else expect(patentStatus(code)).toBe(label);
    }
  }
});

it("keeps original names, identifiers and partial-success reasons while translating their framing", () => {
  const feedback = { kind: "outcome", outcome: { kind: "monitor_failed", reason: "原始错误 <Patent>" } } as const;
  setLocale("en");
  expect(displayPatentList(["原始申请人", "研究机构", "A & B <Lab>"])).toBe("原始申请人 · 研究机构 · 3 in total");
  expect(publicationNumbers([{ publication_number: "WO-原始编号" }])).toBe("WO-原始编号");
  expect(patentSaveFeedback(feedback)).toBe("Search saved, but monitoring could not be enabled: 原始错误 <Patent>");
  setLocale("zh-CN");
  expect(patentSaveFeedback(feedback)).toBe("检索已保存，但监控未启用：原始错误 <Patent>");
});

it("validates both patent date ranges without rewriting or inventing dates", () => {
  expect(
    validatePatentSearchFilters({ ...emptyPatentSearchFilters, priorityFrom: "2026-02-02", priorityTo: "2026-02-01" }),
  ).toBe("优先权日期起始值不能晚于结束值");
  expect(
    validatePatentSearchFilters({
      ...emptyPatentSearchFilters,
      expirationFrom: "2042-02-02",
      expirationTo: "2042-02-01",
    }),
  ).toBe("预计到期日期起始值不能晚于结束值");
  expect(
    validatePatentSearchFilters({ ...emptyPatentSearchFilters, priorityFrom: "2026-02-01", priorityTo: "2026-02-01" }),
  ).toBeNull();
  expect(validatePatentSearchFilters({ ...emptyPatentSearchFilters, expirationTo: "2042-02-01" })).toBeNull();
});

it("renders valid patent calendar days without local-timezone conversion or invalid-date rollover", () => {
  setLocale("en");
  expect(patentCalendarDate("2021-02-03")).toBe("02/03/2021");
  expect(patentCalendarDate("2024-02-29")).toBe("02/29/2024");
  expect(patentCalendarDate("2023-02-29")).toBe("--");
  expect(patentCalendarDate("2026-13-02")).toBe("--");
  expect(patentCalendarDate(null)).toBe("--");
  setLocale("zh-CN");
  expect(patentCalendarDate("2021-02-03")).toBe("2021/02/03");
});
