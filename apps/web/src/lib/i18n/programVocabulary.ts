import { programModalityLabel } from "../programDisplay";
import { createTranslator } from "./translator";

/** Translate existing program captions only; retain unknown scientific codes. */
export const programVocabularyMessages = {
  小分子: "Small molecule",
  抗体: "Antibody",
  单克隆抗体: "Monoclonal antibody",
  双特异性抗体: "Bispecific antibody",
  "抗体偶联药物（ADC）": "Antibody-drug conjugate (ADC)",
  蛋白药物: "Protein therapy",
  多肽: "Peptide",
  寡核苷酸药物: "Oligonucleotide therapy",
  "RNA 药物": "RNA therapy",
  细胞治疗: "Cell therapy",
  基因治疗: "Gene therapy",
  疫苗: "Vaccine",
  分子胶: "Molecular glue",
  PROTAC: "PROTAC",
  降解剂: "Degrader",
} as const;
const text = createTranslator(programVocabularyMessages);
export function localizedProgramModality(value: string): string {
  const caption = programModalityLabel(value);
  return Object.hasOwn(programVocabularyMessages, caption)
    ? text(caption as keyof typeof programVocabularyMessages)
    : caption;
}
