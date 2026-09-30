/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WorkspaceDomainExportCreate = {
  dataset: 'entities' | 'pipelines' | 'trials' | 'patents' | 'deals' | 'regulatory' | 'epidemiology' | 'news';
  export_format: 'csv' | 'json' | 'xlsx';
  fields: Array<string>;
  idempotency_key: string;
  max_records: number;
  query?: Record<string, (string | number | boolean | Array<string>)>;
};
