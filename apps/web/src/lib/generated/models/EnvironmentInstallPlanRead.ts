/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnvironmentInstallPlanRead = {
  commands: Array<Array<string>>;
  expires_at: string;
  generated_at: string;
  manifest_sha256: string;
  offline: boolean;
  plan_id: string;
  product_version: string;
  recipe_id: 'python-dependencies' | 'frontend-dependencies' | 'deployment-tools';
  revision: string;
  schema_version?: string;
};
