/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PatentClaimRead = {
  claim_number: string;
  claim_type: 'composition' | 'method' | 'use' | 'formulation' | 'sequence' | 'other';
  scope?: (string | null);
  source_document_id?: (string | null);
  summary: string;
};
