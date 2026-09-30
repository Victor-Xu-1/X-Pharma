/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PatentSavedSearchQuery = {
  analysis_view?: 'chart' | 'table';
  applicant?: (string | null);
  display_mode?: 'list' | 'landscape';
  entity_id?: (string | null);
  expiration_from?: (string | null);
  expiration_to?: (string | null);
  legal_status?: (string | null);
  priority_from?: (string | null);
  priority_to?: (string | null);
  'q'?: (string | null);
  sort?: Array<string>;
  sort_by?: 'priority_date' | 'family_identifier' | 'legal_status' | 'expiration_date';
  sort_direction?: 'asc' | 'desc';
};
