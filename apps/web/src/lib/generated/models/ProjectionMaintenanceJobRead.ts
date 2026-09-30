/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ProjectionMaintenanceJobRead = {
  attempts: number;
  build_id: (string | null);
  completed_at: (string | null);
  created_at: string;
  id: string;
  last_error: (string | null);
  lease_expires_at: (string | null);
  operation: 'consistency_check' | 'rebuild';
  requested_by_user_id: string;
  result: Record<string, any>;
  started_at: (string | null);
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  updated_at: string;
  worker_id: (string | null);
};
