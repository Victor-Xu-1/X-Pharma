import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { targetCoverageLabelKeys, targetDossierMessages } from "../lib/i18n/targetDossier";
import {
  targetEvidenceDirectionKeys,
  targetEvidenceDirectionLabel,
  targetEvidenceMessages,
  targetEvidenceTypeKeys,
  targetEvidenceTypeLabel,
} from "../lib/i18n/targetEvidence";
import { organismLabel, targetClassLabel } from "../lib/targetDisplay";
import { developmentPhaseLabel, developmentPhaseLabels } from "../views/target/pipeline/presentation";

it("keeps target-owned message parameters paired and coverage labels registered", () => {
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries({ ...targetDossierMessages, ...targetEvidenceMessages })) {
    expect(english.trim(), key).not.toBe("");
    expect(parameters(english), key).toEqual(parameters(key));
  }
  for (const key of Object.values(targetCoverageLabelKeys))
    expect(Object.hasOwn(targetDossierMessages, key)).toBe(true);
});

it("keeps one controlled evidence dictionary for options and row statements", () => {
  setLocale("en");
  for (const key of Object.keys(targetEvidenceTypeKeys) as Array<keyof typeof targetEvidenceTypeKeys>)
    expect(targetEvidenceTypeLabel(key)).not.toBe("");
  for (const key of Object.keys(targetEvidenceDirectionKeys) as Array<keyof typeof targetEvidenceDirectionKeys>)
    expect(targetEvidenceDirectionLabel(key)).not.toBe("");
  expect(targetEvidenceTypeLabel("genetic_association")).toBe("Genetic association");
  expect(targetEvidenceDirectionLabel("supports")).toBe("Supports the target hypothesis");
  setLocale("zh-CN");
  expect(targetEvidenceTypeLabel("genetic_association")).toBe("遗传关联");
  expect(targetEvidenceDirectionLabel("supports")).toBe("支持靶点假设");
});

it("translates only controlled target classification and leaves unknown source values literal", () => {
  setLocale("en");
  expect(targetClassLabel("Single protein")).toBe("Single protein");
  expect(targetClassLabel(" PROTEIN-COMPLEX ")).toBe("Protein complex");
  expect(targetClassLabel(null)).toBe("Unclassified target");
  expect(organismLabel("Homo sapiens")).toBe("Human");
  expect(organismLabel("mus-musculus")).toBe("Mouse");
  expect(organismLabel(undefined)).toBe("Organism not recorded");
  for (const value of ["来源原始分类", "constructor", "toString", "__proto__"]) {
    expect(targetClassLabel(value)).toBe(value);
    expect(organismLabel(value)).toBe(value);
    expect(developmentPhaseLabel(value)).toBe(value);
  }
  setLocale("zh-CN");
  expect(targetClassLabel("Single protein")).toBe("单蛋白");
  expect(organismLabel("Homo sapiens")).toBe("人");
});

it("uses the sole phase dictionary and preserves codes and unknown phase literals", () => {
  setLocale("en");
  for (const code of Object.keys(developmentPhaseLabels)) expect(() => developmentPhaseLabel(code)).not.toThrow();
  expect(developmentPhaseLabel("phase_2")).toBe("Phase II");
  expect(developmentPhaseLabel("FILED")).toBe("Marketing application filed");
  expect(developmentPhaseLabel("来源原始阶段")).toBe("来源原始阶段");
  setLocale("zh-CN");
  expect(developmentPhaseLabel("phase_2")).toBe("II 期");
  expect(developmentPhaseLabel("FILED")).toBe("申报上市");
});
