/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataQualityIssueEventRead = {
  action: string;
  actor_id: string;
  actor_type: string;
  details: Record<string, any>;
  id: string;
  occurred_at: string;
  previous_status: (string | null);
  resulting_status: string;
};
