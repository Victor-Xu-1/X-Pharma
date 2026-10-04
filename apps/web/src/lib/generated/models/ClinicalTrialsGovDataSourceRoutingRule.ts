/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ClinicalTrialsGovDataSourceRoutingRule = {
  max_records?: number;
  overlap_days?: number;
  page_size?: number;
  query_term: string;
  reconcile_interval_days?: number;
  sort: 'LastUpdatePostDate:asc' | 'LastUpdatePostDate:desc' | 'StudyFirstPostDate:asc' | 'StudyFirstPostDate:desc';
  start_date?: (string | null);
  sync_mode?: 'snapshot' | 'continuous';
  window_days?: number;
};
