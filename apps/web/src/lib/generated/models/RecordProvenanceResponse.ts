/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EvidenceLicenseScope } from './EvidenceLicenseScope';
import type { RecordProvenanceRead } from './RecordProvenanceRead';
export type RecordProvenanceResponse = {
  items: Array<RecordProvenanceRead>;
  license_scopes: Array<EvidenceLicenseScope>;
  resource_id: string;
  resource_type: 'activity_measurement' | 'assay' | 'clinical_trial' | 'compound_structure' | 'deal' | 'development_program' | 'epidemiology_observation' | 'evidence_claim' | 'news_event' | 'patient_population' | 'patent_family' | 'regulatory_event' | 'target_profile' | 'target_evidence';
  warnings?: Array<string>;
};
