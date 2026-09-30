/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnterpriseApiKeySecretRead = {
  active: boolean;
  commercial_client_id: (string | null);
  commercial_client_name: (string | null);
  created_at: string;
  expires_at: (string | null);
  id: string;
  last_used_at: (string | null);
  name: string;
  prefix: string;
  revoked_at: (string | null);
  scopes: Array<string>;
  secret: string;
  status: 'active' | 'expired' | 'revoked' | 'disabled';
  updated_at: string;
};
