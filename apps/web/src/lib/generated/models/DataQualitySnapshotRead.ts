/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataQualitySnapshotRead = {
  created_at: string;
  definitions_version: string;
  id: string;
  measured_at: string;
  metrics: Record<string, Record<string, any>>;
  trigger: 'scheduled' | 'manual';
  window_end: string;
  window_start: string;
};
