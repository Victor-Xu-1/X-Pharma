import type { CompanyDossier } from "../../lib/contracts/company";

export type LoadedCompanyAsset = { id: string; name: string; phases: string[]; modalities: string[] };

/** A summary of returned program rows, never a global drug-stage authority. */
export function loadedCompanyAssets(programs: CompanyDossier["programs"]): LoadedCompanyAsset[] {
  const assets = new Map<string, LoadedCompanyAsset>();
  for (const program of programs) {
    const asset = assets.get(program.drug_entity_id) ?? {
      id: program.drug_entity_id,
      name: program.drug_name,
      phases: [],
      modalities: [],
    };
    if (!asset.phases.includes(program.phase)) asset.phases.push(program.phase);
    if (program.modality && !asset.modalities.includes(program.modality)) asset.modalities.push(program.modality);
    assets.set(asset.id, asset);
  }
  return [...assets.values()];
}
