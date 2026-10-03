/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnvironmentInstallResultRead = {
  detail: string;
  exit_code?: (number | null);
  finished_at?: (string | null);
  plan_id: string;
  recipe_id: 'python-dependencies' | 'frontend-dependencies' | 'deployment-tools';
  started_at: string;
  status: 'running' | 'succeeded' | 'failed';
};
