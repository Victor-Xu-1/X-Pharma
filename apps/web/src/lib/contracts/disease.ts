import { contractRequest } from "../contract";
import type { DiseaseDossierResponse } from "../generated";
import { DiseasesService } from "../generated";

export type DiseaseDossier = DiseaseDossierResponse;

export const diseaseKeys = {
  dossier: (diseaseId: string) => ["intelligence", "disease", "dossier", diseaseId] as const,
};

export async function loadDiseaseDossier(diseaseId: string, signal?: AbortSignal): Promise<DiseaseDossier> {
  return contractRequest(
    DiseasesService.getDiseaseDossierApiV1DiseasesDiseaseIdDossierGet({
      diseaseId,
      limit: 100,
    }),
    signal,
  );
}
