import { contractRequest } from "../contract";
import type {
  BioactivityRead,
  ClinicalTrialRead,
  CompetitiveProgramRead,
  CompoundStructureRead,
  DealRead,
  EntityRelationshipRead,
  NewsEventSearchItemRead,
  PatentFamilyRead,
  RegulatoryEventRead,
  SarActivityRead,
  SarComparisonResult,
  TargetDossierResponse,
  TargetEvidenceRead,
  TargetProfileResponse,
} from "../generated";
import { ActivitiesService, TargetsService } from "../generated";

export type SarFilters = {
  standardType: string;
  assayType: string;
  assayFormat: string;
  organism: string;
  cellLine: string;
  offset: number;
};

export const targetKeys = {
  profile: (targetId: string) => ["target", targetId, "profile"] as const,
  dossier: (targetId: string) => ["target", targetId, "dossier"] as const,
  sar: (targetId: string, filters: SarFilters) => ["target", targetId, "sar", filters] as const,
};

export function loadTargetProfile(targetId: string, signal?: AbortSignal): Promise<TargetProfileResponse> {
  return contractRequest(TargetsService.getTargetProfileApiV1TargetsTargetIdProfileGet({ targetId }), signal);
}

export function loadTargetDossier(targetId: string, signal?: AbortSignal): Promise<TargetDossierResponse> {
  return contractRequest(
    TargetsService.getTargetDossierApiV1TargetsTargetIdDossierGet({ targetId, limit: 100 }),
    signal,
  );
}

export function loadTargetSar(
  targetId: string,
  filters: SarFilters,
  signal?: AbortSignal,
): Promise<SarComparisonResult> {
  return contractRequest(
    ActivitiesService.compareTargetSarApiV1TargetsTargetIdSarComparisonGet({
      targetId,
      standardType: filters.standardType || undefined,
      assayType: filters.assayType || undefined,
      assayFormat: filters.assayFormat || undefined,
      organism: filters.organism || undefined,
      cellLine: filters.cellLine || undefined,
      limit: 50,
      offset: filters.offset,
    }),
    signal,
  );
}

export type TargetDossier = TargetDossierResponse;
export type TargetProfile = TargetProfileResponse;
export type Bioactivity = BioactivityRead;
export type CompetitiveProgram = CompetitiveProgramRead;
export type ClinicalTrial = ClinicalTrialRead;
export type PatentFamily = PatentFamilyRead;
export type Deal = DealRead;
export type RegulatoryEvent = RegulatoryEventRead;
export type CompoundStructure = CompoundStructureRead;
export type TargetRelationship = EntityRelationshipRead;
export type TargetNewsEvent = NewsEventSearchItemRead;
export type TargetEvidence = TargetEvidenceRead;
export type SarActivity = SarActivityRead;
export type SarComparison = SarComparisonResult;
