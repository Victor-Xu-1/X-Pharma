/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WorkspaceExportCreate = {
  expected_version: number;
  export_format: 'csv' | 'json' | 'xlsx';
  fields: Array<string>;
  idempotency_key: string;
};
