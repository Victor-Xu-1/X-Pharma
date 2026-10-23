import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { diseaseDossierMessages } from "../lib/i18n/diseaseDossier";
import { dossierRecordMessages } from "../lib/i18n/dossierRecords";
import { targetEvidenceDirectionLabel } from "../lib/i18n/targetEvidence";
import { formatNumber } from "../views/disease/presentation";

it.each([diseaseDossierMessages, dossierRecordMessages])(
  "keeps all owned caption pairs complete and their interpolation slots identical",
  (catalog) => {
    const slots = (text: string) => [...text.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(english, key).not.toMatch(/[\u3400-\u9fff]/u);
      expect(slots(english), key).toEqual(slots(key));
    }
  },
);
it("changes only the controlled evidence subject while preserving the original target interpretation", () => {
  setLocale("en");
  expect(targetEvidenceDirectionLabel("supports")).toBe("Supports the target hypothesis");
  expect(targetEvidenceDirectionLabel("supports", "disease")).toBe("Supports the disease mechanism");
  expect(targetEvidenceDirectionLabel("opposes", "disease")).toBe("Opposes the disease mechanism");
  setLocale("zh-CN");
  expect(targetEvidenceDirectionLabel("supports", "disease")).toBe("支持疾病机制");
  expect(targetEvidenceDirectionLabel("supports")).toBe("支持靶点假设");
});
it("does not round tiny source estimates to zero and preserves zero and missing values", () => {
  setLocale("en");
  expect(formatNumber(0.00000012345)).toBe("0.00000012345");
  expect(formatNumber(0)).toBe("0");
  expect(formatNumber(null)).toBe("--");
  expect(formatNumber(undefined)).toBe("--");
  setLocale("zh-CN");
  expect(formatNumber(0.00000012345)).toBe("0.00000012345");
});
