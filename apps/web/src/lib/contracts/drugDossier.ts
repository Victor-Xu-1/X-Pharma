import { contractRequest } from "../contract";
import type { DrugDossierResponse, DrugProgramSearchResult } from "../generated";
import { DrugsService } from "../generated";

export const drugDossierKeys = {
  detail: (drugId: string) => ["drug-dossier", drugId] as const,
};

export const drugProgramKeys = {
  page: (drugId: string, offset: number) => ["drug-programs", drugId, offset] as const,
};

export function loadDrugDossier(drugId: string, signal?: AbortSignal): Promise<DrugDossierResponse> {
  return contractRequest(DrugsService.getDrugDossierApiV1DrugsDrugIdDossierGet({ drugId, limit: 100 }), signal);
}

export function loadDrugPrograms(
  drugId: string,
  limit = 100,
  offset = 0,
  signal?: AbortSignal,
): Promise<DrugProgramSearchResult> {
  return contractRequest(DrugsService.listDrugProgramsApiV1DrugsDrugIdProgramsGet({ drugId, limit, offset }), signal);
}

export type DrugDossier = DrugDossierResponse;
export type DrugProgramPage = DrugProgramSearchResult;
