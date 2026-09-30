/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnterpriseSessionRead = {
  current: boolean;
  expires_at: string;
  id: string;
  issued_at: string;
  revoke_reason: (string | null);
  revoked_at: (string | null);
  revoked_by_user_id: (string | null);
  user_display_name: string;
  user_email: string;
  user_id: string;
};
