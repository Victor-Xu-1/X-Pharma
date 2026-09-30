/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type PublicationBatchPreviewRequest = {
  idempotency_key: string;
  operation: 'publish' | 'withdraw';
  reason?: (string | null);
  staged_fact_ids: Array<string>;
};
