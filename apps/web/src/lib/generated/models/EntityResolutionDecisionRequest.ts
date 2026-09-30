/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EntityResolutionDecisionRequest = {
  action: 'approve' | 'reject' | 'revert';
  canonical_entity_id?: (string | null);
  expected_status: 'pending' | 'approved' | 'rejected' | 'reverted';
  notes?: (string | null);
};
