/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicationBatchItemRead } from './PublicationBatchItemRead';
export type PublicationBatchRead = {
  blocked_count: number;
  committed_at: (string | null);
  committed_by_user_id: (string | null);
  created_at: string;
  expected_count: number;
  id: string;
  idempotency_key: string;
  items?: Array<PublicationBatchItemRead>;
  operation: 'publish' | 'withdraw';
  preview_sha256: string;
  reason: (string | null);
  requested_by_user_id: string;
  result: Record<string, any>;
  status: 'previewed' | 'committed' | 'failed';
  updated_at: string;
};
