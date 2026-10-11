import { expect, it } from "vitest";
import { dossierCoverageNoteText } from "../lib/i18n/dossierCoverageNote";

const messages = [
  ["当前可查看范围和数据更新时间内暂无记录", "No records observed within the current visibility and update window"],
  ["已返回当前匹配记录", "Current matching records returned"],
  [
    "实体级证据通过证据检索和记录来源接口按许可读取",
    "Entity evidence is available through evidence search and record provenance, subject to source permissions",
  ],
] as const;
it.each(messages)("localizes only the known application coverage statement %s", (note, english) => {
  expect(dossierCoverageNoteText(note, "en")).toBe(english);
  expect(dossierCoverageNoteText(note, "zh-CN")).toBe(note);
});
it("preserves the exact count string in the application pagination message without numeric conversion", () => {
  const count = "999999999999999999999";
  const original = `返回前 ${count} 条，完整结果请使用对应分页接口`;
  expect(dossierCoverageNoteText(original, "en")).toBe(
    `First ${count} records returned; use the matching paginated endpoint for complete results`,
  );
  expect(dossierCoverageNoteText(original, "zh-CN")).toBe(original);
});
it.each(["原始科研来源说明 / Source-owned narrative", "返回前 several 条，完整结果请使用对应分页接口"])(
  "retains unknown/source-owned note verbatim in both languages: %s",
  (note) => {
    expect(dossierCoverageNoteText(note, "en")).toBe(note);
    expect(dossierCoverageNoteText(note, "zh-CN")).toBe(note);
  },
);
