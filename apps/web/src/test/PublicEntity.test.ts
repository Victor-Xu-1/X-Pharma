import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { publicEntityAttributeLabel, publicEntityAttributes } from "../lib/publicEntity";

it("localizes metadata headings without transforming their scientific values", () => {
  const attributes = { mechanism: "来源机制 EGFR", smiles: "C[C@H](O)N", identity_note: "原始身份说明" };
  setLocale("en");
  expect(publicEntityAttributeLabel("mechanism")).toBe("Mechanism of action");
  expect(publicEntityAttributeLabel("smiles")).toBe("Structure notation");
  expect(publicEntityAttributes({ attributes })).toEqual(Object.entries(attributes));
  setLocale("zh-CN");
  expect(publicEntityAttributeLabel("mechanism")).toBe("作用机制");
});

it("uses only own allowlisted attribute names and primitive values", () => {
  const attributes = JSON.parse(
    '{"__proto__":"hidden","constructor":"hidden","toString":"hidden","source_secret":"hidden","country":"中国","mechanism":{"raw":"hidden"},"program_tags":["中文标签",true,null]}',
  );
  expect(publicEntityAttributes({ attributes })).toEqual([
    ["country", "中国"],
    ["program_tags", ["中文标签", true, null]],
  ]);
  expect(publicEntityAttributeLabel("constructor")).toBe("constructor");
});
