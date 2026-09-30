/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SourceVersionQuarantineDecisionRequest = {
  action: 'hold' | 'reject' | 'rescan';
  expected_version: number;
  operation_key: string;
  reason: string;
};
