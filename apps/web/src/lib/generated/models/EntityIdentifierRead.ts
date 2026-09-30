/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ReviewStatus } from './ReviewStatus';
export type EntityIdentifierRead = {
  namespace: string;
  normalized_value: string;
  review_status: ReviewStatus;
  source_document_id: (string | null);
  trusted_namespace: boolean;
  value: string;
};
