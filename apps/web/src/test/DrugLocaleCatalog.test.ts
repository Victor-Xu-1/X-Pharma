import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { dossierRecordMessages } from "../lib/i18n/dossierRecords";
import { controlledDossierLabel } from "../lib/i18n/dossierVocabulary";
import { drugDossierCaption, drugDossierMessages } from "../lib/i18n/drugDossier";
import { localizedFullDevelopmentPhase } from "../lib/i18n/programVocabulary";
import { fullPhaseLabels } from "../lib/phasePresentation";
import { regulatoryStatusLabels } from "../lib/regulatoryDisplay";

it.each([drugDossierMessages, dossierRecordMessages])(
  "keeps every owned caption pair complete with identical interpolation slots",
  (catalog) => {
    const slots = (value: string) =>
      [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
      expect(slots(english), key).toEqual(slots(key));
    }
  },
);
it("uses one full-phase authority and leaves scientific unknown codes and source-like strings literal", () => {
  for (const [code, caption] of Object.entries(fullPhaseLabels)) {
    setLocale("zh-CN");
    expect(localizedFullDevelopmentPhase(code)).toBe(caption);
    setLocale("en");
    expect(localizedFullDevelopmentPhase(code)).not.toMatch(/[\u3400-\u9fff]/u);
  }
  expect(localizedFullDevelopmentPhase("RAW_PHASE_CODE")).toBe("RAW_PHASE_CODE");
  expect(controlledDossierLabel("原始 source <EGFR>", regulatoryStatusLabels)).toBe("原始 source <EGFR>");
  expect(controlledDossierLabel("RAW_STATUS_CODE", regulatoryStatusLabels)).toBe("RAW_STATUS_CODE");
  expect(() => drugDossierCaption("原始研究正文")).toThrow("Unknown drug dossier UI caption");
});
