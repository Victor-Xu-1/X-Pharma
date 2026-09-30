/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataQualityIssueActionRequest = {
  action: 'assign' | 'acknowledge' | 'resolve' | 'waive';
  expected_version: number;
  notes?: (string | null);
  owner_user_id?: (string | null);
};
