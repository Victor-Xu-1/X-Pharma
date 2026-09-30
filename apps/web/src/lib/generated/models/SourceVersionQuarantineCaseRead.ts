/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QuarantineStatus } from './QuarantineStatus';
import type { SourceVersionQuarantineDecisionRead } from './SourceVersionQuarantineDecisionRead';
export type SourceVersionQuarantineCaseRead = {
  decisions?: Array<SourceVersionQuarantineDecisionRead>;
  error_code: (string | null);
  error_message: (string | null);
  file_name: string;
  logical_path: string;
  quarantine_status: QuarantineStatus;
  quarantine_version: number;
  source_asset_id: string;
  source_version_id: string;
  threat_name: (string | null);
  updated_at: string;
};
