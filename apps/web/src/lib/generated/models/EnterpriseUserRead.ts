/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { UserRole } from './UserRole';
export type EnterpriseUserRead = {
  active: boolean;
  created_at: string;
  display_name: string;
  email: string;
  id: string;
  last_login_at: (string | null);
  oidc_issuer: (string | null);
  role: UserRole;
  tenant_id: string;
  token_version: number;
  updated_at: string;
};
