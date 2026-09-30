import { contractRequest } from "../contract";
import type { CompanyDossierResponse, CompanyTimelineResult } from "../generated";
import { CompaniesService } from "../generated";

export const companyKeys = {
  dossier: (companyId: string) => ["company-dossier", companyId] as const,
  timeline: (companyId: string, offset: number) => ["intelligence", "company-timeline", companyId, offset] as const,
};

export function loadCompanyDossier(companyId: string, signal?: AbortSignal): Promise<CompanyDossierResponse> {
  return contractRequest(
    CompaniesService.getCompanyDossierApiV1CompaniesCompanyIdDossierGet({ companyId, limit: 100 }),
    signal,
  );
}

export function loadCompanyTimeline(
  companyId: string,
  offset = 0,
  signal?: AbortSignal,
): Promise<CompanyTimelineResult> {
  return contractRequest(
    CompaniesService.getCompanyTimelineApiV1CompaniesCompanyIdTimelineGet({
      companyId,
      limit: 100,
      offset,
    }),
    signal,
  );
}

export type CompanyDossier = CompanyDossierResponse;
