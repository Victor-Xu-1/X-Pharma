import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { companyDossierMessages, companyDossierText } from "../lib/i18n/companyDossier";
import { loadedCompanyAssets } from "../views/company/assets";
import { program } from "./fixtures/companyDossier";

it("uses a count-neutral registry summary for one returned study", () => {
  setLocale("en");
  expect(
    companyDossierText(
      "本地已核验的注册关联，当前概览显示 {count} 项；不据此推断企业完整管线、资产所有权或批准用途。",
      {
        count: 1,
      },
    ),
  ).toContain("studies shown in this overview: 1.");
});

it("keeps company caption pairs complete and interpolation slots identical", () => {
  const slots = (text: string) => [...text.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(companyDossierMessages)) {
    expect(english.trim(), key).not.toBe("");
    expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
    expect(slots(english), key).toEqual(slots(key));
  }
});
it("summarizes distinct returned phases and modalities without rewriting or discarding the program rows", () => {
  const rows = [
    { ...program, phase: "RAW_PHASE", modality: "原始模态" },
    { ...program, id: "p-2", phase: "phase_2", modality: "second modality" },
    { ...program, id: "p-3", phase: "RAW_PHASE", modality: "原始模态" },
  ];
  const original = structuredClone(rows);
  expect(loadedCompanyAssets(rows)).toEqual([
    {
      id: program.drug_entity_id,
      name: program.drug_name,
      phases: ["RAW_PHASE", "phase_2"],
      modalities: ["原始模态", "second modality"],
    },
  ]);
  expect(rows).toEqual(original);
  expect(rows).toHaveLength(3);
});
