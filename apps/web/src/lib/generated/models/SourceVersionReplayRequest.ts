/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SourceVersionState } from './SourceVersionState';
export type SourceVersionReplayRequest = {
  expected_error_code?: (string | null);
  expected_state: SourceVersionState;
  from_stage?: 'malware_scan' | 'parse' | 'governance' | 'retrieval';
  operation_key: string;
  reason: string;
};
