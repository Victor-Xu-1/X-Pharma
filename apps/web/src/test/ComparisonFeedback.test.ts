import { expect, it } from "vitest";
import { type ComparisonFeedback, comparisonFailure, comparisonFeedbackText } from "../lib/comparisonFeedback";
import { setLocale } from "../lib/i18n";

it("retains a conflict as structured UI state so its message follows the active language", () => {
  const feedback = comparisonFailure(new Error("expected_version changed concurrently"), "成员写入失败");
  expect(comparisonFeedbackText(feedback)).toBe("列表内容已更新，请重新确认后再试");
  setLocale("en");
  expect(comparisonFeedbackText(feedback)).toBe("This list has been updated. Review it before trying again.");
});

it("preserves unknown server reasons instead of treating them as translatable research content", () => {
  const feedback = comparisonFailure(new Error("服务器原文 EGFR"), "成员写入失败");
  setLocale("en");
  expect(comparisonFeedbackText(feedback)).toBe("服务器原文 EGFR");
});

it("keeps partial success and remaining capacity accurate in either language", () => {
  const partial: ComparisonFeedback = { created: comparisonFailure(new Error("write unavailable"), "成员写入失败") };
  setLocale("en");
  expect(comparisonFeedbackText(partial)).toBe(
    "The list was created, but members were not added. The new list is retained; review and retry the addition. Could not add members",
  );
  expect(
    comparisonFeedbackText({ key: "该列表还可添加 {count} 个实体，请减少选择后重试", parameters: { count: 0 } }),
  ).toContain("room for 0 more entities");
  setLocale("zh-CN");
  expect(comparisonFeedbackText(partial)).toBe(
    "列表已创建，但成员尚未加入；已保留新列表，请重新确认加入。成员写入失败",
  );
  expect(comparisonFeedbackText(null)).toBe("");
});
