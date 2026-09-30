/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EpidemiologySavedSearchQuery = {
  age_group?: (string | null);
  analysis_view?: 'chart' | 'table';
  disease_entity_id?: (string | null);
  display_mode?: 'list' | 'landscape';
  geography?: (string | null);
  measure?: ('prevalence' | 'incidence' | 'mortality' | 'patient_count' | 'diagnosed_count' | 'treated_count' | 'survival_rate' | 'daly' | 'other' | null);
  patient_population_id?: (string | null);
  period_end_to?: (string | null);
  period_start_from?: (string | null);
  population_scope?: (string | null);
  'q'?: (string | null);
  sex?: (string | null);
  sort?: Array<string>;
  sort_by?: 'period_end' | 'period_start' | 'disease' | 'measure' | 'value' | 'geography' | 'unit' | 'publisher' | 'sample_size';
  sort_direction?: 'asc' | 'desc';
  unit?: (string | null);
};
