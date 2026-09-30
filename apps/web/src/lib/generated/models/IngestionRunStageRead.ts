/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type IngestionRunStageRead = {
  completed_items: number;
  failed_items: number;
  stage: 'discovery' | 'snapshot' | 'malware_scan' | 'parse' | 'retrieval' | 'governance';
  status: 'not_started' | 'running' | 'succeeded' | 'failed' | 'skipped' | 'canceled';
  total_items: number;
};
