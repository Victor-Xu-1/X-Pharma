/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QuarantineStatus } from './QuarantineStatus';
export type SourceVersionQuarantineDecisionRead = {
  action: string;
  actor_id: string;
  actor_type: string;
  created_at: string;
  details: Record<string, any>;
  expected_version: number;
  id: string;
  previous_status: QuarantineStatus;
  reason: string;
  resulting_status: QuarantineStatus;
  resulting_version: number;
  source_version_id: string;
  workflow_id: (string | null);
};
