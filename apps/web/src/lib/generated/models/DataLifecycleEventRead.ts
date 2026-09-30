/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataLifecycleEventRead = {
  action: 'purge' | 'blocked' | 'reauthorize';
  actor_user_id: string;
  created_at: string;
  data_class: string;
  details: Record<string, any>;
  id: string;
  idempotency_key: string;
  legal_hold_ids: Array<string>;
  outcome: 'succeeded' | 'blocked';
  policy_id: string;
  policy_version: number;
  reason: string;
  target_id: string;
  target_type: string;
};
