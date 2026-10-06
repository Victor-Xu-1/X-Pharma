/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GovernanceStatus } from './GovernanceStatus';
export type StagedFactRead = {
  confidence: number;
  conflict_with_ids: Array<string>;
  created_at: string;
  fact_key?: (string | null);
  fact_kind: string;
  id: string;
  normalization_version: (string | null);
  payload: Record<string, any>;
  quality_findings: Array<Record<string, any>>;
  raw_payload: Record<string, any>;
  source_document_id: (string | null);
  source_locator: (string | null);
  source_quote: string;
  status: GovernanceStatus;
};
