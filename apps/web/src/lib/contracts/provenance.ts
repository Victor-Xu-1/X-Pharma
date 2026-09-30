import { contractRequest } from "../contract";
import type { RecordProvenanceResponse } from "../generated";
import { EvidenceService } from "../generated";

export type ProvenanceResourceType =
  | "activity_measurement"
  | "assay"
  | "clinical_trial"
  | "compound_structure"
  | "deal"
  | "development_program"
  | "epidemiology_observation"
  | "evidence_claim"
  | "news_event"
  | "patent_family"
  | "regulatory_event"
  | "target_profile"
  | "target_evidence";

export type ProvenanceSelection = {
  resourceType: ProvenanceResourceType;
  resourceId: string;
  label: string;
};

export const provenanceKeys = {
  record: (resourceType: ProvenanceResourceType, resourceId: string) =>
    ["provenance", resourceType, resourceId] as const,
};

export async function loadRecordProvenance(
  selection: ProvenanceSelection,
  signal?: AbortSignal,
): Promise<RecordProvenanceResponse> {
  return contractRequest(
    EvidenceService.getRecordProvenanceApiV1ProvenanceResourceTypeResourceIdGet({
      resourceType: selection.resourceType,
      resourceId: selection.resourceId,
      limit: 100,
    }),
    signal,
  );
}
