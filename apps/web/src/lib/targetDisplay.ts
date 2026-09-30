const targetClassLabels: Record<string, string> = {
  SINGLE_PROTEIN: "单蛋白",
  PROTEIN_COMPLEX: "蛋白复合物",
  PROTEIN_COMPLEX_GROUP: "蛋白复合物组",
  PROTEIN_FAMILY: "蛋白家族",
  RNA: "RNA",
};

const organismLabels: Record<string, string> = {
  HOMO_SAPIENS: "人",
  MUS_MUSCULUS: "小鼠",
  RATTUS_NORVEGICUS: "大鼠",
};

function vocabularyKey(value: string): string {
  return value
    .trim()
    .toUpperCase()
    .replace(/[\s-]+/g, "_");
}

function displayValue(value: string | null | undefined, fallback: string, labels: Record<string, string>): string {
  const normalized = value?.trim() ?? "";
  if (!normalized) return fallback;
  return labels[vocabularyKey(normalized)] ?? normalized;
}

export function targetClassLabel(value: string | null | undefined): string {
  return displayValue(value, "未分类靶点", targetClassLabels);
}

export function organismLabel(value: string | null | undefined): string {
  return displayValue(value, "物种未记录", organismLabels);
}

export function targetDisplayIdentity({
  name,
  description,
  geneSymbol,
}: {
  name: string;
  description: string | null | undefined;
  geneSymbol: string | null | undefined;
}): { primaryName: string; fullName: string | null } {
  const normalizedName = name.trim();
  const normalizedGeneSymbol = geneSymbol?.trim() ?? "";
  const primaryName = normalizedGeneSymbol || normalizedName;
  const normalizedDescription = description?.trim() ?? "";
  const fullName =
    normalizedName && normalizedName.toLocaleLowerCase() !== primaryName.toLocaleLowerCase()
      ? normalizedName
      : normalizedDescription && normalizedDescription.toLocaleLowerCase() !== primaryName.toLocaleLowerCase()
        ? normalizedDescription
        : null;
  return { primaryName, fullName };
}
