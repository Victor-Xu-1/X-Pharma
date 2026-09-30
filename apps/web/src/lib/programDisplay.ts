const programModalityLabels: Record<string, string> = {
  SMALL_MOLECULE: "小分子",
  ANTIBODY: "抗体",
  MONOCLONAL_ANTIBODY: "单克隆抗体",
  BISPECIFIC_ANTIBODY: "双特异性抗体",
  ANTIBODY_DRUG_CONJUGATE: "抗体偶联药物（ADC）",
  ADC: "抗体偶联药物（ADC）",
  PROTEIN: "蛋白药物",
  PEPTIDE: "多肽",
  OLIGONUCLEOTIDE: "寡核苷酸药物",
  RNA: "RNA 药物",
  CELL_THERAPY: "细胞治疗",
  GENE_THERAPY: "基因治疗",
  VACCINE: "疫苗",
  MOLECULAR_GLUE: "分子胶",
  PROTAC: "PROTAC",
  DEGRADER: "降解剂",
};

const programTagLabels: Record<string, string> = {
  BEST_IN_CLASS: "Best-in-Class",
  FIRST_IN_CLASS: "First-in-Class",
  NEW_MODALITY: "新模态",
  NEXT_GENERATION: "下一代",
};

const technicalProgramTags = new Set(["chembl"]);
const technicalProgramTagPrefixes = ["maximum clinical phase"];

function vocabularyKey(value: string): string {
  return value
    .trim()
    .toUpperCase()
    .replace(/[\s-]+/g, "_");
}

export function programModalityLabel(value: string): string {
  const normalized = value.trim();
  return programModalityLabels[vocabularyKey(normalized)] ?? normalized;
}

export function publicProgramTags(values: readonly string[] | null | undefined): string[] {
  const visible: string[] = [];
  const seen = new Set<string>();
  for (const value of values ?? []) {
    const normalized = value.trim().replace(/\s+/g, " ");
    const key = normalized.toLocaleLowerCase("en-US");
    if (
      !normalized ||
      technicalProgramTags.has(key) ||
      technicalProgramTagPrefixes.some((prefix) => key.startsWith(prefix)) ||
      seen.has(key)
    ) {
      continue;
    }
    visible.push(normalized);
    seen.add(key);
  }
  return visible;
}

export function isPublicProgramTag(value: string): boolean {
  return publicProgramTags([value]).length === 1;
}

export function programTagLabel(value: string): string {
  const normalized = value.trim();
  return programTagLabels[vocabularyKey(normalized)] ?? normalized;
}
