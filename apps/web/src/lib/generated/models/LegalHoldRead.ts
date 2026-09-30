/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type LegalHoldRead = {
  id: string;
  matter_reference: string;
  placed_at: string;
  placed_by_user_id: string;
  reason: string;
  release_reason: (string | null);
  released_at: (string | null);
  released_by_user_id: (string | null);
  scope_id: (string | null);
  scope_type: string;
  status: 'active' | 'released';
};
