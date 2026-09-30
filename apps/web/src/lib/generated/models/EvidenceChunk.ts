/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EvidenceChunk = {
  content: string;
  dataset_id: string;
  document_id: string;
  document_name: string;
  metadata?: Record<string, any>;
  positions?: Array<any>;
  /**
   * Retriever ranking score; it is not normalized and is not a probability.
   */
  similarity?: (number | null);
};
