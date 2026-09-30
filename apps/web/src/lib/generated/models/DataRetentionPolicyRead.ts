/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataRetentionPolicyRead = {
  active: boolean;
  configured_by_user_id: string;
  created_at: string;
  data_class: 'commercial_export_artifact' | 'source_asset_snapshot';
  geographic_scope: Array<string>;
  id: string;
  legal_basis: string;
  policy_version: number;
  retention_seconds: number;
  updated_at: string;
};
