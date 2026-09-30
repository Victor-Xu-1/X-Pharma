/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataExportCreate = {
  dataset: 'entities' | 'structures' | 'bioactivities' | 'competitive_programs' | 'clinical_trials' | 'patents' | 'deals' | 'regulatory_events' | 'fact_provenance';
  export_format?: 'jsonl' | 'csv';
  fields?: Array<string>;
  filters?: Record<string, any>;
  idempotency_key: string;
  max_billable_units: (number | string);
  max_records?: number;
};
