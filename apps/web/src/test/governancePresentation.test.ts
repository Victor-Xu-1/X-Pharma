import { expect, it } from "vitest";
import { governanceLabel, payloadDifferences, reviewValue } from "../lib/governancePresentation";

it("compares actual old/new business fields without treating citation changes as fact changes", () => {
  const differences = payloadDifferences(
    { phase: "phase_2", subject: { name: "EGFR" }, missing: null, citation: { confidence: 1 } },
    { phase: "phase_3", subject: { name: "ERBB1" }, added: ["CN"], citation: { confidence: 0.8 } },
  );
  expect(differences.map((row) => row.path)).toEqual(["added", "missing", "phase", "subject.name"]);
  expect(reviewValue(differences[0].before)).toBe("字段不存在");
  expect(reviewValue(differences[1].before)).toBe("未披露");
  expect(governanceLabel("subject.name")).toBe("研究对象 / 名称");
});
