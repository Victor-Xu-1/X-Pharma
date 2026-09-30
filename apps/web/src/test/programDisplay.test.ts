import { describe, expect, it } from "vitest";

import { programModalityLabel, programTagLabel, publicProgramTags } from "../lib/programDisplay";

describe("programModalityLabel", () => {
  it.each([
    ["small molecule", "小分子"],
    ["bispecific-antibody", "双特异性抗体"],
    ["antibody drug conjugate", "抗体偶联药物（ADC）"],
  ])("renders governed value %s for public users", (value, expected) => {
    expect(programModalityLabel(value)).toBe(expected);
  });

  it.each([
    ["GENE THERAPY", "基因治疗"],
    ["MOLECULAR-GLUE", "分子胶"],
  ])("maps live source modality %s to %s", (value, expected) => {
    expect(programModalityLabel(value)).toBe(expected);
  });

  it("preserves an unknown scientific value instead of guessing a translation", () => {
    expect(programModalityLabel("Novel switch binder")).toBe("Novel switch binder");
    expect(programModalityLabel("INHIBITOR")).toBe("INHIBITOR");
  });
});

describe("publicProgramTags", () => {
  it("removes source and duplicated phase metadata while preserving business tags", () => {
    expect(
      publicProgramTags([
        "ChEMBL",
        "maximum clinical phase 2",
        "first_in_class",
        "Novel switch binder",
        "first_in_class",
      ]),
    ).toEqual(["first_in_class", "Novel switch binder"]);
  });

  it("maps governed business tags and preserves unknown scientific terms", () => {
    expect(programTagLabel("first_in_class")).toBe("First-in-Class");
    expect(programTagLabel("Novel switch binder")).toBe("Novel switch binder");
  });
});
