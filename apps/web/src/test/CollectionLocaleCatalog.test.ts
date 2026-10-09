import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import { profilePhase } from "../components/collectionComparisonPresentation";
import { setLocale } from "../lib/i18n";
import { collectionExportMessages } from "../lib/i18n/collectionExport";
import { collectionMatrixMessages } from "../lib/i18n/collectionMatrix";
import { collectionsMessages } from "../lib/i18n/collections";
import { localizedProgramModality, programVocabularyMessages } from "../lib/i18n/programVocabulary";
import { researchMetadataMessages } from "../lib/i18n/researchMetadata";

it("pairs collection message parameters and keeps matrix reads out of presentation-only modules", () => {
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const catalog of [
    collectionsMessages,
    collectionExportMessages,
    collectionMatrixMessages,
    researchMetadataMessages,
    programVocabularyMessages,
  ])
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(parameters(english), key).toEqual(parameters(key));
    }
  for (const module of ["CollectionComparisonMatrix", "DrugComparisonMatrix", "collectionComparisonPresentation"]) {
    const source = readFileSync(resolve(process.cwd(), `src/components/${module}.tsx`), "utf8");
    expect(source.split("\n").length).toBeLessThan(300);
    if (module === "CollectionComparisonMatrix") {
      expect(source.match(/\buseQuery\s*\(/g)).toHaveLength(1);
      expect(source.match(/\buseQueries\s*\(/g)).toHaveLength(1);
    } else expect(source).not.toMatch(/\b(?:useQuery|useQueries|useMutation)\s*\(/);
  }
});

it("keeps unknown and prototype-like phase values literal while localizing existing phase captions", () => {
  setLocale("en");
  expect(profilePhase("phase_2")).toBe("Phase II");
  expect(profilePhase("FUTURE_PHASE")).toBe("FUTURE_PHASE");
  expect(profilePhase("constructor")).toBe("constructor");
  expect(localizedProgramModality("SMALL_MOLECULE")).toBe("Small molecule");
  expect(localizedProgramModality("biologic")).toBe("biologic");
  expect(localizedProgramModality("FUTURE_MODALITY")).toBe("FUTURE_MODALITY");
  setLocale("zh-CN");
  expect(profilePhase("phase_2")).toBe("II期");
});
