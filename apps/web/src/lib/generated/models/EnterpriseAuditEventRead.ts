/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EnterpriseAuditEventRead = {
  action: string;
  actor_id: string;
  actor_type: string;
  details: Record<string, any>;
  id: string;
  occurred_at: string;
  outcome: string;
  request_id: string;
  resource_id: (string | null);
  resource_type: string;
};
