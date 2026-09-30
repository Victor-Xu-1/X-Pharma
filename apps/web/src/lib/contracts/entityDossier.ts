import { contractRequest } from "../contract";
import type { DrugComparisonResult, EntityDossierResponse } from "../generated";
import { DrugsService, EntitiesService } from "../generated";

export const entityDossierKeys = {
  detail: (entityId: string) => ["entity-dossier", entityId] as const,
  drugComparison: (entityIds: string[]) => ["drug-comparison", ...entityIds] as const,
};

export function loadEntityDossier(entityId: string, signal?: AbortSignal): Promise<EntityDossierResponse> {
  return contractRequest(
    EntitiesService.getEntityDossierApiV1EntitiesEntityIdDossierGet({ entityId, limit: 50 }),
    signal,
  );
}

export function loadDrugComparison(entityIds: string[], signal?: AbortSignal): Promise<DrugComparisonResult> {
  return contractRequest(DrugsService.compareDrugsApiV1DrugsComparisonGet({ drugIds: entityIds }), signal);
}

export type EntityDossier = EntityDossierResponse;
export type DrugComparison = DrugComparisonResult;
