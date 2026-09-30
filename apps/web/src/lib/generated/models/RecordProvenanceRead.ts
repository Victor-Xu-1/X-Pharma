/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RecordProvenanceRead = {
  content_sha256?: (string | null);
  created_at: string;
  dataset_key: string;
  document_name: string;
  evidence_claim_id?: (string | null);
  id: string;
  license: Record<string, any>;
  locator?: (string | null);
  quote: string;
  resource_id: string;
  resource_type: 'activity_measurement' | 'assay' | 'clinical_trial' | 'compound_structure' | 'deal' | 'development_program' | 'epidemiology_observation' | 'evidence_claim' | 'news_event' | 'patient_population' | 'patent_family' | 'regulatory_event' | 'target_profile' | 'target_evidence';
  review_status?: (string | null);
  source_document_id?: (string | null);
  source_uri?: (string | null);
  source_version_id?: (string | null);
  subject_entity_id?: (string | null);
  warnings?: Array<string>;
};
