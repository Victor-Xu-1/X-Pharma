/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type InvitationRead = {
  claimed_at: (string | null);
  created_at: string;
  email: string;
  expires_at: string;
  id: string;
  revoked_at: (string | null);
  readonly status: 'active' | 'consumed' | 'revoked' | 'expired';
  tenant_id: string;
};
