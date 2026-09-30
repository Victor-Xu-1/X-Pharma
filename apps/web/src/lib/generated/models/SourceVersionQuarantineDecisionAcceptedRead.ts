/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QuarantineStatus } from './QuarantineStatus';
export type SourceVersionQuarantineDecisionAcceptedRead = {
  action: 'hold' | 'reject' | 'rescan';
  decision_id: string;
  quarantine_status: QuarantineStatus;
  quarantine_version: number;
  source_version_id: string;
  status: string;
  workflow_id: (string | null);
};
