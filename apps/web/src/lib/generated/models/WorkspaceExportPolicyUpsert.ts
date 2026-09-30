/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WorkspaceExportPolicyUpsert = {
  allowed_fields: Array<string>;
  allowed_formats: Array<'csv' | 'json' | 'xlsx'>;
  attribution: string;
  enabled: boolean;
  max_records_per_export: number;
  policy_version: string;
};
