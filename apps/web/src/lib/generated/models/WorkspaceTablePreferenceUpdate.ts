/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WorkspaceTablePreferenceUpdate = {
  column_order?: Array<string>;
  column_visibility?: Record<string, boolean>;
  density?: 'comfortable' | 'compact';
  expected_version: number;
  schema_version?: number;
};
