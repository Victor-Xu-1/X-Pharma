import { act, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { setLocale } from "../lib/i18n";
import { recordedCalendarDate } from "../lib/recordedCalendarDate";
import { clinicalContentRows } from "../views/trials/contentRows";
import { displayBoolean, formatResultRange } from "../views/trials/presentation";
import { TrialDesign } from "../views/trials/TrialDesign";
import { TrialOutcomes } from "../views/trials/TrialOutcomes";
import { TrialRecordedDate } from "../views/trials/TrialRecordedDate";
import { TrialStatisticalAnalysis } from "../views/trials/TrialStatisticalAnalysis";
import { trialDetail } from "./fixtures/clinicalTrial";

it.each([
  ["2026-07-01T00:00:00Z", "month", "2026-07"],
  ["2026-01-01T00:00:00.000+00:00", "year", "2026"],
  ["2024-02-29", "day", "2024-02-29"],
  ["2026-02-29", "day", null],
  ["2026-13", "month", null],
  ["2026-07-01T12:00:00Z", "month", null],
  ["2026-07-01", "RAW_PRECISION", null],
  ["2026-07-01", null, null],
] as const)(
  "honors recorded calendar precision for %s / %s without timezone or precision inference",
  (value, precision, expected) => {
    setLocale("en");
    expect(recordedCalendarDate(value, precision)).toBe(expected);
  },
);

it("retains an unknown date precision literally rather than calling it year precision", () => {
  setLocale("en");
  render(<TrialRecordedDate value="2026-07-01" precision="RAW_PRECISION" />);
  expect(screen.getByText("2026-07-01")).toBeVisible();
  expect(screen.getByText("Date precision: RAW_PRECISION")).toBeVisible();
  act(() => setLocale("zh-CN"));
  // Render-bound parent localization is deliberately absent in this pure isolated component.
  expect(screen.getByText("2026-07-01")).toBeVisible();
});

it("retains literal zero, false, partial bounds and dispersion", () => {
  setLocale("en");
  expect(displayBoolean(false)).toBe("No");
  expect(formatResultRange(0, null, "原始 dispersion")).toBe(
    "Lower limit: 0 · Upper limit not reported · 原始 dispersion",
  );
  expect(formatResultRange(null, 0)).toBe("Lower limit not reported · Upper limit: 0");
  expect(formatResultRange(0, 1, "source SD")).toBe("0-1 · source SD");
  expect(formatResultRange(null, null)).toBe("--");
});

it.each([0, 90, 99])("preserves the actually reported confidence level %s, notes, p and parameter zeros", (level) => {
  setLocale("en");
  render(
    <TrialStatisticalAnalysis
      analysis={{
        method: "原始方法",
        parameter_type: "RAW_TYPE",
        parameter_value: 0,
        p_value: "0",
        confidence_interval_percent: level,
        lower_limit: null,
        upper_limit: 0,
        notes: "原始 notes",
      }}
    />,
  );
  expect(screen.getByText(new RegExp(`${level}% CI`))).toHaveTextContent("Upper limit: 0");
  expect(screen.getByText(/p=0/)).toBeVisible();
  expect(screen.getByText("原始 notes")).toBeVisible();
  expect(screen.getByText("RAW_TYPE")).toBeVisible();
});

it("preserves identical source rows with unique stable content-occurrence keys", () => {
  const raw = { group_label: "原始组", value: "0", participants: 0 };
  const rows = clinicalContentRows([raw, raw, { ...raw, value: "1" }]);
  expect(rows.map((row) => row.value)).toEqual([raw, raw, { ...raw, value: "1" }]);
  expect(new Set(rows.map((row) => row.key)).size).toBe(3);
  expect(clinicalContentRows([raw, raw]).map((row) => row.key)).toEqual(rows.slice(0, 2).map((row) => row.key));
});

it("keeps original eligibility text keyboard-readable in its scrolling region", () => {
  setLocale("en");
  render(
    <TrialDesign
      data={{ ...trialDetail, eligibility: { ...trialDetail.eligibility, criteria: "原始资格原文\nSOURCE_CRITERIA" } }}
    />,
  );
  const criteria = screen.getByRole("region", { name: "Original eligibility criteria" });
  expect(criteria).toHaveAttribute("tabindex", "0");
  expect(criteria).toHaveTextContent("原始资格原文");
  expect(criteria.textContent).toBe("原始资格原文\nSOURCE_CRITERIA");
});

it("renders duplicate source outcomes and result groups without dropped rows or key warnings", () => {
  setLocale("en");
  const error = vi.spyOn(console, "error");
  const result = { group_label: "SOURCE_GROUP", value: "0", participants: 0 };
  const outcome = { outcome_type: "SOURCE_TYPE", measure: "SOURCE_ENDPOINT", results: [result, result] };
  render(<TrialOutcomes data={{ ...trialDetail, outcomes: [outcome, outcome] }} />);
  expect(screen.getAllByRole("row", { name: /SOURCE_GROUP/ })).toHaveLength(4);
  expect(screen.getAllByRole("heading", { name: "SOURCE_ENDPOINT" })).toHaveLength(2);
  expect(error.mock.calls.flat().join(" ")).not.toContain("same key");
});
