/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type TargetEvidenceRead = {
  direction: 'supports' | 'opposes' | 'neutral' | 'unknown';
  disease_entity_id?: (string | null);
  disease_name?: (string | null);
  effect_size?: (number | null);
  effect_unit?: (string | null);
  evidence_type: 'genetic_association' | 'expression' | 'functional' | 'translational' | 'biomarker' | 'safety';
  id: string;
  observed_at?: (string | null);
  p_value?: (number | null);
  population?: (string | null);
  qualifiers?: Record<string, any>;
  sample_size?: (number | null);
  source_document_id?: (string | null);
  source_record_id: string;
  source_system: string;
  study_name?: (string | null);
  summary: string;
  target_entity_id: string;
  target_name: string;
  tissue?: (string | null);
  variant?: (string | null);
};
