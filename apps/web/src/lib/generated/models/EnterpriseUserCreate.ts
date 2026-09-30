/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { UserRole } from './UserRole';
export type EnterpriseUserCreate = {
  display_name: string;
  email: string;
  initial_password?: (string | null);
  oidc_issuer?: (string | null);
  oidc_subject?: (string | null);
  role?: UserRole;
};
