/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type IngestionRunReplayRequest = {
  expected_state: 'failed' | 'partial' | 'canceled';
  operation_key: string;
  reason: string;
};
